"""CounterPick local — fase 1.

Abre o site em http://localhost:5002 só neste computador.
A chave da Riot fica no arquivo .env (nunca no navegador).
"""
import ipaddress
import os
import re
import shutil
import subprocess
import threading
import time

from flask import Flask, jsonify, request, send_from_directory

import json
import math
from urllib.parse import quote

import dados
import riot_coletor
from opgg import chave_opgg
from recomendar import recomendar
from riot import PLATAFORMA, RiotAPI, RiotErro

PASTA = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(PASTA, "site")
PORTA = int(os.environ.get("COUNTERPICK_PORTA", "5002"))


def porta_ocupada(porta):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def ler_env(caminho):
    """Lê KEY=valor do .env sem depender de biblioteca extra."""
    valores = {}
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith("#") and "=" in linha:
                    k, v = linha.split("=", 1)
                    valores[k.strip()] = v.strip().strip('"').strip("'")
    return valores


def chave_atual():
    # Relê o .env a cada pedido: dá para trocar a chave (se precisar gerar outra) sem reiniciar.
    return ler_env(os.path.join(PASTA, ".env")).get("RIOT_API_KEY") or os.environ.get("RIOT_API_KEY", "")


app = Flask(__name__, static_folder=SITE, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 26 * 1024 * 1024  # nenhum pedido maior que isso (prints incluídos)
_riot = {"chave": None, "api": None}


def riot():
    k = chave_atual()
    if k != _riot["chave"]:
        _riot["chave"], _riot["api"] = k, RiotAPI(k)
    return _riot["api"]


# ---------- segurança ----------
# Endereços aceitos. No modo amigos entram também o IP e o nome deste PC na rede privada do Tailscale.
HOSTS_OK = {f"localhost:{PORTA}", f"127.0.0.1:{PORTA}"}
ORIGENS_OK = {f"http://{h}" for h in HOSTS_OK}
REDE_TAILSCALE = [ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48")]
SO_DONO = {"/api/dados/atualizar", "/api/riot/coletar", "/api/riot/parar", "/api/riot/perfil"}
LIMITES = {"/api/riot/perfil": 6, "/api/riot/coletar": 3, "/api/perfil_opgg": 10, "/api/perfil_riot": 4,
           "/api/dados/atualizar": 3, "/api/recomendar": 40, "/api/preparar": 60, "/api/ler_print": 15}
_limites = {}
_trava_limite = threading.Lock()


def dentro_do_limite(chave, maximo, janela=60):
    """Limite simples por pessoa e por rota (protege a cota da chave da Riot e o op.gg)."""
    with _trava_limite:
        agora = time.monotonic()
        if len(_limites) > 5000:
            for k in [k for k, v in _limites.items() if not v or agora - v[-1] > janela]:
                del _limites[k]
        hist = [t for t in _limites.get(chave, []) if agora - t < janela]
        if len(hist) >= maximo:
            _limites[chave] = hist
            return False
        hist.append(agora)
        _limites[chave] = hist
        return True


def e_o_dono():
    """Só quem está no próprio PC (127.0.0.1) é o dono. Amigos chegam pelo IP do Tailscale."""
    return request.remote_addr in ("127.0.0.1", "::1")


def da_rede_tailscale(ip):
    try:
        a = ipaddress.ip_address(ip)
        return any(a in r for r in REDE_TAILSCALE)
    except ValueError:
        return False


@app.before_request
def proteger():
    # 0) Quem pode chegar: este PC ou alguém da sua rede privada do Tailscale. Mais ninguém.
    if not (e_o_dono() or da_rede_tailscale(request.remote_addr)):
        return jsonify(erro="Acesso negado."), 403
    # 1) DNS rebinding: só atende pedidos endereçados a este computador, nesta porta.
    if request.host not in HOSTS_OK:
        return jsonify(erro="Acesso negado."), 403
    if request.path.startswith("/api/"):
        # 2) CSRF: outro site não consegue mandar este cabeçalho sem a permissão do navegador (CORS),
        #    e este servidor nunca dá essa permissão. Assim só a própria página usa a API.
        if request.headers.get("X-CounterPick") != "1":
            return jsonify(erro="Acesso negado."), 403
        origem = request.headers.get("Origin")
        if origem and origem not in ORIGENS_OK:
            return jsonify(erro="Acesso negado."), 403
        # 3) Coisas que mexem nos dados ou gastam muita cota: só o dono, no próprio PC.
        if request.path in SO_DONO and not e_o_dono():
            return jsonify(erro="Só o dono do sistema pode fazer isso."), 403
        # 4) Limite de uso por pessoa nas rotas que gastam a sua chave da Riot ou consultam o op.gg.
        if request.path in LIMITES and not dentro_do_limite((request.path, request.remote_addr), LIMITES[request.path]):
            return jsonify(erro="Muitos pedidos seguidos. Espere um minuto e tente de novo."), 429
        registrar_acesso()


# ---------- quem acessou (modo amigos) ----------
_quem = {}
LOG_ACESSOS = os.path.join(PASTA, "acessos.log")


def quem_e(ip):
    """Nome do amigo na rede do Tailscale (ex.: amigo@gmail.com). Guardado em memória."""
    if ip in ("127.0.0.1", "::1"):
        return "você"
    if ip not in _quem:
        nome = ip
        exe = tailscale_exe()
        if exe:
            try:
                out = subprocess.run([exe, "whois", "--json", ip], capture_output=True, text=True, timeout=4)
                nome = (json.loads(out.stdout or "{}").get("UserProfile") or {}).get("LoginName") or ip
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        _quem[ip] = nome
    return _quem[ip]


def registrar_acesso():
    """Uma linha por consulta: quando, quem e o quê. Sem guardar o que a pessoa digitou."""
    if request.path in ("/api/dados/status", "/api/status"):
        return
    try:
        if os.path.exists(LOG_ACESSOS) and os.path.getsize(LOG_ACESSOS) > 2_000_000:
            os.replace(LOG_ACESSOS, LOG_ACESSOS + ".1")
        with open(LOG_ACESSOS, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%d/%m/%Y %H:%M:%S')}\t{quem_e(request.remote_addr)}\t{request.method} {request.path}\n")
    except OSError:
        pass


def tailscale_exe():
    for c in (shutil.which("tailscale"), r"C:\Program Files\Tailscale\tailscale.exe"):
        if c and os.path.exists(c):
            return c
    return None


def tailscale_endereco():
    """(ip, nome) deste PC na rede do Tailscale, ou (None, None) se não estiver instalado/conectado."""
    exe = tailscale_exe()
    if not exe:
        return None, None
    try:
        st = json.loads(subprocess.run([exe, "status", "--json"], capture_output=True, text=True, timeout=5).stdout or "{}")
        eu = st.get("Self") or {}
        ips = [i for i in eu.get("TailscaleIPs") or [] if "." in i]
        nome = (eu.get("DNSName") or "").rstrip(".")
        return (ips[0] if ips else None), (nome or None)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, None


@app.after_request
def cabecalhos_seguros(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'none'; object-src 'none'")
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------- entradas à prova de lixo: tipo errado vira vazio, nunca derruba o servidor ----------
def corpo_json():
    d = request.get_json(silent=True)
    return d if isinstance(d, dict) else {}


def lista(v, limite):
    return v[:limite] if isinstance(v, list) else []


def item(v):
    return v if isinstance(v, dict) else {}


def inteiro(v, padrao=0, minimo=0, maximo=10**6):
    try:
        n = int(v)
    except (TypeError, ValueError, OverflowError):
        return padrao
    return max(minimo, min(maximo, n))


def real(v, padrao=0.0, minimo=0.0, maximo=100.0):
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return padrao
    return padrao if not math.isfinite(f) else max(minimo, min(maximo, f))


@app.errorhandler(500)
def erro_interno(_):
    return jsonify(erro="Algo deu errado aqui. Tente de novo."), 500


@app.errorhandler(404)
def nao_achou(_):
    return jsonify(erro="Não encontrado."), 404


@app.errorhandler(413)
def grande_demais(_):
    return jsonify(erro="Arquivo grande demais."), 413


@app.get("/")
def inicio():
    return send_from_directory(SITE, "index.html")


@app.get("/api/status")
def status():
    # Diz só SE existe chave; nunca devolve a chave.
    resp = {"local": True, "riot_configurada": riot().configurada, "dono": e_o_dono()}
    rid = ler_env(os.path.join(PASTA, ".env")).get("COUNTERPICK_RIOT_ID", "").strip()
    if e_o_dono() and RIOT_ID.match(rid):       # só o dono vê o próprio Riot ID; amigos não
        resp["dono_riot_id"] = rid
    return jsonify(**resp)


# ---------- dados do patch (OP.GG + Data Dragon) ----------
@app.get("/api/dados/status")
def dados_status():
    con = dados.conectar()
    try:
        n_build = con.execute("SELECT COUNT(*) FROM builds").fetchone()[0]
        n_riot = con.execute("SELECT COUNT(*) FROM riot_partidas WHERE patch=?", (dados.info(con, "patch") or "",)).fetchone()[0]
        return jsonify(patch=dados.patch_oficial(dados.info(con, "patch")), sincronizado_em=dados.info(con, "sincronizado_em"),
                       builds=n_build, partidas_riot=n_riot, sync=dict(dados.progresso), coleta=dict(riot_coletor.progresso))
    finally:
        con.close()


@app.post("/api/dados/atualizar")
def dados_atualizar():
    dados.sincronizar_em_segundo_plano(forcar=True)
    return jsonify(ok=True)


ROTA_SITE = {"TOP": "top", "JUNGLE": "jungle", "MID": "mid", "ADC": "adc", "SUPPORT": "support"}
_cache_confronto = {}


def buscar_confronto(rota, meu, oponente):
    """Build e dica do op.gg para MEU x OPONENTE na rota. Guardado em memória: só a 1ª vez demora."""
    chave = (rota, meu, oponente)
    if chave not in _cache_confronto:
        g = dados.opgg.confronto(rota, chave_opgg(meu), chave_opgg(oponente))
        con = dados.conectar()
        itens = json.loads(dados.info(con, "itens_json")); tr = json.loads(dados.info(con, "transforma"))
        con.close()
        gd = g.get("data") or {}
        _cache_confronto[chave] = (dados.montar_build(gd, itens, tr), gd.get("opponent_champion_tip"),
                                   gd.get("lane_advantage_champion"), gd.get("recommended_play_style"))
    return _cache_confronto[chave]


# ---------- adiantar buscas lentas enquanto a pessoa ainda preenche os campos ----------
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

_fila_preparo = ThreadPoolExecutor(max_workers=1)  # uma de cada vez: educado com o op.gg
_preparando = set()
_trava_preparo = threading.Lock()


def _agendar(chave, func, *args):
    with _trava_preparo:
        if chave in _preparando:
            return
        _preparando.add(chave)

    def rodar():
        try:
            func(*args)
        except Exception:
            pass
        finally:
            with _trava_preparo:
                _preparando.discard(chave)
    _fila_preparo.submit(rodar)


@app.post("/api/preparar")
def api_preparar():
    """A página avisa o que já foi preenchido; o servidor busca em segundo plano o que ainda não tem guardado
    (sinergia de cada aliado e a build do confronto da 'Minha escolha'). Responde na hora."""
    d = corpo_json()
    rota = ROTA_SITE.get(str(d.get("rota", "")).upper())
    if not rota:
        return jsonify(ok=False), 400
    con = dados.conectar()
    nomes = dados.mapa_nomes(con)
    con.close()
    for a in lista(d.get("aliados"), 5):
        n = nomes.get(dados.norm(item(a).get("name")))
        papel = ROTA_SITE.get(str(item(a).get("role", "")).upper())
        if n and papel and papel != rota:
            _agendar(("sin", papel, n, rota), dados.sinergias, papel, n, rota)
    meu = nomes.get(dados.norm(str(d.get("meu")))) if isinstance(d.get("meu"), str) else None
    op = nomes.get(dados.norm(str(d.get("oponente")))) if isinstance(d.get("oponente"), str) else None
    if meu and op and (rota, meu, op) not in _cache_confronto:
        _agendar(("conf", rota, meu, op), buscar_confronto, rota, meu, op)
    return jsonify(ok=True)


def _nomes_validos(lista, nomes, limite=10):
    out = []
    for x in (lista if isinstance(lista, list) else [])[:limite]:
        n = nomes.get(dados.norm(x if isinstance(x, str) else item(x).get("name")))
        if n:
            out.append(n)
    return out


@app.post("/api/recomendar")
def api_recomendar():
    d = corpo_json()
    rota = ROTA_SITE.get(str(d.get("rota", "")).upper())
    modo = d.get("modo") if d.get("modo") in ("lane", "full", "draft") else "full"
    if not rota:
        return jsonify(erro="Rota inválida."), 400
    con = dados.conectar()
    nomes = dados.mapa_nomes(con)
    con.close()
    inimigos = []
    for e in lista(d.get("inimigos"), 5):
        n = nomes.get(dados.norm(item(e).get("name")))
        if n:
            inimigos.append({"name": n, "role": ROTA_SITE.get(str(item(e).get("role", "")).upper())})
    aliados = []
    for a in lista(d.get("aliados"), 5):
        n = nomes.get(dados.norm(a if isinstance(a, str) else item(a).get("name")))
        if n:
            papel = None if isinstance(a, str) else ROTA_SITE.get(str(item(a).get("role", "")).upper())
            aliados.append({"name": n, "role": papel})
    pool = _nomes_validos(d.get("pool"), nomes, 20)
    meu = (_nomes_validos([d.get("meu")], nomes, 1) or [None])[0] if isinstance(d.get("meu"), str) else None
    perfil = []
    for c in lista(d.get("perfil"), 200):
        n = nomes.get(dados.norm(item(c).get("n")))
        if n:
            perfil.append({"n": n, "g": inteiro(item(c).get("g"), 0, 0, 100000), "wr": real(item(c).get("wr"), 0, 0, 100)})
    depois = inteiro(item(d.get("draft")).get("after", 0), 0, 0, 5)
    nomes_ini = [e["name"] for e in inimigos]
    if modo == "draft":
        r = recomendar(rota, "draft", nomes_ini, aliados, pool, perfil, {"after": depois}, meu)
    else:
        # o recomendador espera papéis em minúsculo
        r = recomendar(rota, modo, [{"name": e["name"], "role": e["role"]} for e in inimigos], aliados, pool, perfil, None, meu)
    if "erro" in r:
        return jsonify(r), 409
    # ordem das habilidades nível a nível: builds antigas não têm; busca uma vez no OP.GG e guarda no banco
    for p in r["picks"] + ([r["melhorPool"]] if r.get("melhorPool") else []):
        if not p.get("order"):
            try:
                b = dados.completar_ordem(rota, p["name"])
                if b:
                    p["order"] = b.get("order") or []
                    p["max"] = p.get("max") or b.get("max")
            except Exception:
                pass
    # "Já escolhi" + oponente conhecido: busca no OP.GG a build e a dica DESSE confronto (1 consulta, guardada)
    oponente = next((e["name"] for e in inimigos if e.get("role") == rota), None) if modo != "draft" else None
    if meu and oponente and r["picks"]:
        try:
            b, dica, vantagem, estilo = buscar_confronto(rota, meu, oponente)
            p = r["picks"][0]
            for k in ("runes", "spells", "max", "order", "start", "boots", "core", "later"):
                if b.get(k):
                    p[k] = b[k]
            p["buildNote"] = f"Runas e itens do op.gg para {meu} contra {oponente} neste patch."
            extra = []
            if vantagem:
                extra.append("Vantagem de lane: " + ("equilibrada" if vantagem == "EVEN" else vantagem))
            if estilo:
                extra.append("estilo recomendado: " + {"aggressive": "agressivo", "defensive": "defensivo", "passive": "passivo", "even": "equilibrado"}.get(estilo, estilo))
            if dica:
                extra.append("Dica do op.gg (em inglês): " + dica)
            if extra:
                p["plan"] = " · ".join(extra)
        except Exception:
            pass
    return jsonify(r)


# ---------- perfil pelo Riot ID (OP.GG, não precisa de chave) ----------
@app.get("/api/perfil_opgg")
def perfil_opgg():
    riot_id = (request.args.get("riot_id") or "").strip()
    regiao = (request.args.get("regiao") or "BR").upper()
    m = RIOT_ID.match(riot_id)
    if not m or regiao.lower() not in PLATAFORMA:
        return jsonify(erro="Use o formato nome#TAG, por exemplo Nome#BR1."), 400
    try:
        r = dados.opgg.perfil(m.group(1), m.group(2), regiao)
    except Exception:
        return jsonify(erro="Não achei esse perfil no OP.GG. Confira o nome#TAG e a região."), 404
    s = ((r or {}).get("data") or {}).get("summoner") or {}
    con = dados.conectar()
    nomes = dados.mapa_nomes(con)
    papel = {}
    for row in con.execute("SELECT rota, campeao, role_rate FROM meta"):
        atual = papel.get(row["campeao"])
        if not atual or (row["role_rate"] or 0) > atual[1]:
            papel[row["campeao"]] = (row["rota"], row["role_rate"] or 0)
    con.close()
    champs = []
    for c in (s.get("most_champions") or {}).get("champion_stats") or []:
        n = nomes.get(dados.norm(c.get("champion_name")))
        g = int(c.get("play") or 0)
        if not n or not g:
            continue
        minutos = max(1, (c.get("game_length_second") or 0) / 60)
        cs_min = (c.get("minion_kill") or 0) / minutos
        jg = (c.get("neutral_minion_kill") or 0) / g
        # monstros da selva por jogo e farm por minuto dizem a rota melhor que o campeão em si
        rota = "jungle" if jg >= 35 else ("support" if cs_min < 2.5 else papel.get(n, ("mid",))[0])
        if rota == "jungle" and papel.get(n, ("",))[0] not in ("jungle",) and cs_min >= 5:
            rota = papel.get(n, ("mid",))[0]
        mortes = c.get("death") or 0
        kda = round(((c.get("kill") or 0) + (c.get("assist") or 0)) / max(1, mortes), 2)
        champs.append({"n": n, "r": [ROTA_SITE_INV[rota]], "g": g, "wr": round(100 * (c.get("win") or 0) / g), "kda": kda})
    champs.sort(key=lambda x: -x["g"])
    if not champs:
        return jsonify(erro="O perfil não tem ranqueadas nesta temporada."), 404
    solo = next((x for x in s.get("league_stats") or [] if x.get("game_type") in ("SOLORANKED", "SOLO", "RANKED_SOLO_5x5")), None)
    ti = (solo or {}).get("tier_info") or {}
    tiers = {"IRON": "Ferro", "BRONZE": "Bronze", "SILVER": "Prata", "GOLD": "Ouro", "PLATINUM": "Platina", "EMERALD": "Esmeralda",
             "DIAMOND": "Diamante", "MASTER": "Mestre", "GRANDMASTER": "Grão-Mestre", "CHALLENGER": "Desafiante"}
    rank = (f'{tiers.get(str(ti.get("tier")).upper(), ti.get("tier"))} {ti.get("division") or ""} Solo/Duo · {ti.get("lp", 0)} PDL · '
            f'{solo.get("win", 0)}V {solo.get("lose", 0)}D') if solo and ti.get("tier") else "Sem ranqueada solo"
    por_rota = {}
    for c in champs:
        por_rota[c["r"][0]] = por_rota.get(c["r"][0], 0) + c["g"]
    total = sum(por_rota.values()) or 1
    main = max(por_rota, key=por_rota.get)
    share = ", ".join(f"{k} {round(100 * v / total)}%" for k, v in sorted(por_rota.items(), key=lambda kv: -kv[1]))
    return jsonify(name=f"{m.group(1)}#{m.group(2).upper()}", rank=rank, main=main, roleShare=share, champs=champs,
                   url=f"https://op.gg/pt/lol/summoners/{regiao.lower()}/{quote(m.group(1), safe='')}-{quote(m.group(2), safe='')}")


ROTA_SITE_INV = {v: k for k, v in ROTA_SITE.items()}


# ---------- perfil pelo Riot ID direto da Riot (precisa da chave) ----------
POSICAO_SITE = {"TOP": "TOP", "JUNGLE": "JUNGLE", "MIDDLE": "MID", "BOTTOM": "ADC", "UTILITY": "SUPPORT"}
ELO_PT = {"IRON": "Ferro", "BRONZE": "Bronze", "SILVER": "Prata", "GOLD": "Ouro", "PLATINUM": "Platina", "EMERALD": "Esmeralda",
          "DIAMOND": "Diamante", "MASTER": "Mestre", "GRANDMASTER": "Grão-Mestre", "CHALLENGER": "Desafiante"}


@app.get("/api/perfil_riot")
def perfil_riot():
    riot_id = (request.args.get("riot_id") or "").strip()
    regiao = (request.args.get("regiao") or "br").lower()
    m = RIOT_ID.match(riot_id)
    if not m or regiao not in PLATAFORMA:
        return jsonify(erro="Use o formato nome#TAG, por exemplo Nome#BR1."), 400
    api = riot()
    if not api.configurada:
        return jsonify(erro="sem_chave"), 412
    try:
        conta = api.conta_por_riot_id(regiao, m.group(1), m.group(2))
        puuid = conta["puuid"]
        filas = api.ranqueadas(regiao, puuid)
        solo = next((f for f in filas if f.get("queueType") == "RANKED_SOLO_5x5"), None)
        flex = next((f for f in filas if f.get("queueType") == "RANKED_FLEX_SR"), None)
        ids = api.ids_partidas(regiao, puuid, quantidade=40)
        tipo = "solo/duo"
        if len(ids) < 15:  # joga pouco solo/duo: usa solo/duo + flex para o perfil não ficar vazio
            ids = api.ids_partidas(regiao, puuid, quantidade=40, fila=None)
            tipo = "solo/duo e flex"
        con = dados.conectar()
        nomes = dados.mapa_nomes(con)
        con.close()
        por_champ = {}
        for mid in ids:
            p = api.partida(regiao, mid)
            eu = next((x for x in p["info"]["participants"] if x["puuid"] == puuid), None)
            if not eu or p["info"].get("gameDuration", 0) < 300:
                continue
            n = nomes.get(dados.norm(eu["championName"]))
            if not n:
                continue
            c = por_champ.setdefault(n, {"g": 0, "w": 0, "k": 0, "d": 0, "a": 0, "rotas": {}})
            c["g"] += 1; c["w"] += 1 if eu["win"] else 0
            c["k"] += eu["kills"]; c["d"] += eu["deaths"]; c["a"] += eu["assists"]
            rota = POSICAO_SITE.get(eu.get("teamPosition") or "")
            if rota:
                c["rotas"][rota] = c["rotas"].get(rota, 0) + 1
    except RiotErro as e:
        codigo = e.status if e.status in (401, 403, 404, 429) else 502
        msg = "Não achei esse Riot ID na Riot. Confira o nome#TAG." if e.status == 404 else e.mensagem
        return jsonify(erro=msg), codigo
    champs = []
    for n, c in por_champ.items():
        rotas = sorted(c["rotas"], key=lambda r: -c["rotas"][r]) or ["MID"]
        champs.append({"n": n, "r": rotas, "g": c["g"], "wr": round(100 * c["w"] / c["g"]),
                       "kda": round((c["k"] + c["a"]) / max(1, c["d"]), 2)})
    champs.sort(key=lambda x: -x["g"])
    if not champs:
        return jsonify(erro="Esse jogador não tem ranqueadas solo recentes."), 404
    por_rota = {}
    for c in champs:
        por_rota[c["r"][0]] = por_rota.get(c["r"][0], 0) + c["g"]
    main = max(por_rota, key=por_rota.get)
    jogos = sum(c["g"] for c in champs)
    def fila_txt(f, nome_fila):
        return (f'{ELO_PT.get(f["tier"], f["tier"].title())} {f["rank"]} {nome_fila} · {f["leaguePoints"]} PDL · '
                f'{f["wins"]}V {f["losses"]}D')
    rank = fila_txt(solo, "Solo/Duo") if solo else (fila_txt(flex, "Flex") if flex else "Sem elo nesta temporada")
    nome = f'{conta.get("gameName", m.group(1))}#{conta.get("tagLine", m.group(2))}'
    return jsonify(name=nome, rank=rank, main=main, champs=champs, fonte=f"Riot · últimas {jogos} ranqueadas ({tipo})",
                   url=f"https://op.gg/pt/lol/summoners/{regiao}/{quote(m.group(1), safe='')}-{quote(m.group(2), safe='')}")


# ---------- ler print (seleção de campeões / Tab) no próprio PC ----------
@app.post("/api/ler_print")
def ler_print():
    """Recebe o print (bytes da imagem), devolve os campeões de cada lado. Nada é gravado em disco."""
    try:
        import leitor_print
    except ImportError:
        return jsonify(erro="Falta instalar a leitura de print. Feche e abra o INICIAR.bat (ele instala sozinho)."), 501
    corpo = request.get_data(cache=False)
    if not corpo or len(corpo) > 25 * 1024 * 1024:
        return jsonify(erro="Mande um print PNG ou JPG de até 25 MB."), 400
    if not (corpo[:8] == b"\x89PNG\r\n\x1a\n" or corpo[:3] == b"\xff\xd8\xff" or (corpo[:4] == b"RIFF" and corpo[8:12] == b"WEBP")):
        return jsonify(erro="Esse arquivo não é uma imagem PNG, JPG ou WEBP."), 400
    con = dados.conectar()
    try:
        mapa = {r["id"]: r["nome"] for r in con.execute("SELECT id, nome FROM campeoes")}
        rr = {}
        for r in con.execute("SELECT rota, campeao, role_rate FROM meta"):
            rr.setdefault(r["campeao"], {})[r["rota"]] = r["role_rate"] or 0
    finally:
        con.close()
    try:
        r = leitor_print.ler(corpo, mapa, rr)
    except ValueError as e:
        return jsonify(erro=str(e)), 400
    except Exception:
        return jsonify(erro="Não consegui ler esse print. Tente um print da seleção de campeões ou do Tab."), 422
    return jsonify(r)


@app.post("/api/riot/parar")
def riot_parar():
    riot_coletor.progresso["parar"] = True
    return jsonify(ok=True)


# ---------- fase 2: coleta de partidas da Riot ----------
@app.post("/api/riot/coletar")
def riot_coletar():
    if not riot().configurada:
        return jsonify(erro="Configure a chave da Riot no .env primeiro."), 400
    meta = inteiro(corpo_json().get("partidas", 200), 200, 20, 5000)
    riot_coletor.coletar_em_segundo_plano(chave_atual(), meta)
    return jsonify(ok=True, meta=meta)


RIOT_ID = re.compile(r"^([^#/\\\x00-\x1f\x7f]{3,16})#([A-Za-z0-9]{2,5})$")


@app.get("/api/riot/perfil")
def perfil():
    riot_id = (request.args.get("riot_id") or "").strip()
    regiao = (request.args.get("regiao") or "br").lower()
    m = RIOT_ID.match(riot_id)
    if not m or regiao not in PLATAFORMA:
        return jsonify(erro="Use o formato nome#TAG, por exemplo Nome#BR1."), 400
    nome, tag = m.group(1), m.group(2)
    api = riot()
    try:
        conta = api.conta_por_riot_id(regiao, nome, tag)
        puuid = conta["puuid"]
        filas = api.ranqueadas(regiao, puuid)
        solo = next((f for f in filas if f.get("queueType") == "RANKED_SOLO_5x5"), None)
        partidas = []
        for mid in api.ids_partidas(regiao, puuid, quantidade=5):
            p = api.partida(regiao, mid)
            eu = next((x for x in p["info"]["participants"] if x["puuid"] == puuid), None)
            if not eu:
                continue
            partidas.append({
                "campeao": eu["championName"],
                "rota": eu.get("teamPosition") or "",
                "venceu": bool(eu["win"]),
                "kda": f'{eu["kills"]}/{eu["deaths"]}/{eu["assists"]}',
                "cs": eu["totalMinionsKilled"] + eu["neutralMinionsKilled"],
                "duracao_min": round(p["info"]["gameDuration"] / 60),
                "quando": time.strftime("%d/%m %H:%M", time.localtime(p["info"]["gameCreation"] / 1000)),
            })
        return jsonify(
            riot_id=f'{conta.get("gameName", nome)}#{conta.get("tagLine", tag)}',
            elo=(f'{solo["tier"]} {solo["rank"]} · {solo["leaguePoints"]} PDL · {solo["wins"]}V {solo["losses"]}D' if solo else "Sem ranqueada solo nesta temporada"),
            partidas=partidas,
        )
    except RiotErro as e:
        codigo = e.status if e.status in (401, 403, 404, 429) else 502
        return jsonify(erro=e.mensagem), codigo


if __name__ == "__main__":
    if porta_ocupada(PORTA):
        # No Windows duas cópias conseguem dividir a mesma porta e as respostas se misturam: não deixa abrir a segunda.
        print("=" * 56)
        print(" O CounterPick JÁ ESTÁ ABERTO em http://localhost:%d" % PORTA)
        print(" Use a janela que já está aberta. Se quiser reiniciar,")
        print(" feche a outra janela preta e abra o INICIAR.bat de novo.")
        print("=" * 56)
        raise SystemExit(1)
    k = chave_atual()
    amigos = ler_env(os.path.join(PASTA, ".env")).get("COUNTERPICK_AMIGOS", "0").strip() == "1"
    print("=" * 60)
    print(" CounterPick rodando em http://localhost:%d" % PORTA)
    print(" Chave da Riot:", "configurada" if k.startswith("RGAPI-") else "NÃO configurada (veja LEIA-ME.txt)")
    ts_ip = None
    if amigos:
        ts_ip, ts_nome = tailscale_endereco()
        if ts_ip:
            # Escuta SÓ no endereço do Tailscale (rede privada), nunca na rede de casa nem na internet.
            curto = ts_nome.split(".")[0] if ts_nome else None
            for h in filter(None, (ts_ip, ts_nome, curto)):
                HOSTS_OK.add(f"{h}:{PORTA}")
            ORIGENS_OK.update(f"http://{h}" for h in HOSTS_OK)
            print(" MODO AMIGOS ligado. Seus amigos (no Tailscale) abrem:")
            print(f"    http://{curto or ts_ip}:{PORTA}" + (f"   ou   http://{ts_ip}:{PORTA}" if curto else ""))
        else:
            print(" MODO AMIGOS: o Tailscale não está instalado ou conectado. Só este PC acessa.")
    print(" Para desligar, feche esta janela.")
    print("=" * 60)
    # Atualiza builds/counters sozinho quando sai patch novo (leva alguns minutos, em segundo plano).
    dados.sincronizar_em_segundo_plano()
    if ts_ip:
        from werkzeug.serving import make_server
        srv = make_server(ts_ip, PORTA, app, threaded=True)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    # 127.0.0.1 = este computador. Nunca 0.0.0.0 (que abriria para a rede de casa toda).
    app.run(host="127.0.0.1", port=PORTA, debug=False, threaded=True)
