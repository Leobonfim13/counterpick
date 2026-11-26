"""Lê um print do LoL (seleção de campeões ou placar do Tab) e descobre os campeões, 100% no seu PC.

Como funciona:
1. Procura no print regiões que podem ser retrato: círculos (seleção) e quadrados (Tab).
2. Compara cada região com os 173 ícones oficiais de campeão E com os ícones de item, feitiço e runa:
   se parecer mais um item/feitiço do que um campeão, é descartada (o Tab é cheio de itens!).
   Antes de comparar, testa pequenos deslocamentos e zooms (recortes tortos, retratos escurecidos).
3. Usa a FORMA do time: os 5 campeões ficam numa coluna, do mesmo tamanho e espaçados igual.
   Itens ficam em fileira horizontal e feitiços são menores, então saem.
4. Esquerda/direita da tela = os dois times; de cima para baixo = a ordem.
5. Para cada time, sugere a rota mais provável de cada campeão (op.gg), sem repetir rota.
O print é lido na memória e descartado: nada é salvo.
"""
import glob
import itertools
import math
import os

# limite de pixels ANTES de carregar o OpenCV: barra "bomba de imagem" (arquivo pequeno, milhões de pixels)
os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", str(40_000_000))
import cv2
import numpy as np

PASTA = os.path.dirname(os.path.abspath(__file__))
ICONES = os.path.join(PASTA, "site", "icons")
TAM = 32
CONFIA = 0.66     # nota mínima para "certeza"
MARGEM_OK = 0.06  # distância mínima para o 2º colocado para "certeza"
MINIMO = 0.40     # abaixo disso não é campeão

_base = None


def _mascara(n, raio):
    yy, xx = np.mgrid[0:n, 0:n]
    c = (n - 1) / 2
    return ((xx - c) ** 2 + (yy - c) ** 2) <= (raio * n) ** 2


MASC = _mascara(TAM, 0.44)


