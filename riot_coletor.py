"""Fase 2: coleta partidas ranqueadas de todos os elos (prioridade Ferro–Platina) do servidor BR direto da API da Riot
e soma os confrontos de rota no banco (fonte 'riot'), junto com os do OP.GG.

Uso pelo terminal:   python riot_coletor.py --partidas 200
Ou pelo site (modo local): botão "Coletar partidas da Riot".
Com a chave pessoal (100 pedidos a cada 2 min) dá ~20-25 partidas por minuto.
"""
import argparse
import random
import threading
import time

from dados import conectar, info, mapa_nomes, norm
from riot import RiotAPI, RiotErro

POSICAO = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "mid", "BOTTOM": "adc", "UTILITY": "support"}
progresso = {"rodando": False, "partidas": 0, "meta": 0, "etapa": "", "erro": "", "pular": 0, "parar": False, "por_elo": {}}


def registrar_partida(con, nomes, partida, patch, elo=None):
    """Grava os 5 confrontos de rota de uma partida. Devolve True se foi usada."""
    info_p = partida.get("info") or {}
    mid = (partida.get("metadata") or {}).get("matchId")
    if not mid or info_p.get("queueId") != 420:
        return False
    if not str(info_p.get("gameVersion", "")).startswith(patch + "."):
        return False
    if info_p.get("gameDuration", 0) < 15 * 60:  # remakes e rendições muito cedo distorcem
        return False
    if con.execute("SELECT 1 FROM riot_partidas WHERE match_id=?", (mid,)).fetchone():
        return False
    por_rota = {}
    for p in info_p.get("participants") or []:
        rota = POSICAO.get(p.get("teamPosition") or "")
        nome = nomes.get(norm(p.get("championName")))
        if rota and nome:
            por_rota.setdefault(rota, {})[p.get("teamId")] = (nome, bool(p.get("win")))
    # seu campeão contra CADA inimigo do time (qualquer rota): é o que torna a recomendação situacional
    times_p = {}
    for p in info_p.get("participants") or []:
        nome = nomes.get(norm(p.get("championName")))
        if nome:
            times_p.setdefault(p.get("teamId"), []).append((POSICAO.get(p.get("teamPosition") or ""), nome, bool(p.get("win"))))
    if 100 in times_p and 200 in times_p:
        for meu_t, outro_t in ((100, 200), (200, 100)):
            for rota, nome, venceu in times_p[meu_t]:
                if not rota:
                    continue
                for _, inimigo, _ in times_p[outro_t]:
                    con.execute("""INSERT INTO riot_vs_time VALUES(?,?,?,1,?)
                                   ON CONFLICT(rota, campeao, inimigo) DO UPDATE SET play=play+1, win=win+excluded.win""",
                                (rota, nome, inimigo, 1 if venceu else 0))
    usados = 0
    for rota, times in por_rota.items():
        if 100 in times and 200 in times:
            (a, wa), (b, wb) = times[100], times[200]
            for x, y, w in ((a, b, wa), (b, a, wb)):
                con.execute("""INSERT INTO confrontos VALUES('riot',?,?,?,1,?)
                               ON CONFLICT(fonte, rota, campeao, oponente) DO UPDATE SET play=play+1, win=win+excluded.win""",
                            (rota, x, y, 1 if w else 0))
            usados += 1
    con.execute("INSERT INTO riot_partidas(match_id, patch, coletada_em, elo) VALUES(?,?,?,?)", (mid, patch, int(time.time()), elo))
    con.commit()
    return usados > 0


ELOS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER+"]
ELO_PT = {"IRON": "Ferro", "BRONZE": "Bronze", "SILVER": "Prata", "GOLD": "Ouro", "PLATINUM": "Platina",
          "EMERALD": "Esmeralda", "DIAMOND": "Diamante", "MASTER+": "Mestre+"}
# Quanto de cada coleta vai para cada elo. Prioridade para Ferro–Platina (onde jogam os usuários):
# 75% do Ferro à Platina, 25% do Esmeralda para cima.
COTA = {"IRON": 0.15, "BRONZE": 0.15, "SILVER": 0.15, "GOLD": 0.15, "PLATINUM": 0.15,
        "EMERALD": 0.10, "DIAMOND": 0.08, "MASTER+": 0.07}
RECARGAS = 4  # quantas páginas extras de jogadores buscar por elo quando a lista acaba


