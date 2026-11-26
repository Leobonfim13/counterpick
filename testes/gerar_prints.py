"""Gera prints de teste parecidos com os do LoL, com o GABARITO certo (nós montamos, então sabemos a resposta).

Armadilhas incluídas para o leitor não ficar "mal acostumado":
- seleção de campeões: retratos redondos com aro, alguns ESCURECIDOS (ainda não travou), feitiços ao lado,
  nome do jogador escrito, fundo com arte borrada e ruído;
- Tab: ícones quadrados com NÚMERO DE NÍVEL por cima, 6 ITENS e 2 FEITIÇOS na mesma linha (parecem ícones!);
- resoluções 720p/900p/1080p/1440p, tamanhos variados, borrão, brilho/contraste e compressão JPG forte.

Uso:  python testes/gerar_prints.py 100     -> salva 100 prints + gabarito.json em testes/prints/
"""
import glob
import json
import os
import random
import sqlite3
import string
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
ICONES = os.path.join(RAIZ, "site", "icons")
RESOLUCOES = [(1280, 720), (1600, 900), (1920, 1080), (2560, 1440)]


def carregar():
    con = sqlite3.connect(os.path.join(RAIZ, "counterpick.db"))
    mapa = {r[0]: r[1] for r in con.execute("SELECT id, nome FROM campeoes")}
    con.close()
    champs = {}
    for arq in glob.glob(os.path.join(ICONES, "*.jpg")):
        cid = os.path.splitext(os.path.basename(arq))[0]
        if cid in mapa:
            champs[mapa[cid]] = cv2.imread(arq)
    itens = [cv2.imread(a) for a in glob.glob(os.path.join(ICONES, "items", "*.png"))]
    feiticos = [cv2.imread(a) for a in glob.glob(os.path.join(ICONES, "spells", "*.png"))]
    return mapa, champs, [i for i in itens if i is not None], [f for f in feiticos if f is not None]


