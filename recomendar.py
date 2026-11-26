"""Motor de recomendação sem IA: só números do OP.GG e das partidas da Riot (quando houver).

A pontuação é uma estimativa de chance de vitória (0..1), somando efeitos pequenos e explicados:
- Força no patch: taxa de vitória do campeão na rota.
- Confronto de lane: contra o oponente direto (ou os prováveis, no draft), com "encolhimento"
  para amostras pequenas (poucas partidas puxam para 50%).
- Time inimigo inteiro:
    * dados reais da Riot (seu campeão contra cada inimigo, qualquer rota) quando houver coleta;
    * leitura da comp (dano físico x mágico, tanques, assassinos, alcance) com regras simples.
- Time aliado: sinergia real do op.gg (taxa de vitória jogando junto) e equilíbrio de dano.
- Draft: risco de levar counter dos inimigos que ainda faltam escolher.
- Conforto: suas partidas e sua taxa de vitória com o campeão (perfil).
Cada efeito que mexe na nota aparece escrito no card.
"""
import json

from dados import conectar, info, norm, patch_oficial, sinergias

K_SUAVE = 250   # partidas "fictícias" a 50% para suavizar confrontos com pouca amostra
K_TIME = 60     # idem para os dados da Riot contra cada inimigo do time
ROTA_MIN = 0.25  # o campeão precisa jogar pelo menos 25% das partidas dele nessa rota
ROTA_EXO_MIN = 0.05  # abaixo disso não há dados confiáveis nem para um pick exótico
EXO_FOLGA = 0.02     # o exótico só aparece se ficar no máximo 2 pontos abaixo do 5º pick
MAIS_OPCOES = 5      # quantos picks extras o botão "Ver mais opções" mostra
ROTA_PT = {"top": "Top", "jungle": "Jungle", "mid": "Mid", "adc": "ADC", "support": "Suporte"}


def pct(x):
    return f"{x * 100:.1f}%".replace(".", ",")


def mil(n):
    return f"{int(n):,}".replace(",", ".")


def pts(x):
    """Efeito em pontos percentuais, com sinal: +0,6 / −0,4."""
    return ("+" if x >= 0 else "−") + f"{abs(x) * 100:.1f}".replace(".", ",")


class Base:
    """Carrega tudo da rota uma vez por pedido (é pouco dado; SQLite responde em milissegundos)."""

    def __init__(self, rota):
        con = conectar()
        self.rota = rota
        self.patch = patch_oficial(info(con, "patch"))
        self.sinc = info(con, "sincronizado_em")
        self.meta = {r["campeao"]: dict(r) for r in con.execute("SELECT * FROM meta WHERE rota=?", (rota,))}
        self.builds = {r["campeao"]: json.loads(r["json"]) for r in con.execute("SELECT campeao, json FROM builds WHERE rota=?", (rota,))}
        self.mu = {}
        for r in con.execute("SELECT fonte, campeao, oponente, play, win FROM confrontos WHERE rota=?", (rota,)):
            a = self.mu.setdefault((r["campeao"], r["oponente"]), [0, 0, set()])
            a[0] += r["play"]; a[1] += r["win"]; a[2].add(r["fonte"])
        self.ap, self.tags = {}, {}
        for r in con.execute("SELECT nome, ap, tags FROM campeoes"):
            self.ap[r["nome"]] = r["ap"]
            self.tags[r["nome"]] = [t for t in (r["tags"] or "").split(",") if t]
        self.todos_meta = {}
        for r in con.execute("SELECT rota, campeao, role_rate FROM meta"):
            self.todos_meta.setdefault(r["campeao"], {})[r["rota"]] = r["role_rate"] or 0
        self.vs_time = {(r["campeao"], r["inimigo"]): (r["play"], r["win"])
                        for r in con.execute("SELECT campeao, inimigo, play, win FROM riot_vs_time WHERE rota=?", (rota,))}
        con.close()

    def confronto(self, a, b):
        """(taxa de A contra B suavizada, partidas, fontes). Usa a linha de A ou o inverso da de B."""
        play = win = 0
        fontes = set()
        if (a, b) in self.mu:
            p, w, f = self.mu[(a, b)]; play += p; win += w; fontes |= f
        elif (b, a) in self.mu:
            p, w, f = self.mu[(b, a)]; play += p; win += p - w; fontes |= f
        if not play:
            return None, 0, fontes
        return (win + 0.5 * K_SUAVE) / (play + K_SUAVE), play, fontes

    def piores(self, c, minimo=300):
        """Confrontos ruins de C na rota: [(oponente, taxa, partidas)]."""
        out = []
        for (a, b), (p, w, _) in self.mu.items():
            if a == c and p >= minimo:
                out.append((b, (w + 0.5 * K_SUAVE) / (p + K_SUAVE), p))
        out.sort(key=lambda x: x[1])
        return out

    def principal(self, c):
        """Classe principal do campeão pelo Data Dragon (Tank, Fighter, Mage, Assassin, Marksman, Support)."""
        t = self.tags.get(c) or []
        return t[0] if t else ""