def buscar_jogadores(api, regiao, tier):
    """Uma página de jogadores do elo (divisão e página sorteadas), embaralhada."""
    try:
        if tier == "MASTER+":
            lista = []
            for nivel in ("challenger", "grandmaster", "master"):
                lista += api.liga_elite(regiao, nivel).get("entries", [])
        else:
            lista = api.jogadores_do_elo(regiao, tier, random.choice(["I", "II", "III", "IV"]), random.randint(1, 3))
    except RiotErro:
        lista = []
    puuids = [e["puuid"] for e in lista if e.get("puuid")]
    random.shuffle(puuids)
    return puuids[:150]


def jogadores_por_elo(api, regiao):
    """Uma amostra de jogadores de cada elo, do Ferro ao Desafiante."""
    return {tier: buscar_jogadores(api, regiao, tier) for tier in ELOS}


def proximo_elo(feitas, por_elo, esgotados):
    """O elo mais atrasado em relação à cota (ex.: Ouro com 5% quando a cota é 15% vem primeiro)."""
    total = sum(feitas.values()) + 1
    abertos = [t for t in ELOS if t not in esgotados]
    if not abertos:
        return None
    return max(abertos, key=lambda t: COTA[t] * total - feitas.get(t, 0))


def coletar(chave, meta=200, regiao="br", dias=14, por_jogador=5):
    """Coleta por cotas de elo (ver COTA): sempre busca o elo mais atrasado. Jogador de elo baixo
    joga menos, então ele precisa de mais jogadores para render as mesmas partidas — o que a cota resolve.
    Poucas partidas por jogador para variar bastante."""
    if progresso["rodando"]:
        return
    progresso.update(rodando=True, partidas=0, meta=meta, etapa="Buscando jogadores de todos os elos…", erro="", pular=0, parar=False,
                     por_elo={})
    con = conectar()
    try:
        api = RiotAPI(chave)
        patch = info(con, "patch")
        if not patch:
            raise RiotErro(0, "Atualize os dados do patch antes de coletar.")
        nomes = mapa_nomes(con)
        por_elo = jogadores_por_elo(api, regiao)
        desde = time.time() - dias * 86400
        progresso["etapa"] = f"Lendo partidas de todos os elos (patch {patch})…"
        feitas, esgotados, recargas = {}, set(), {}
        while progresso["partidas"] < meta and not progresso["parar"]:
            tier = proximo_elo(feitas, por_elo, esgotados)
            if tier is None:
                break
            if not por_elo[tier]:
                if recargas.get(tier, 0) >= RECARGAS:
                    esgotados.add(tier)
                    continue
                recargas[tier] = recargas.get(tier, 0) + 1
                por_elo[tier] = buscar_jogadores(api, regiao, tier)
                if not por_elo[tier]:
                    esgotados.add(tier)
                continue
            jogador = por_elo[tier].pop()
            antes = progresso["partidas"]
            for mid in api.ids_partidas_desde(regiao, jogador, desde, quantidade=por_jogador):
                if progresso["partidas"] >= meta or progresso["parar"]:
                    break
                if con.execute("SELECT 1 FROM riot_partidas WHERE match_id=?", (mid,)).fetchone():
                    continue
                p = api.partida(regiao, mid)
                if registrar_partida(con, nomes, p, patch, tier):
                    progresso["partidas"] += 1
                    feitas[tier] = feitas.get(tier, 0) + 1
                    progresso["por_elo"][ELO_PT[tier]] = progresso["por_elo"].get(ELO_PT[tier], 0) + 1
                else:
                    progresso["pular"] += 1
            # jogador sem nenhuma partida útil conta um pouquinho, para não travar num elo que não rende
            if progresso["partidas"] == antes:
                feitas[tier] = feitas.get(tier, 0) + 0.2
        fim = "Parado por você" if progresso["parar"] else "Pronto"
        progresso["etapa"] = f"{fim}: {progresso['partidas']} partidas novas do patch {patch}, de todos os elos."
    except RiotErro as e:
        progresso["erro"] = e.mensagem
    except Exception as e:
        progresso["erro"] = f"Falha na coleta: {e}"
    finally:
        progresso["rodando"] = False
        con.close()


def coletar_em_segundo_plano(chave, meta=200):
    threading.Thread(target=coletar, args=(chave, meta), daemon=True).start()


if __name__ == "__main__":
    import app  # reaproveita a leitura do .env
    ap = argparse.ArgumentParser()
    ap.add_argument("--partidas", type=int, default=200)
    a = ap.parse_args()
    t = threading.Thread(target=coletar, args=(app.chave_atual(), a.partidas))
    t.start()
    while t.is_alive():
        print(f"\r{progresso['etapa']} {progresso['partidas']}/{progresso['meta']}", end="", flush=True)
        time.sleep(2)
    print("\n", progresso["erro"] or progresso["etapa"])