def fundo(W, H, champs, rng):
    img = np.zeros((H, W, 3), np.float32)
    c1 = np.array(rng.choice([(28, 22, 16), (20, 24, 30), (30, 26, 22)]), np.float32)
    for y in range(H):
        img[y, :] = c1 * (0.7 + 0.6 * y / H)
    # "arte" de fundo: alguns campeões gigantes, borrados e escuros (como a splash art da seleção)
    for _ in range(3):
        a = cv2.resize(rng.choice(list(champs.values())), (W // 3, W // 3))
        a = cv2.GaussianBlur(a, (0, 0), 18).astype(np.float32) * 0.25
        x, y = rng.randint(0, W - W // 3), rng.randint(0, max(1, H - W // 3))
        h = min(W // 3, H - y)
        img[y:y + h, x:x + W // 3] += a[:h]
    img += np.random.default_rng(rng.randint(0, 9999)).normal(0, 4, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def colar(img, peca, x, y):
    h, w = peca.shape[:2]
    H, W = img.shape[:2]
    if x < 0 or y < 0 or x + w > W or y + h > H:
        return
    img[y:y + h, x:x + w] = peca


def texto(img, x, y, escala, rng):
    nome = "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(rng.randint(4, 12)))
    cv2.putText(img, nome, (x, y), cv2.FONT_HERSHEY_SIMPLEX, escala, (200, 200, 200), max(1, int(escala * 2)), cv2.LINE_AA)


def selecao(W, H, champs, feiticos, rng):
    img = fundo(W, H, champs, rng)
    escolhidos = rng.sample(list(champs), 10)
    ali, ini = escolhidos[:5], escolhidos[5:]
    d = int(H * rng.uniform(0.065, 0.095))
    passo = int(H * rng.uniform(0.11, 0.135))
    topo = int(H * rng.uniform(0.15, 0.22))
    for lado, nomes in ((0, ali), (1, ini)):
        for k, nome in enumerate(nomes):
            cx = int(W * (rng.uniform(0.06, 0.09) if lado == 0 else rng.uniform(0.91, 0.94)))
            cy = topo + k * passo
            p = cv2.resize(champs[nome], (d, d), interpolation=cv2.INTER_CUBIC)
            if rng.random() < 0.3:  # ainda não travou: retrato escurecido
                p = (p * rng.uniform(0.4, 0.6)).astype(np.uint8)
            m = np.zeros((d, d), np.uint8)
            cv2.circle(m, (d // 2, d // 2), d // 2 - 1, 255, -1)
            x0, y0 = cx - d // 2, cy - d // 2
            if 0 <= x0 and x0 + d <= W and 0 <= y0 and y0 + d <= H:
                roi = img[y0:y0 + d, x0:x0 + d]
                roi[m > 0] = p[m > 0]
                cor = rng.choice([(90, 140, 160), (60, 110, 200), (120, 120, 120)])
                cv2.circle(img, (cx, cy), d // 2, cor, max(2, d // 30))
            # feitiços ao lado (armadilha) e nome do jogador
            s = int(d * 0.36)
            fx = cx + int(d * 0.65) if lado == 0 else cx - int(d * 0.65) - s
            for j in range(2):
                colar(img, cv2.resize(rng.choice(feiticos), (s, s)), fx, cy - s + j * (s + 2))
            texto(img, (fx + s + 10) if lado == 0 else (fx - int(W * 0.12)), cy + 6, H / 1400, rng)
    return img, ali, ini


def tab(W, H, champs, itens, feiticos, rng):
    img = fundo(W, H, champs, rng)
    escolhidos = rng.sample(list(champs), 10)
    ali, ini = escolhidos[:5], escolhidos[5:]
    d = int(H * rng.uniform(0.04, 0.06))
    passo = int(d * rng.uniform(1.25, 1.5))
    topo = int(H * rng.uniform(0.25, 0.35))
    for lado, nomes in ((0, ali), (1, ini)):
        x = int(W * (rng.uniform(0.18, 0.22) if lado == 0 else rng.uniform(0.53, 0.57)))
        for k, nome in enumerate(nomes):
            y = topo + k * passo
            p = cv2.resize(champs[nome], (d, d), interpolation=cv2.INTER_AREA)
            colar(img, p, x, y)
            cv2.rectangle(img, (x - 1, y - 1), (x + d, y + d), (70, 70, 70), 1)
            # número do nível no canto (armadilha)
            r = d // 5
            cv2.circle(img, (x + r, y + d - r), r, (10, 10, 10), -1)
            cv2.putText(img, str(rng.randint(1, 18)), (x + 2, y + d - 2), cv2.FONT_HERSHEY_SIMPLEX, d / 90, (230, 230, 230), 1, cv2.LINE_AA)
            s = int(d * 0.48)
            for j in range(2):
                colar(img, cv2.resize(rng.choice(feiticos), (s, s)), x + d + 4, y + j * (s + 1))
            texto(img, x + d + s + 12, y + d // 2 + 5, H / 1800, rng)
            ix = x + d + s + int(W * 0.09)
            t = int(d * rng.uniform(0.75, 0.95))
            for j in range(6):  # 6 itens na linha (armadilha: também são ícones quadrados)
                if rng.random() < 0.85:
                    colar(img, cv2.resize(rng.choice(itens), (t, t)), ix + j * (t + 3), y + (d - t) // 2)
    return img, ali, ini


def piorar(img, rng):
    if rng.random() < 0.5:
        img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.4, 1.2))
    a, b = rng.uniform(0.85, 1.15), rng.uniform(-15, 15)
    img = np.clip(img.astype(np.float32) * a + b, 0, 255).astype(np.uint8)
    q = rng.choice([45, 60, 75, 90])
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return buf.tobytes()


def gerar(n, semente=2026, salvar_em=None):
    mapa, champs, itens, feiticos = carregar()
    rng = random.Random(semente)
    casos = []
    for i in range(n):
        W, H = rng.choice(RESOLUCOES)
        tipo = "selecao" if i % 2 == 0 else "tab"
        if tipo == "selecao":
            img, ali, ini = selecao(W, H, champs, feiticos, rng)
        else:
            img, ali, ini = tab(W, H, champs, itens, feiticos, rng)
        dados = piorar(img, rng)
        caso = {"arquivo": f"print_{i:03d}_{tipo}_{W}x{H}.jpg", "tipo": tipo, "resolucao": f"{W}x{H}",
                "esquerda": ali, "direita": ini}
        if salvar_em:
            with open(os.path.join(salvar_em, caso["arquivo"]), "wb") as f:
                f.write(dados)
        casos.append((caso, dados))
    if salvar_em:
        with open(os.path.join(salvar_em, "gabarito.json"), "w", encoding="utf-8") as f:
            json.dump([c for c, _ in casos], f, ensure_ascii=False, indent=1)
    return casos


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    destino = os.path.join(AQUI, "prints")
    os.makedirs(destino, exist_ok=True)
    gerar(n, salvar_em=destino)
    print(f"{n} prints + gabarito.json salvos em {destino}")