def risco_counter(base, c):
    """0..1: fração (pesada por popularidade) de oponentes da rota que ganham bem de C."""
    tot = ruim = 0.0
    for op, wr, p in base.piores(c):
        peso = (base.meta.get(op, {}).get("pick_rate") or 0.01)
        tot += peso
        if wr < 0.47:
            ruim += peso * (0.47 - wr) / 0.05
    return min(1.0, ruim / tot) if tot else 0.5


# ---------- leitura da composição ----------
def ler_comp(b, nomes):
    """Resumo do time: quantos de cada tipo e o lado do dano."""
    comp = {"n": len(nomes), "tank": 0, "assassin": 0, "fragil": 0, "ap": 0.0, "longe": 0, "luta": 0}
    for c in nomes:
        t = b.tags.get(c) or []
        p = t[0] if t else ""
        if p == "Tank" or (p == "Fighter" and "Tank" in t):
            comp["tank"] += 1
        if p == "Assassin" or (p == "Fighter" and "Assassin" in t):
            comp["assassin"] += 1
        if p in ("Mage", "Marksman") or (p == "Support" and "Mage" in t):
            comp["fragil"] += 1
        if p in ("Mage", "Marksman"):
            comp["longe"] += 1
        if p in ("Tank", "Fighter"):
            comp["luta"] += 1
        comp["ap"] += b.ap.get(c, 0.5)
    comp["ap"] = comp["ap"] / comp["n"] if comp["n"] else 0.5
    return comp


def texto_comp(cp):
    if not cp["n"]:
        return ""
    lado = "quase todo físico" if cp["ap"] < 0.35 else ("quase todo mágico" if cp["ap"] > 0.65 else "misto")
    partes = [f"dano {lado}"]
    if cp["tank"]:
        partes.append(f"{cp['tank']} tanque{'s' if cp['tank'] > 1 else ''}")
    if cp["assassin"]:
        partes.append(f"{cp['assassin']} assassino{'s' if cp['assassin'] > 1 else ''}")
    if cp["fragil"] >= 3:
        partes.append("vários alvos frágeis")
    return ", ".join(partes)


def efeito_comp(b, c, cp):
    """Regras simples e explicadas de como C se sai contra esse TIPO de time. Retorna [(efeito, motivo)]."""
    if cp["n"] < 2:
        return []
    t = b.tags.get(c) or []
    p = t[0] if t else ""
    out = []
    if cp["fragil"] >= 3 and cp["tank"] == 0 and (p == "Assassin" or "Assassin" in t):
        out.append((0.007, "time inimigo frágil e sem tanque: assassino tira muito proveito"))
    if cp["tank"] >= 2:
        if p in ("Marksman", "Fighter"):
            out.append((0.005, f"inimigo com {cp['tank']} tanques: dano contínuo derrete linha de frente"))
        if p == "Assassin":
            out.append((-0.006, f"inimigo com {cp['tank']} tanques: assassino tem pouco alvo"))
    if cp["assassin"] >= 2:
        if p == "Tank" or (p == "Support" and ("Tank" in t or "Fighter" in t)):
            out.append((0.006, f"inimigo com {cp['assassin']} assassinos: quem aguenta e protege vale mais"))
        if p in ("Marksman", "Mage") and "Tank" not in t and "Fighter" not in t and b.rota in ("mid", "adc"):
            out.append((-0.003, f"inimigo com {cp['assassin']} assassinos: campeão frágil vira alvo"))
    if cp["longe"] >= 3 and (p in ("Tank", "Assassin") or (p == "Fighter" and "Tank" in t)):
        out.append((0.004, "inimigo com muito poke de longe: quem entra rápido na luta pune"))
    if cp["luta"] >= 3 and p == "Mage" and b.rota in ("mid", "support"):
        out.append((0.004, "inimigo com muita linha de frente: mago de controle segura a luta"))
    return out


