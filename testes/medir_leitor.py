"""Mede a precisão do leitor de print numa bateria grande de prints gerados (gabarito conhecido).

Uso:  python testes/medir_leitor.py 400
Mostra: acerto por campeão, erros "com certeza" (os perigosos), campeões inventados (falso positivo) e tempo.
"""
import os
import sqlite3
import sys
import time
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
sys.path.insert(0, AQUI)

import gerar_prints  # noqa: E402
import leitor_print  # noqa: E402


def main(n, semente):
    con = sqlite3.connect(os.path.join(RAIZ, "counterpick.db"))
    mapa = {r[0]: r[1] for r in con.execute("SELECT id, nome FROM campeoes")}
    rr = {}
    for rota, c, x in con.execute("SELECT rota, campeao, role_rate FROM meta"):
        rr.setdefault(c, {})[rota] = x or 0
    con.close()
    casos = gerar_prints.gerar(n, semente=semente)
    stats = {t: Counter() for t in ("selecao", "tab")}
    erros_exemplo = Counter()
    tempos = []
    for caso, dados in casos:
        t = time.time()
        s = stats[caso["tipo"]]
        try:
            r = leitor_print.ler(dados, mapa, rr)
        except ValueError:
            s["recusado"] += 1
            s["total"] += 10
            continue
        tempos.append(time.time() - t)
        for lado in ("esquerda", "direita"):
            esperado, lido = caso[lado], r[lado]
            s["total"] += len(esperado)
            nomes_lidos = [x["name"] for x in lido]
            for k, nome in enumerate(esperado):
                if k < len(lido) and lido[k]["name"] == nome:
                    s["certo"] += 1
                    s["certo_com_certeza"] += lido[k]["certeza"]
                else:
                    s["errado"] += 1
                    if k < len(lido):
                        if lido[k]["certeza"]:
                            s["errado_com_certeza"] += 1
                        erros_exemplo[f"{nome} lido como {lido[k]['name']}"] += 1
                    else:
                        s["nao_achou"] += 1
            s["inventados"] += sum(1 for x in nomes_lidos if x not in esperado)
    for tipo, s in stats.items():
        if not s["total"]:
            continue
        print(f"{tipo:8}: {s['certo']}/{s['total']} certos ({100 * s['certo'] / s['total']:.1f}%) | "
              f"errados COM certeza: {s['errado_com_certeza']} | não achou: {s['nao_achou']} | "
              f"campeões inventados: {s['inventados']} | certos marcados 'certeza': {s['certo_com_certeza']} | "
              f"prints recusados com aviso: {s['recusado']}")
    tempos.sort()
    print(f"tempo por print: mediana {1000 * tempos[len(tempos) // 2]:.0f} ms, pior {1000 * tempos[-1]:.0f} ms")
    if erros_exemplo:
        print("erros mais comuns:", erros_exemplo.most_common(6))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200, int(sys.argv[2]) if len(sys.argv) > 2 else 99)
