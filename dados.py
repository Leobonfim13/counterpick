"""Banco local (SQLite) + sincronização por patch com Data Dragon (Riot) e OP.GG."""
import json
import os
import sqlite3
import threading
import time
import unicodedata
import urllib.request

from opgg import OpggMCP, chave_opgg

PASTA = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(PASTA, "counterpick.db")
SITE_DATA = os.path.join(PASTA, "site", "data")
ROTAS = ["top", "jungle", "mid", "adc", "support"]
STAT_MODS = {5008: "Força Adaptativa", 5005: "Velocidade de Ataque", 5007: "Aceleração de Habilidade",
             5010: "Velocidade de Movimento", 5001: "Escalamento de Vida", 5011: "Vida",
             5013: "Tenacidade e Resistência a Lentidão"}

opgg = OpggMCP()
progresso = {"rodando": False, "feito": 0, "total": 0, "etapa": "", "erro": "", "inicio": 0}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).lower()
    return "".join(ch for ch in s if ch.isalnum())


def conectar():
    con = sqlite3.connect(BANCO, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS info(chave TEXT PRIMARY KEY, valor TEXT);
    CREATE TABLE IF NOT EXISTS campeoes(id TEXT PRIMARY KEY, nome TEXT, ap REAL, tags TEXT);
    CREATE TABLE IF NOT EXISTS meta(rota TEXT, campeao TEXT, tier INT, rank INT, win_rate REAL, pick_rate REAL,
        ban_rate REAL, role_rate REAL, play INT, PRIMARY KEY(rota, campeao));
    CREATE TABLE IF NOT EXISTS builds(rota TEXT, campeao TEXT, json TEXT, PRIMARY KEY(rota, campeao));
    CREATE TABLE IF NOT EXISTS confrontos(fonte TEXT, rota TEXT, campeao TEXT, oponente TEXT, play INT, win INT,
        PRIMARY KEY(fonte, rota, campeao, oponente));
    CREATE TABLE IF NOT EXISTS riot_partidas(match_id TEXT PRIMARY KEY, patch TEXT, coletada_em INT);
    CREATE TABLE IF NOT EXISTS sinergias(patch TEXT, rota_aliado TEXT, aliado TEXT, rota TEXT, campeao TEXT, play INT, win INT,
        PRIMARY KEY(patch, rota_aliado, aliado, rota, campeao));
    CREATE TABLE IF NOT EXISTS sinergias_buscadas(patch TEXT, rota_aliado TEXT, aliado TEXT, rota TEXT,
        PRIMARY KEY(patch, rota_aliado, aliado, rota));
    CREATE TABLE IF NOT EXISTS riot_vs_time(rota TEXT, campeao TEXT, inimigo TEXT, play INT, win INT,
        PRIMARY KEY(rota, campeao, inimigo));
    """)
    colunas = {r[1] for r in con.execute("PRAGMA table_info(riot_partidas)")}
    if "elo" not in colunas:  # bancos criados antes da coleta de todos os elos
        con.execute("ALTER TABLE riot_partidas ADD COLUMN elo TEXT")
        con.execute("UPDATE riot_partidas SET elo='MASTER+' WHERE elo IS NULL")
        con.commit()
    return con


def info(con, chave, valor=None):
    if valor is None:
        r = con.execute("SELECT valor FROM info WHERE chave=?", (chave,)).fetchone()
        return r["valor"] if r else None
    con.execute("INSERT OR REPLACE INTO info VALUES(?,?)", (chave, str(valor)))


def baixar_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "CounterPick-local"}), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def versao_atual():
    return baixar_json("https://ddragon.leagueoflegends.com/api/versions.json")[0]


def patch_de(versao):
    return ".".join(versao.split(".")[:2])


def patch_oficial(patch):
    """A Riot numera internamente 16.23, mas o nome público do patch é 26.23 (ano + número)."""
    try:
        a, b = patch.split(".")[:2]
        return f"{int(a) + 10}.{b}" if int(a) >= 15 else patch
    except (AttributeError, ValueError):
        return patch


# ---------- Data Dragon: campeões, itens e runas oficiais ----------
def atualizar_ddragon(con, v):
    cdn = f"https://ddragon.leagueoflegends.com/cdn/{v}"
    champs = baixar_json(f"{cdn}/data/en_US/champion.json")["data"]
    con.execute("DELETE FROM campeoes")
    for c in champs.values():
        at, mg = c["info"]["attack"], c["info"]["magic"]
        con.execute("INSERT INTO campeoes VALUES(?,?,?,?)", (c["id"], c["name"], mg / max(1, at + mg), ",".join(c["tags"])))

    itens = baixar_json(f"{cdn}/data/pt_BR/item.json")["data"]
    lista, vistos = [], set()
    for iid in sorted(itens, key=int):
        i = itens[iid]
        if not i.get("maps", {}).get("11") or not i["gold"]["purchasable"] or i["gold"]["total"] <= 0:
            continue
        if i.get("requiredChampion") or i.get("requiredAlly") or "Trinket" in i.get("tags", []):
            continue
        tags = i.get("tags", [])
        if "Boots" in tags:
            if not i.get("from"):
                continue
            k = "boots"
        elif not i.get("into") and i["gold"]["total"] >= 2200:
            k = "full"
        elif i["gold"]["total"] <= 500 and not i.get("from") and ("Doran" in i["name"] or i["name"] in (
                "Poção de Vida", "Poção com Refil", "Lacre Sombrio", "Abatedora", "Atlas Mundial",
                "Filhote de Garrabrasa", "Cria de Andabrisas", "Broto de Esmagamusgo", "Lágrima da Deusa")):
            k = "start"
        else:
            continue
        if i["name"] in vistos:
            continue
        vistos.add(i["name"])
        lista.append({"id": iid, "n": i["name"], "k": k})
    # Itens que se transformam sozinhos não se compram: troca pelo item que você compra.
    # (O Data Dragon não liga um ao outro, então a lista é fixa.)
    compravel = {x["id"] for x in lista}
    transforma = {k: v for k, v in {"3042": "3004", "3040": "3003", "3121": "3119"}.items() if v in compravel}
    for iid, i in itens.items():
        if iid not in compravel and iid not in transforma and i.get("from"):
            pais = [p for p in i["from"] if p in compravel]
            if len(pais) == 1:
                transforma[iid] = pais[0]
    pt = baixar_json(f"{cdn}/data/pt_BR/champion.json")["data"]
    info(con, "nomes_pt", json.dumps({norm(c["name"]): champs[k]["name"] for k, c in pt.items() if k in champs}, ensure_ascii=False))

    runas = baixar_json(f"{cdn}/data/pt_BR/runesReforged.json")
    arvores = [{"n": t["name"], "k": t["key"], "slots": [[{"n": r["name"], "k": r["key"]} for r in s["runes"]] for s in t["slots"]]} for t in runas]
    icones_runas = {t["key"]: t["icon"] for t in runas}
    for t in runas:
        for s in t["slots"]:
            for r in s["runes"]:
                icones_runas[r["key"]] = r["icon"]

    os.makedirs(SITE_DATA, exist_ok=True)
    with open(os.path.join(SITE_DATA, "items.json"), "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(SITE_DATA, "runes.json"), "w", encoding="utf-8") as f:
        json.dump(arvores, f, ensure_ascii=False, separators=(",", ":"))
    # ícones novos (campeões, itens, runas) que ainda não existem na pasta
    ic = os.path.join(PASTA, "site", "icons")
    faltando = [(f"{cdn}/img/item/{x['id']}.png", os.path.join(ic, "items", x["id"] + ".png")) for x in lista]
    faltando += [(f"https://ddragon.leagueoflegends.com/cdn/img/{p}", os.path.join(ic, "runes", k + ".png")) for k, p in icones_runas.items()]
    faltando += [(f"{cdn}/img/champion/{c['id']}.png", os.path.join(ic, c["id"] + ".png")) for c in champs.values()]
    for url, destino in faltando:
        alt = destino[:-4] + ".jpg"
        if os.path.exists(destino) or os.path.exists(alt):
            continue
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        try:
            with urllib.request.urlopen(url, timeout=30) as r, open(destino, "wb") as f:
                f.write(r.read())
        except Exception:
            pass
    try:
        baixar_feiticos(v)
    except Exception:
        pass  # sem os ícones dos feitiços o site continua funcionando (mostra só o nome)
    info(con, "itens_json", json.dumps({x["id"]: x for x in lista}, ensure_ascii=False))
    info(con, "transforma", json.dumps(transforma))
    con.commit()


def baixar_feiticos(v):
    """Feitiços de invocador oficiais do Summoner's Rift (nome pt_BR + ícone)."""
    cdn = f"https://ddragon.leagueoflegends.com/cdn/{v}"
    d = baixar_json(f"{cdn}/data/pt_BR/summoner.json")["data"]
    lista = [{"n": s["name"], "k": k} for k, s in d.items() if "CLASSIC" in s.get("modes", [])]
    os.makedirs(SITE_DATA, exist_ok=True)
    with open(os.path.join(SITE_DATA, "spells.json"), "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, separators=(",", ":"))
    pasta = os.path.join(PASTA, "site", "icons", "spells")
    os.makedirs(pasta, exist_ok=True)
    for s in lista:
        destino = os.path.join(pasta, s["k"] + ".png")
        if not os.path.exists(destino):
            with urllib.request.urlopen(f"{cdn}/img/spell/{s['k']}.png", timeout=30) as r, open(destino, "wb") as f:
                f.write(r.read())
    return lista


def mapa_nomes(con):
    """nome normalizado -> nome oficial (en_US), aceitando variações (pt_BR, sem acento)."""
    m = {}
    for r in con.execute("SELECT id, nome FROM campeoes"):
        m[norm(r["nome"])] = r["nome"]
        m[norm(r["id"])] = r["nome"]
    try:
        m.update(json.loads(info(con, "nomes_pt") or "{}"))
    except ValueError:
        pass
    extra = {"nunuewillump": "Nunu & Willump", "nunu": "Nunu & Willump", "renata": "Renata Glasc", "monkeyking": "Wukong"}
    for k, v in extra.items():
        if norm(v) in m:
            m[k] = m[norm(v)]
    return m


# ---------- normaliza a build do OP.GG ----------
def montar_build(d, itens, transforma):
    def item_ok(iid, kinds):
        iid = str(iid)
        iid = transforma.get(iid, iid)
        x = itens.get(iid)
        return x["n"] if x and x["k"] in kinds else None

    def primeiro(lista):
        return lista[0] if isinstance(lista, list) and lista else (lista if isinstance(lista, dict) else {})

    r = primeiro(d.get("runes"))
    sp = primeiro(d.get("summoner_spells"))
    sk = primeiro(d.get("skill_masteries"))
    ordem = [str(x).upper() for x in (primeiro(d.get("skills")).get("order") or []) if str(x).upper() in ("Q", "W", "E", "R")]
    st = primeiro(d.get("starter_items"))
    bo = primeiro(d.get("boots"))
    co = primeiro(d.get("core_items"))
    core = []
    for i in co.get("ids", []):
        n = item_ok(i, ("full", "boots"))
        if n and n not in core:
            core.append(n)
    tardios = []
    for grupo in ("last_items", "fourth_items", "fifth_items", "sixth_items"):
        for x in d.get(grupo) or []:
            for i in x.get("ids", []):
                n = item_ok(i, ("full",))
                if n and n not in core and n not in tardios:
                    tardios.append(n)
    shards = [STAT_MODS.get(int(s), "") for s in r.get("stat_mod_ids", []) if str(s).isdigit()]
    return {
        "runes": {"primary": r.get("primary_page_name"), "keystone": (r.get("primary_rune_names") or [None])[0],
                  "p": (r.get("primary_rune_names") or [])[1:4], "secondary": r.get("secondary_page_name"),
                  "s": (r.get("secondary_rune_names") or [])[:2], "shards": [s for s in shards if s]},
        "runes_wr": round(r["win"] / r["play"], 3) if r.get("play") else None,
        "spells": sp.get("ids_names", []),
        "max": " > ".join(sk.get("ids", [])),
        "order": ordem,  # habilidade upada em cada nível (1..15/18), a mais jogada no op.gg
        "start": [n for n in (item_ok(i, ("start", "full")) for i in st.get("ids", [])) if n],
        "boots": item_ok((bo.get("ids") or [0])[0], ("boots",)),
        "core": core[:3],
        "core_wr": round(co["win"] / co["play"], 3) if co.get("play") else None,
        "core_play": co.get("play"),
        "later": tardios[:5],
    }


# ---------- sincronização completa (uma vez por patch) ----------
def sincronizar(forcar=False):
    if progresso["rodando"]:
        return
    progresso.update(rodando=True, feito=0, total=0, etapa="Conferindo versão do jogo…", erro="", inicio=time.time())
    con = conectar()
    try:
        v = versao_atual()
        patch = patch_de(v)
        if not forcar and info(con, "patch") == patch and info(con, "sincronizado_em"):
            progresso.update(etapa="Dados já estão no patch atual.")
            return
        progresso["etapa"] = "Baixando itens, runas e campeões oficiais (Riot)…"
        atualizar_ddragon(con, v)
        itens = json.loads(info(con, "itens_json"))
        transforma = json.loads(info(con, "transforma"))
        nomes = mapa_nomes(con)

        progresso["etapa"] = "Baixando a força de cada campeão por rota (OP.GG)…"
        meta = opgg.meta_por_rota()["data"]["positions"]
        con.execute("DELETE FROM meta")
        alvo = []
        for rota in ROTAS:
            for x in meta.get(rota) or []:
                nome = nomes.get(norm(x.get("champion")))
                if not nome:
                    continue
                con.execute("INSERT OR REPLACE INTO meta VALUES(?,?,?,?,?,?,?,?,?)",
                            (rota, nome, x.get("tier"), x.get("rank"), x.get("win_rate"), x.get("pick_rate"),
                             x.get("ban_rate"), x.get("role_rate"), x.get("play")))
                if (x.get("role_rate") or 0) >= 0.08 and (x.get("play") or 0) >= 800:
                    alvo.append((rota, nome))
        con.commit()

        progresso.update(total=len(alvo), etapa="Baixando builds e confrontos de cada campeão (OP.GG)…")
        topo = {r: [n for (rr, n) in alvo if rr == r] for r in ROTAS}
        falhas = 0
        for rota, nome in alvo:
            oponente = next((o for o in topo[rota] if o != nome), nome)
            try:
                g = opgg.confronto(rota, chave_opgg(nome), chave_opgg(oponente))
                d = g.get("data") or {}
                b = montar_build(d, itens, transforma)
                con.execute("INSERT OR REPLACE INTO builds VALUES(?,?,?)", (rota, nome, json.dumps(b, ensure_ascii=False)))
                con.execute("DELETE FROM confrontos WHERE fonte='opgg' AND rota=? AND campeao=?", (rota, nome))
                for c in d.get("counters") or []:
                    op = nomes.get(norm(c.get("champion_name")))
                    if op and c.get("play"):
                        con.execute("INSERT OR REPLACE INTO confrontos VALUES('opgg',?,?,?,?,?)", (rota, nome, op, c["play"], c["win"]))
                con.commit()
            except Exception:
                falhas += 1
            progresso["feito"] += 1
        info(con, "patch", patch)
        info(con, "versao", v)
        info(con, "sincronizado_em", time.strftime("%d/%m/%Y %H:%M"))
        info(con, "falhas_sync", falhas)
        con.commit()
        progresso["etapa"] = f"Pronto: {len(alvo) - falhas} campeões/rotas atualizados no patch {patch}."
    except Exception as e:
        progresso["erro"] = f"Falha ao atualizar: {e}"
    finally:
        progresso["rodando"] = False
        con.close()


def completar_ordem(rota, campeao):
    """Builds baixadas antes desta versão não têm a ordem nível a nível: busca uma vez no OP.GG e guarda."""
    con = conectar()
    try:
        r = con.execute("SELECT json FROM builds WHERE rota=? AND campeao=?", (rota, campeao)).fetchone()
        if not r:
            return None
        b = json.loads(r["json"])
        if b.get("order"):
            return b
        outro = con.execute("SELECT campeao FROM meta WHERE rota=? AND campeao<>? ORDER BY rank LIMIT 1", (rota, campeao)).fetchone()
        g = opgg.confronto(rota, chave_opgg(campeao), chave_opgg(outro["campeao"] if outro else campeao))
        itens = json.loads(info(con, "itens_json")); transforma = json.loads(info(con, "transforma"))
        novo = montar_build(g.get("data") or {}, itens, transforma)
        b["order"] = novo.get("order") or []
        if not b.get("max"):
            b["max"] = novo.get("max")
        con.execute("UPDATE builds SET json=? WHERE rota=? AND campeao=?", (json.dumps(b, ensure_ascii=False), rota, campeao))
        con.commit()
        return b
    finally:
        con.close()


def sinergias(rota_aliado, aliado, rota):
    """Campeões da `rota` que mais jogam junto com `aliado` (op.gg): {campeao: (play, win)}.
    Busca uma vez por patch e guarda; depois responde na hora."""
    con = conectar()
    try:
        patch = info(con, "patch") or ""
        ja = con.execute("SELECT 1 FROM sinergias_buscadas WHERE patch=? AND rota_aliado=? AND aliado=? AND rota=?",
                         (patch, rota_aliado, aliado, rota)).fetchone()
        if not ja:
            nomes = mapa_nomes(con)
            try:
                r = opgg.chamar("lol_get_champion_synergies", {
                    "champion": chave_opgg(aliado), "my_position": rota_aliado, "synergy_position": rota, "lang": "pt_BR",
                    "desired_output_fields": ["data.synergies[].{synergy_champion_name,play,win}"]})
                for s in ((r or {}).get("data") or {}).get("synergies") or []:
                    n = nomes.get(norm(s.get("synergy_champion_name")))
                    if n and s.get("play"):
                        con.execute("INSERT OR REPLACE INTO sinergias VALUES(?,?,?,?,?,?,?)",
                                    (patch, rota_aliado, aliado, rota, n, s["play"], s["win"]))
            except Exception as e:
                if "HTTP" in str(e) or "conexão" in str(e):
                    return {}  # sem internet / op.gg fora: segue sem sinergia e tenta de novo na próxima vez
                # combinação que o op.gg não tem (campeão raro na rota): marca para não perguntar de novo
            con.execute("INSERT OR REPLACE INTO sinergias_buscadas VALUES(?,?,?,?)", (patch, rota_aliado, aliado, rota))
            con.commit()
        return {r["campeao"]: (r["play"], r["win"]) for r in con.execute(
            "SELECT campeao, play, win FROM sinergias WHERE patch=? AND rota_aliado=? AND aliado=? AND rota=?",
            (patch, rota_aliado, aliado, rota))}
    finally:
        con.close()


def sincronizar_em_segundo_plano(forcar=False):
    threading.Thread(target=sincronizar, args=(forcar,), daemon=True).start()