def _descritor(img_bgr):
    p = cv2.resize(img_bgr, (TAM, TAM), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(p, cv2.COLOR_BGR2LAB).astype(np.float32)
    v = lab[MASC]                     # (pixels, 3)
    v = v - v.mean(axis=0)            # tira o brilho médio de cada canal (retrato escurecido continua igual)
    v = v.reshape(-1)
    n = np.linalg.norm(v)
    return v / n if n else v


def _carregar_base(mapa_id_nome):
    """Campeões (ícone inteiro e aproximações no centro) + itens, feitiços e runas como 'não é campeão'."""
    global _base
    if _base is not None:
        return _base
    nomes, vetores, eh_campeao = [], [], []
    for arq in glob.glob(os.path.join(ICONES, "*.jpg")):
        cid = os.path.splitext(os.path.basename(arq))[0]
        nome = mapa_id_nome.get(cid)
        img = cv2.imread(arq)
        if nome is None or img is None:
            continue
        h, w = img.shape[:2]
        for corte in (0.0, 0.07, 0.14):
            a, b = int(h * corte), int(w * corte)
            vetores.append(_descritor(img[a:h - a, b:w - b])); nomes.append(nome); eh_campeao.append(True)
    for pasta in ("items", "spells", "runes"):
        for arq in glob.glob(os.path.join(ICONES, pasta, "*.png")):
            img = cv2.imread(arq, cv2.IMREAD_UNCHANGED)
            if img is None:
                continue
            if img.ndim == 3 and img.shape[2] == 4:  # runas têm fundo transparente: põe fundo escuro
                alfa = img[:, :, 3:4].astype(np.float32) / 255
                img = (img[:, :, :3].astype(np.float32) * alfa + 20 * (1 - alfa)).astype(np.uint8)
            vetores.append(_descritor(img)); nomes.append("_" + pasta); eh_campeao.append(False)
    _base = (nomes, np.stack(vetores), np.array(eh_campeao))
    return _base


def _classificar(img, x, y, l, base):
    """Melhor campeão para a região, testando pequenos deslocamentos e zooms. None se for item/feitiço/runa."""
    nomes, M, eh_c = base
    H, W = img.shape[:2]
    melhor = (None, -1.0, 0.0)
    for z in (0.92, 1.0, 1.08):
        ll = int(l * z)
        for dx in (-0.06, 0.0, 0.06):
            for dy in (-0.06, 0.0, 0.06):
                cx, cy = x + l / 2 + dx * l, y + l / 2 + dy * l
                x0, y0 = int(cx - ll / 2), int(cy - ll / 2)
                if x0 < 0 or y0 < 0 or x0 + ll > W or y0 + ll > H or ll < 12:
                    continue
                s = M @ _descritor(img[y0:y0 + ll, x0:x0 + ll])
                i_c = int(np.argmax(np.where(eh_c, s, -2)))
                s_obj = float(np.max(np.where(eh_c, -2, s))) if (~eh_c).any() else -1
                if s[i_c] > melhor[1]:
                    segundo = max((s[j] for j in np.argsort(-s)[:12] if eh_c[j] and nomes[j] != nomes[i_c]), default=-1)
                    melhor = (nomes[i_c], float(s[i_c]), float(s[i_c] - segundo), s_obj)
    if melhor[0] is None or melhor[1] < MINIMO:
        return None
    if len(melhor) > 3 and melhor[3] >= melhor[1] - 0.02:
        return None  # parece mais um item/feitiço/runa do que um campeão
    return melhor[:3]


def _candidatos(img):
    h, w = img.shape[:2]
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    out = []
    borrada = cv2.medianBlur(cinza, 5)
    rmin, rmax = int(h * 0.02), int(h * 0.06)
    circ = cv2.HoughCircles(borrada, cv2.HOUGH_GRADIENT, dp=1.2, minDist=rmin * 2,
                            param1=110, param2=30, minRadius=rmin, maxRadius=rmax)
    if circ is not None:
        for x, y, r in np.round(circ[0]).astype(int):
            out.append((x - r, y - r, 2 * r, "circulo"))
    bordas = cv2.Canny(cinza, 50, 150)
    conts, _ = cv2.findContours(bordas, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    lmin, lmax = int(h * 0.03), int(h * 0.12)
    for c in conts:
        x, y, ww, hh = cv2.boundingRect(c)
        if lmin <= ww <= lmax and lmin <= hh <= lmax and abs(ww - hh) <= max(3, 0.12 * ww):
            if cv2.contourArea(c) >= 0.55 * ww * hh:
                out.append((x, y, max(ww, hh), "quadrado"))
    # tira candidatos repetidos (mesma região achada duas vezes)
    n_circulos = sum(1 for c in out if c[3] == "circulo")
    unicos = []
    for c in sorted(out, key=lambda c: (c[3] != "circulo", -c[2])):  # círculos primeiro
        if not any(abs(c[0] - u[0]) < 0.3 * u[2] and abs(c[1] - u[1]) < 0.3 * u[2] and abs(c[2] - u[2]) < 0.3 * u[2] for u in unicos):
            unicos.append(c)
    # devolve a contagem bruta de círculos no primeiro item "virtual" para a decisão do tipo de tela
    return [c for c in unicos] if n_circulos else unicos


def _melhor_coluna(achados):
    """Dos campeões achados num lado da tela, escolhe a COLUNA de até 5 (mesmo x, mesmo tamanho, espaçados)."""
    if not achados:
        return []
    melhor, melhor_nota = [], -1
    for ref in achados:
        tol_x, l = 0.45 * ref["l"], ref["l"]
        col = [a for a in achados if abs((a["x"] + a["l"] / 2) - (ref["x"] + ref["l"] / 2)) <= tol_x
               and 0.75 * l <= a["l"] <= 1.33 * l]
        col.sort(key=lambda a: a["y"])
        limpa = []
        for a in col:  # dois retratos não podem estar sobrepostos na vertical
            if limpa and a["y"] - limpa[-1]["y"] < 0.8 * l:
                if a["score"] > limpa[-1]["score"]:
                    limpa[-1] = a
                continue
            limpa.append(a)
        if len(limpa) > 5:
            limpa = sorted(sorted(limpa, key=lambda a: -a["score"])[:5], key=lambda a: a["y"])
        nota = sum(a["score"] for a in limpa) + 0.15 * len(limpa)
        if nota > melhor_nota:
            melhor, melhor_nota = limpa, nota
    # um time de verdade aparece como coluna: com menos de 3 alinhados, é ruído (melhor não chutar)
    return melhor if len(melhor) >= 3 else []


def ler(dados_imagem, mapa_id_nome, role_rate):
    arr = np.frombuffer(dados_imagem, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Não consegui abrir essa imagem. Use PNG ou JPG.")
    h, w = img.shape[:2]
    if w * h > 60_000_000:
        raise ValueError("Imagem grande demais.")
    if h < 200 or w < 200 or w / h > 4 or h / w > 2:   # print de jogo é ~16:9; fina/comprida explodiria ao redimensionar
        raise ValueError("Isso não parece um print da tela do jogo.")
    if h != 1080:  # escala padrão: mesmo comportamento em 720p, 1080p ou 1440p
        f = 1080 / h
        img = cv2.resize(img, (int(w * f), 1080), interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_CUBIC)
        h, w = img.shape[:2]
    base = _carregar_base(mapa_id_nome)

    cands = _candidatos(img)
    # A seleção de campeões tem retratos REDONDOS; o Tab tem quadrados. Por enquanto só lemos a seleção
    # (o Tab ainda não é confiável). Reconhece a tela pela quantidade de círculos achados.
    if sum(1 for c in cands if c[3] == "circulo") < 6:
        raise ValueError("Não reconheci uma seleção de campeões nesse print. Por enquanto eu leio só a tela de "
                         "seleção de campeões (o placar do Tab ainda está em teste). Ou digite os nomes.")
    achados = []
    for x, y, l, tipo in cands:
        r = _classificar(img, x, y, l, base)
        if r:
            achados.append({"x": x, "y": y, "l": l, "nome": r[0], "score": r[1], "margem": r[2], "tipo": tipo})
    if len(achados) < 3:
        raise ValueError("Não reconheci uma seleção de campeões nesse print. Por enquanto eu leio só a tela de "
                         "seleção de campeões (o placar do Tab ainda está em teste). Ou digite os nomes.")

    # Na seleção de campeões os times ficam nas BORDAS: aliados no terço esquerdo, inimigos no terço direito.
    esquerda = _melhor_coluna([a for a in achados if a["x"] + a["l"] / 2 < w * 0.33])
    direita = _melhor_coluna([a for a in achados if a["x"] + a["l"] / 2 > w * 0.67])

    # Na seleção, os retratos dos times são redondos. Se o que sobrou veio de quadrados, não é a seleção.
    escolhidos = esquerda + direita
    if len(escolhidos) < 3 or sum(1 for a in escolhidos if a["tipo"] == "circulo") < 0.6 * len(escolhidos):
        raise ValueError("Não reconheci uma seleção de campeões nesse print. Por enquanto eu leio só a tela de "
                         "seleção de campeões (o placar do Tab ainda está em teste). Ou digite os nomes.")

    # o mesmo campeão não pode estar duas vezes: fica onde a nota é maior
    for lado, outro in ((esquerda, direita), (direita, esquerda)):
        for a in list(lado):
            for b in list(lado) + list(outro):
                if b is not a and b["nome"] == a["nome"] and b["score"] >= a["score"]:
                    if a in lado:
                        lado.remove(a)
                    break

    def saida(lista):
        return [{"name": a["nome"], "certeza": a["score"] >= CONFIA and a["margem"] >= MARGEM_OK,
                 "nota": round(a["score"], 3)} for a in lista]

    return {"esquerda": saida(esquerda), "direita": saida(direita),
            "rotas_direita": rotas_provaveis([a["nome"] for a in direita], role_rate),
            "rotas_esquerda": rotas_provaveis([a["nome"] for a in esquerda], role_rate)}


ROTAS = ["top", "jungle", "mid", "adc", "support"]


def rotas_provaveis(nomes, role_rate):
    """Distribui até 5 campeões nas 5 rotas pela combinação mais provável (sem repetir rota)."""
    if not nomes:
        return {}
    melhor, melhor_s = None, -1e9
    for perm in itertools.permutations(ROTAS, len(nomes)):
        s = sum(math.log((role_rate.get(n, {}).get(r) or 0) + 0.01) for n, r in zip(nomes, perm))
        if s > melhor_s:
            melhor, melhor_s = perm, s
    return {n: r for n, r in zip(nomes, melhor)}
