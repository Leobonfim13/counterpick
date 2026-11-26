"""Roda o leitor de print nos prints REAIS (testes/reais/) e compara com o gabarito informado pelo usuário.

Uso:  python testes/medir_reais.py          (todos)
      python testes/medir_reais.py -v       (mostra a leitura de cada slot)
"""
import json
import os
import sqlite3
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PASTA = os.path.join(AQUI, "reais")
sys.path.insert(0, RAIZ)

import leitor_print  # noqa: E402


def main(verboso):
    con = sqlite3.connect(os.path.join(RAIZ, "counterpick.db"))
    mapa = {r[0]: r[1] for r in con.execute("SELECT id, nome FROM campeoes")}
    rr = {}
    for rota, c, x in con.execute("SELECT rota, campeao, role_rate FROM meta"):
        rr.setdefault(c, {})[rota] = x or 0
    con.close()
    nomes = set(mapa.values())
    with open(os.path.join(PASTA, "gabarito.json"), encoding="utf-8") as f:
        gabarito = json.load(f)
    total = certos = errados_certeza = 0
    for caso in gabarito:
        for lado in ("esquerda", "direita"):
            for n in caso[lado]:
                assert n in nomes, f"gabarito com nome desconhecido: {n}"
        with open(os.path.join(PASTA, caso["arquivo"]), "rb") as f:
            dados = f.read()
        try:
            r = leitor_print.ler(dados, mapa, rr)
        except ValueError as e:
            print(f"{caso['arquivo']}: RECUSADO -> {e}")
            total += 10
            continue
        acertos = []
        for lado in ("esquerda", "direita"):
            lido = r[lado]
            for k, nome in enumerate(caso[lado]):
                total += 1
                got = lido[k] if k < len(lido) else None
                ok = got is not None and got["name"] == nome
                certos += ok
                if got is not None and not ok and got["certeza"]:
                    errados_certeza += 1
                acertos.append(ok)
                if verboso:
                    print(f"  {lado:8} {k + 1}: esperado {nome:14} lido {got['name'] if got else '-':14} "
                          f"{'certeza' if got and got['certeza'] else 'confira':8} {'OK' if ok else 'ERRO'}")
        print(f"{caso['arquivo']}: {sum(acertos)}/{len(acertos)}")
    print(f"TOTAL: {certos}/{total} ({100 * certos / max(total, 1):.0f}%) | errados marcados 'certeza': {errados_certeza}")


if __name__ == "__main__":
    main("-v" in sys.argv)