def efeito_riot_time(b, c, inimigos):
    """Dados reais (coleta Riot BR): C contra cada inimigo do time, qualquer rota."""
    soma = peso = 0.0
    n_total = 0
    for e in inimigos:
        pw = b.vs_time.get((c, e))
        if pw and pw[0] >= 20:
            p, w = pw
            soma += ((w + 0.5 * K_TIME) / (p + K_TIME) - 0.5) * p
            peso += p
            n_total += p
    if not peso:
        return None
    return soma / peso, n_total


def recomendar(rota, modo, inimigos, aliados, pool, perfil, draft=None, meu=None, quantos=5, sinergia=True):
    """inimigos: [{"name","role"}] (lane/full) ou [nomes] (draft). aliados: [{"name","role"}] ou [nomes]."""
    b = Base(rota)
    if not b.meta:
        return {"erro": "Ainda não há dados desta rota. Aguarde a atualização do patch terminar."}
    perfil_d = {norm(c["n"]): c for c in (perfil or [])}
    pool_n = {norm(x) for x in pool or []}
    ali = [a if isinstance(a, dict) else {"name": a, "role": None} for a in aliados or []]
    nomes_ali = [a["name"] for a in ali]
    nomes_ini = [e if isinstance(e, str) else e.get("name") for e in inimigos]

    oponente, possiveis = None, []
    if modo == "draft":
        for e in nomes_ini:
            rr = b.todos_meta.get(e, {}).get(rota, 0)
            outras = max([v for k, v in b.todos_meta.get(e, {}).items() if k != rota] or [0])
            if rr >= 0.25 and rr >= outras * 0.6:
                possiveis.append((e, rr))
    else:
        oponente = next((e.get("name") for e in inimigos if isinstance(e, dict) and e.get("role") == rota), None)

    comp_ini = ler_comp(b, [e for e in nomes_ini if e != oponente] if modo != "lane" else [])
    ap_ali = [b.ap.get(a, 0.5) for a in nomes_ali]
    falta_ap = len(ap_ali) >= 2 and sum(ap_ali) / len(ap_ali) < 0.35
    falta_ad = len(ap_ali) >= 2 and sum(ap_ali) / len(ap_ali) > 0.65

    # sinergia real com cada aliado que tem rota conhecida (op.gg; busca uma vez por patch)
    sin = {}
    if sinergia and modo != "lane":
        for a in ali:
            if a.get("role") and a["role"] != rota:
                d = sinergias(a["role"], a["name"], rota)
                if d:
                    sin[a["name"]] = d

    depois = (draft or {}).get("after", 0)
    usados = set(nomes_ini) | set(nomes_ali)
    # Normais: jogam >= 25% das partidas nesta rota (ou estão no seu pool).
    # Exóticos: jogam só 5% a 25% aqui. Entram na conta, mas só aparecem no card "exótico".
    def eh_exotico(c):
        return (b.meta[c].get("role_rate") or 0) < ROTA_MIN and norm(c) not in pool_n
    candidatos = [c for c, m in b.meta.items() if c in b.builds and c not in usados
                  and ((m.get("role_rate") or 0) >= ROTA_MIN or (norm(c) in pool_n and (m.get("role_rate") or 0) >= 0.05))]
    exoticos = [c for c, m in b.meta.items() if c in b.builds and c not in usados
                and ROTA_EXO_MIN <= (m.get("role_rate") or 0) < ROTA_MIN and norm(c) not in pool_n]
    if meu:
        candidatos, exoticos = [meu], []

    res = []
    for c in candidatos + exoticos:
        m = b.meta.get(c, {})
        forca = m.get("win_rate") or 0.5
        motivos, efeitos = [], []
        lane_wr = amostra = None
        if oponente:
            lane_wr, n, fontes = b.confronto(c, oponente)
            amostra = n
            if lane_wr is not None:
                motivos.append(f"{pct(lane_wr)} de vitória contra {oponente} ({mil(n)} partidas"
                               f"{' · inclui Riot BR' if 'riot' in fontes else ''}{' · amostra pequena' if n < 1000 else ''})")
        elif possiveis:
            soma = peso = 0.0
            partes = []
            for e, rr in possiveis:
                wr, n, _ = b.confronto(c, e)
                if wr is not None:
                    soma += wr * rr; peso += rr
                    partes.append(f"{pct(wr)} vs {e}")
            if peso:
                lane_wr = soma / peso
                motivos.append("Contra os prováveis oponentes de rota: " + ", ".join(partes[:3]))

        # jungle e suporte jogam contra o time todo: o duelo direto pesa menos e a partida pesa mais
        time_todo = rota in ("jungle", "support") and modo != "lane"
        if modo == "lane" and lane_wr is not None:
            score = 0.75 * lane_wr + 0.25 * forca
        elif lane_wr is not None:
            score = (0.35 if time_todo else 0.55) * lane_wr + (0.65 if time_todo else 0.45) * forca
        else:
            score = forca
        if amostra is not None and amostra < 1000:
            score -= 0.008 * (1 - amostra / 1000)
        motivos.append(f"Tier {m.get('tier', '?')} no {ROTA_PT[rota]} neste patch ({pct(forca)} de vitória)")

        if modo != "lane":
            # time inimigo: dados reais primeiro, regras da comp depois
            rt = efeito_riot_time(b, c, [e for e in nomes_ini if e != oponente])
            if rt:
                ef = max(-0.02, min(0.02, rt[0] * 0.6))
                efeitos.append((ef, f"contra este time inimigo (Riot BR, {mil(rt[1])} partidas)"))
            for ef, txt in efeito_comp(b, c, comp_ini):
                efeitos.append((ef, txt))
            # aliados
            for a, d in sin.items():
                if c in d:
                    p_, w_ = d[c]
                    wr_s = (w_ + 0.5 * K_SUAVE) / (p_ + K_SUAVE)
                    ef = max(-0.012, min(0.012, (wr_s - forca) * 0.6))
                    if abs(ef) >= 0.001:
                        efeitos.append((ef, f"com {a}: {pct(w_ / p_)} de vitória juntos, contra {pct(forca)} normalmente "
                                            f"({mil(p_)} partidas, op.gg)"))
            ap = b.ap.get(c, 0.5)
            if falta_ap and ap >= 0.6:
                efeitos.append((0.006, "seu time está quase todo de dano físico: este traz dano mágico"))
            if falta_ad and ap <= 0.4:
                efeitos.append((0.006, "seu time está quase todo de dano mágico: este traz dano físico"))

        risco = risco_counter(b, c)
        if modo == "draft":
            pen = risco * 0.03 * (depois / 5 + (0.4 if not possiveis else 0))
            if pen >= 0.002:
                efeitos.append((-pen, f"risco de levar counter dos {depois} inimigos que ainda vão escolher" if depois
                                else "risco de levar counter"))

        p = perfil_d.get(norm(c))
        if p and p.get("g", 0) >= 3:
            ef = min(p["g"], 60) / 60 * 0.012 + (p.get("wr", 50) - 50) / 100 * 0.02
            efeitos.append((ef, f"você: {p['g']} jogos com {round(p.get('wr', 0))}% de vitória"))

        if time_todo:
            efeitos = [(e * 1.6 if not (t.startswith("você:") or t.startswith("risco")) else e, t) for e, t in efeitos]
        score += sum(e for e, _ in efeitos)
        res.append({"name": c, "score": score, "lane_wr": lane_wr, "risk_val": risco, "pool": norm(c) in pool_n,
                    "amostra": amostra, "exotico": not meu and eh_exotico(c),
                    "why": motivos, "efeitos": sorted(efeitos, key=lambda x: -abs(x[0]))})

    if not oponente and not possiveis and not meu:
        quantos = max(quantos, 5)  # sem oponente direto: mais opções para escolher

    res.sort(key=lambda x: -x["score"])
    exo_res = [r for r in res if r["exotico"]]
    res = [r for r in res if not r["exotico"]]
    if not res:
        return {"erro": "Nenhum campeão desta rota tem dados para essa situação ainda."}
    escolhidos = res[:1] if meu else []
    if not meu:
        do_pool = [r for r in res if r["pool"] and r["score"] >= res[0]["score"] - 0.02
                   and (r["lane_wr"] is None or r["lane_wr"] >= 0.49)]
        escolhidos += do_pool[:2]
        for r in res:
            if len(escolhidos) >= quantos:
                break
            if r not in escolhidos:
                escolhidos.append(r)
        escolhidos.sort(key=lambda x: -x["score"])

    melhor = res[0]["score"] if res else 0.5

    def nivel(r):
        diff = r["score"] - melhor
        return "S" if diff >= -0.004 and r["score"] >= 0.52 else ("A" if diff >= -0.015 else "B")

    def montar_pick(r):
        bd = b.builds.get(r["name"], {})
        tier = nivel(r)
        rk = "baixo" if r["risk_val"] < 0.15 else ("medio" if r["risk_val"] < 0.35 else "alto")
        piores = [f"{o} ({pct(w)})" for o, w, _ in b.piores(r["name"])[:3]]
        return {
            "t": "pick", "name": r["name"], "tier": tier, "offPool": bool(pool_n) and not r["pool"],
            "why": " · ".join(r["why"]),
            "ajustes": [{"efeito": round(e, 4), "texto": t} for e, t in r["efeitos"] if abs(e) >= 0.001],
            "runes": bd.get("runes"), "spells": bd.get("spells"), "max": bd.get("max"), "order": bd.get("order") or [],
            "start": bd.get("start"), "boots": bd.get("boots"), "core": bd.get("core"), "later": (bd.get("later") or [])[:5],
            "buildNote": "Build mais jogada no op.gg neste patch"
                         + (f": {pct(bd['core_wr'])} de vitória em {mil(bd['core_play'])} partidas com esses itens." if bd.get("core_wr") else "."),
            "risk": rk if modo == "draft" else None,
            "riskWhy": ("Leva counter de " + ", ".join(piores)) if piores and modo == "draft" else None,
        }

    picks = [montar_pick(r) for r in escolhidos]

    # Melhor opção do SEU pool nesta partida, com o nível dito com sinceridade.
    # Se ela já está entre os 5, ganha um selo na lista; se não, vira um card próprio.
    melhor_pool = None
    nomes_esc = {r["name"] for r in escolhidos}
    if not meu and pool_n:
        meus_todos = [r for r in res if r["pool"]]
        if meus_todos:
            mp = meus_todos[0]  # res já está ordenado do melhor para o pior
            posicao = res.index(mp) + 1
            if mp["name"] in nomes_esc:
                for p in picks:
                    if p["name"] == mp["name"]:
                        p["melhorDoPool"] = True
            else:
                card = montar_pick(mp)
                t = card["tier"]
                card["posicao"] = posicao
                card["nivelTexto"] = {
                    "S": "Nível S: é uma das melhores escolhas desta partida.",
                    "A": "Nível A: boa escolha, perto das melhores. Se você tem mais confiança nele, vá sem medo.",
                    "B": "Nível B: dá para jogar, mas não é o melhor. As opções da lista acima ganham mais nesta partida.",
                }[t]
                card["diferenca"] = round(melhor - mp["score"], 4)
                melhor_pool = card

    # Card vermelho (sempre que der): "esse você não usa agora".
    # 1º o pior do SEU pool, se estiver bem abaixo; senão, um campeão popular nesta rota que vai mal nesta partida.
    nao_vale = None
    if not meu and escolhidos:
        ja_mostrados = nomes_esc | ({melhor_pool["name"]} if melhor_pool else set())
        corte = escolhidos[-1]["score"] - 0.005
        pior, do_pool = None, False
        meus = [r for r in res if r["pool"] and r["name"] not in ja_mostrados]
        if meus:
            p_ = min(meus, key=lambda r: r["score"])
            if p_["score"] < corte:
                pior, do_pool = p_, True
        if pior is None:
            # populares = os 15 mais escolhidos nesta rota; dentre eles, o que pior se sai aqui
            populares = sorted((r for r in res if r["name"] not in ja_mostrados and not r["pool"]),
                               key=lambda r: -(b.meta.get(r["name"], {}).get("pick_rate") or 0))[:15]
            p_ = min(populares, key=lambda r: r["score"], default=None)
            if p_ and p_["score"] < corte:
                pior = p_
        if pior:
            if oponente and pior["lane_wr"] is not None and pior["lane_wr"] < 0.49:
                motivo = f"perde a rota: {pct(pior['lane_wr'])} de vitória contra {oponente}"
            else:
                ruins = [t for e, t in pior["efeitos"] if e < 0]
                motivo = ruins[0] if ruins else "fica abaixo das outras opções nesta partida"
            pr = b.meta.get(pior["name"], {}).get("pick_rate") or 0
            nao_vale = {"name": pior["name"], "doPool": do_pool, "motivo": motivo[0].upper() + motivo[1:],
                        "popular": None if do_pool else f"Um dos mais escolhidos no {ROTA_PT[rota]} ({pct(pr)} das partidas), mas não nesta.",
                        "posicao": res.index(pior) + 1, "total": len(res),
                        "why": " · ".join(pior["why"]),
                        "ajustes": [{"efeito": round(e, 4), "texto": t} for e, t in pior["efeitos"] if abs(e) >= 0.001],
                        "diferenca": round(melhor - pior["score"], 4)}

    # Card "exótico": alguém que quase não joga nesta rota, mas que encaixa contra este time.
    # Só aparece se ficar perto dos 5 melhores; com pouca amostra vira "aposta".
    exotico = None
    if not meu and exo_res and escolhidos:
        e = exo_res[0]
        bom_na_rota = e["lane_wr"] is None or e["lane_wr"] >= 0.50
        if bom_na_rota and e["score"] >= escolhidos[-1]["score"] - EXO_FOLGA:
            card = montar_pick(e)
            rr = b.meta.get(e["name"], {}).get("role_rate") or 0
            aposta = e["amostra"] is not None and e["amostra"] < 1000
            if aposta:
                base = f"É uma APOSTA: só {mil(e['amostra'])} partidas neste confronto, pode surpreender ou não."
            elif e["amostra"]:
                base = "Fora do comum, mas os números deste confronto sustentam."
            else:
                base = "Fora do comum: entra pela força dele nessa rota e pelo encaixe contra este time."
            card["exoticoTexto"] = (f"Só {pct(rr)} das partidas de {e['name']} são no {ROTA_PT[rota]}. {base} "
                                    "Quem leva ele nessa rota costuma dominar o campeão: vale mais se você já joga com ele.")
            card["aposta"] = aposta
            card["posicao"] = sum(1 for r in res if r["score"] > e["score"]) + 1
            exotico = card

    # "Ver mais opções": do 6º ao 10º, sem repetir o que já está na tela
    mais = []
    if not meu:
        ja = nomes_esc | {x["name"] for x in (melhor_pool, nao_vale) if x}
        for r in res:
            if len(mais) >= MAIS_OPCOES:
                break
            if r["name"] not in ja:
                card = montar_pick(r)
                card["posicao"] = res.index(r) + 1
                mais.append(card)

    evite = []
    if oponente and not meu:
        ruins = []
        for c in candidatos:
            wr, n, _ = b.confronto(c, oponente)
            if wr is not None and n >= 300:
                ruins.append((wr, c, n))
        ruins.sort()
        evite = [{"name": c, "why": f"só {pct(wr)} de vitória contra {oponente} ({mil(n)} partidas)."} for wr, c, n in ruins[:2]]

    leitura = texto_comp(comp_ini)
    if meu:
        resumo = f"Avaliação de {meu}" + (f" contra {oponente}" if oponente else "") + f" (patch {b.patch})."
    elif modo == "draft":
        resumo = ("Seu oponente de rota ainda não saiu" if not possiveis
                  else "Prováveis oponentes de rota: " + ", ".join(e for e, _ in possiveis))
        resumo += "." + ("" if not depois else (" Depois de você ainda falta 1 inimigo escolher." if depois == 1
                                                else f" Depois de você ainda faltam {depois} inimigos escolherem."))
    elif oponente:
        resumo = f"Comparei {len(candidatos)} campeões de {ROTA_PT[rota]} contra {oponente} (patch {b.patch})."
    else:
        resumo = (f"Sem o seu oponente de rota, mostro {len(picks)} opções que se dão melhor contra o resto do time. "
                  f"Preencha o campo vermelho para counters mais precisos.")
    if leitura and modo != "lane" and not meu:
        resumo += f" Time inimigo: {leitura}."
    if sin and not meu:
        resumo += " Sinergia com " + ", ".join(sin) + " considerada."
    out = {"summary": resumo, "picks": picks, "avoid": evite, "melhorPool": melhor_pool, "naoVale": nao_vale,
           "exotico": exotico, "mais": mais, "patch": b.patch, "sincronizado_em": b.sinc}
    if meu:
        melhor_geral = recomendar(rota, modo, inimigos, aliados, pool, perfil, draft, None, quantos=1, sinergia=sinergia)
        r0 = res[0] if res else None
        out["avaliacao"] = avaliar(b, meu, oponente, possiveis, perfil_d, depois, modo, melhor_geral, r0)
    return out


