"""Cliente do servidor MCP oficial do OP.GG (https://mcp-api.op.gg/mcp).

Fala o protocolo MCP (JSON-RPC por HTTP) e entende os dois formatos de resposta
do OP.GG: JSON normal e o formato compacto "class X: campos" + X(valores).
Consultas são lentas de propósito (uma por vez, com pausa) para não sobrecarregar o serviço.
"""
import json
import re
import threading
import time
import urllib.error
import urllib.request

URL = "https://mcp-api.op.gg/mcp"
CLIENT_APP = "CounterPick-local/0.2"
PAUSA = 0.35  # segundos entre consultas


class OpggErro(Exception):
    pass


# ---------- leitor do formato compacto ----------
_CLASS_LINE = re.compile(r"^class\s+(\w+):\s*(.*)$")


def parse_compacto(texto):
    classes = {}
    corpo = []
    for linha in texto.splitlines():
        m = _CLASS_LINE.match(linha.strip())
        if m:
            classes[m.group(1)] = [c.strip() for c in m.group(2).split(",") if c.strip()]
        elif linha.strip():
            corpo.append(linha)
    s = "\n".join(corpo).strip()
    pos = 0
    dec = json.JSONDecoder()

    def ws():
        nonlocal pos
        while pos < len(s) and s[pos] in " \t\r\n":
            pos += 1

    def valor(campos_pai=None):
        nonlocal pos
        ws()
        c = s[pos]
        if c == '"':
            v, fim = dec.raw_decode(s, pos)
            pos = fim
            return v
        if c == "[":
            pos += 1
            itens = []
            ws()
            if s[pos] == "]":
                pos += 1
                return itens
            while True:
                itens.append(valor())
                ws()
                if s[pos] == ",":
                    pos += 1
                    continue
                if s[pos] == "]":
                    pos += 1
                    return itens
                raise OpggErro("lista mal formada")
        m = re.compile(r"[A-Za-z_]\w*").match(s, pos)
        if m:
            nome = m.group(0)
            pos = m.end()
            ws()
            if pos < len(s) and s[pos] == "(":
                pos += 1
                args = []
                ws()
                if s[pos] != ")":
                    while True:
                        args.append(valor())
                        ws()
                        if s[pos] == ",":
                            pos += 1
                            continue
                        if s[pos] == ")":
                            break
                        raise OpggErro("objeto mal formado")
                pos += 1
                campos = classes.get(nome, [])
                return {campos[i] if i < len(campos) else f"_{i}": a for i, a in enumerate(args)}
            return {"true": True, "false": False, "null": None, "None": None, "True": True, "False": False}.get(nome, nome)
        m = re.compile(r"-?\d+(\.\d+)?([eE][-+]?\d+)?").match(s, pos)
        if m:
            pos = m.end()
            t = m.group(0)
            return float(t) if any(ch in t for ch in ".eE") else int(t)
        raise OpggErro(f"valor inesperado perto de: {s[pos:pos + 30]!r}")

    return valor()


def ler_conteudo(resultado):
    """Converte o texto da ferramenta (JSON ou compacto) em dict."""
    textos = [c.get("text", "") for c in resultado.get("content", []) if c.get("type") == "text"]
    if not textos:
        raise OpggErro("resposta vazia do OP.GG")
    t = textos[0].strip()
    if resultado.get("isError"):
        raise OpggErro(t[:200])
    if t.startswith("{") or t.startswith("["):
        return json.loads(t)
    if t.startswith("class "):
        return parse_compacto(t)
    raise OpggErro(t[:200])


class OpggMCP:
    def __init__(self):
        self.sessao = None
        self.trava = threading.Lock()
        self.ultimo = 0.0
        self.n = 0

    def _post(self, corpo):
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "User-Agent": CLIENT_APP}
        if self.sessao:
            h["Mcp-Session-Id"] = self.sessao
        req = urllib.request.Request(URL, data=json.dumps(corpo).encode(), headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            self.sessao = r.headers.get("Mcp-Session-Id") or self.sessao
            raw = r.read().decode("utf-8")
            ctype = r.headers.get("Content-Type", "")
        if not raw.strip():
            return None
        if "event-stream" in ctype:
            dados = [l[5:].strip() for l in raw.splitlines() if l.startswith("data:")]
            return json.loads(dados[-1]) if dados else None
        return json.loads(raw)

    def _iniciar(self):
        self.sessao = None
        self._post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                               "clientInfo": {"name": "counterpick", "version": "0.2"}}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def chamar(self, ferramenta, argumentos, tentativas=3):
        argumentos = {**argumentos, "client_app": CLIENT_APP}
        with self.trava:
            erro = None
            for t in range(tentativas):
                espera = PAUSA - (time.monotonic() - self.ultimo)
                if espera > 0:
                    time.sleep(espera)
                try:
                    if not self.sessao:
                        self._iniciar()
                    self.n += 1
                    r = self._post({"jsonrpc": "2.0", "id": self.n + 10, "method": "tools/call",
                                    "params": {"name": ferramenta, "arguments": argumentos}})
                    self.ultimo = time.monotonic()
                    if r is None or "error" in r:
                        raise OpggErro((r or {}).get("error", {}).get("message", "erro do OP.GG"))
                    return ler_conteudo(r["result"])
                except urllib.error.HTTPError as e:
                    erro = OpggErro(f"HTTP {e.code} do OP.GG")
                    if e.code in (400, 404, 409):
                        self.sessao = None  # sessão expirou: abre outra
                    time.sleep(1.5 * (t + 1))
                except (urllib.error.URLError, TimeoutError) as e:
                    erro = OpggErro("Sem conexão com o OP.GG")
                    time.sleep(1.5 * (t + 1))
                except OpggErro as e:
                    erro = e
                    time.sleep(1.0)
            raise erro

    # ---------- atalhos ----------
    def meta_por_rota(self):
        campos = [f"data.positions.{p}[].{{champion,tier,rank,win_rate,pick_rate,ban_rate,role_rate,play,is_rip}}"
                  for p in ("top", "jungle", "mid", "adc", "support")]
        return self.chamar("lol_list_lane_meta_champions", {"position": "all", "lang": "pt_BR", "desired_output_fields": campos})

    def confronto(self, rota, meu, oponente):
        return self.chamar("lol_get_lane_matchup_guide", {"position": rota, "my_champion": meu, "opponent_champion": oponente, "lang": "pt_BR"})

    def perfil(self, nome, tag, regiao="BR"):
        campos = [
            "data.summoner.league_stats[].{game_type,win,lose}",
            "data.summoner.league_stats[].tier_info.{tier,division,lp}",
            "data.summoner.most_champions.champion_stats[].{champion_name,play,win,kill,death,assist,minion_kill,neutral_minion_kill,game_length_second}",
        ]
        return self.chamar("lol_get_summoner_profile", {"game_name": nome, "tag_line": tag, "region": regiao, "lang": "pt_BR", "desired_output_fields": campos})


def chave_opgg(nome_campeao):
    """'Kai'Sa' -> 'KAISA', 'Dr. Mundo' -> 'DR_MUNDO', 'Nunu & Willump' -> 'NUNU_WILLUMP' (conferido no OP.GG)."""
    s = nome_campeao.replace("'", "").replace(".", "").replace("&", " ")
    return re.sub(r"\s+", "_", s.strip()).upper()