def avaliar(b, meu, oponente, possiveis, perfil, depois, modo, melhor_geral, r0=None):
    """Chance de vitória estimada da SUA escolha, com o porquê de cada parte do número."""
    m = b.meta.get(meu, {})
    patch_wr = m.get("win_rate")
    partes, alertas = [], []
    base = None
    if oponente:
        wr, n, _ = b.confronto(meu, oponente)
        if wr is not None:
            base = wr
            partes.append(f"Contra {oponente} na rota: {pct(wr)} em {mil(n)} partidas" + (" (amostra pequena)" if n < 1000 else ""))
        else:
            alertas.append(f"Não há partidas suficientes de {meu} contra {oponente} nesta rota.")
    elif possiveis:
        soma = peso = 0.0
        for e, rr in possiveis:
            wr, n, _ = b.confronto(meu, e)
            if wr is not None:
                soma += wr * rr; peso += rr
                partes.append(f"Se pegar {e} na rota: {pct(wr)} ({mil(n)} partidas)")
        if peso:
            base = soma / peso
    if patch_wr:
        partes.append(f"{meu} no {ROTA_PT[b.rota]} neste patch: {pct(patch_wr)} de vitória (tier {m.get('tier', '?')})")
        if base is None:
            base = patch_wr
    elif not m:
        alertas.append(f"{meu} é pouco jogado no {ROTA_PT[b.rota]}: quase não há dados dele nessa rota.")
    if base is None:
        base = 0.5

    # efeitos da partida (time inimigo e aliados), já calculados no ranking; o histórico é tratado à parte
    situ = 0.0
    if r0:
        for e, t in r0["efeitos"]:
            if t.startswith("você:") or t.startswith("risco"):
                continue
            situ += e
            partes.append(f"{t[0].upper() + t[1:]} ({pts(e)})")
    situ = max(-0.03, min(0.03, situ))

    ajuste = 0.0
    p = perfil.get(norm(meu))
    if p and p.get("g", 0) >= 5:
        g, wr_p = p["g"], (p.get("wr") or 50) / 100
        suave = (wr_p * g + 0.5 * 20) / (g + 20)
        ajuste = max(-0.04, min(0.04, (suave - 0.5) * 0.5))
        partes.append(f"Seu histórico: {g} jogos com {round(wr_p * 100)}% de vitória ({pts(ajuste)} na estimativa)")
    elif p:
        partes.append(f"Seu histórico: só {p['g']} {'jogo' if p['g'] == 1 else 'jogos'} com {meu}, ainda não entra na conta.")

    chance = max(0.35, min(0.65, base + situ + ajuste))

    piores = [(o, w) for o, w, n in b.piores(meu) if w < 0.48][:3]
    if (modo == "draft" and depois) or (not oponente and not possiveis):
        if piores:
            alertas.append("Cuidado se o inimigo pegar " + ", ".join(f"{o} ({pct(w)})" for o, w in piores) + " na sua rota.")

    if chance >= 0.53:
        veredito, tom = "Boa escolha", "bom"
    elif chance >= 0.49:
        veredito, tom = "Equilibrado", "medio"
    else:
        veredito, tom = "Arriscado", "ruim"
    sugestao = None
    if melhor_geral and melhor_geral.get("picks"):
        alt = melhor_geral["picks"][0]
        if alt["name"] != meu:
            sugestao = alt["name"]
            if tom == "ruim":
                alertas.append(f"Opção melhor nesta situação: {alt['name']}.")
    return {"chance": round(chance, 3), "veredito": veredito, "tom": tom, "partes": partes, "alertas": alertas,
            "sugestao": sugestao, "aviso": "Estimativa com base em estatísticas de muitas partidas, não uma garantia: o resultado depende de como o jogo é jogado."}
