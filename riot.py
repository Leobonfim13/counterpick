"""Cliente mínimo da API oficial da Riot Games.

- A chave fica só aqui no servidor (lida do arquivo .env); nunca vai para o navegador.
- Respeita os limites da chave de desenvolvimento (20 pedidos/1s e 100 pedidos/2min)
  e espera o tempo pedido pela Riot quando recebe 429.
"""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque

# Servidor de cada região: contas e partidas usam o "regional", ranking usa a "plataforma".
PLATAFORMA = {"br": "br1", "na": "na1", "euw": "euw1", "eune": "eun1", "lan": "la1", "las": "la2", "kr": "kr", "jp": "jp1", "oce": "oc1", "tr": "tr1", "ru": "ru"}
REGIONAL = {"br": "americas", "na": "americas", "lan": "americas", "las": "americas", "oce": "sea",
            "euw": "europe", "eune": "europe", "tr": "europe", "ru": "europe", "kr": "asia", "jp": "asia"}


class RiotErro(Exception):
    def __init__(self, status, mensagem):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


class LimitadorDePedidos:
    """Janela deslizante para várias regras ao mesmo tempo, ex.: [(20, 1), (100, 120)]."""

    def __init__(self, regras):
        self.regras = [(maximo, janela, deque()) for maximo, janela in regras]
        self.trava = threading.Lock()

    def aguardar_vez(self):
        while True:
            with self.trava:
                agora = time.monotonic()
                espera = 0.0
                for maximo, janela, hist in self.regras:
                    while hist and agora - hist[0] >= janela:
                        hist.popleft()
                    if len(hist) >= maximo:
                        espera = max(espera, janela - (agora - hist[0]))
                if espera <= 0:
                    for _, _, hist in self.regras:
                        hist.append(agora)
                    return
            time.sleep(min(espera, 5))


_LIMITE_GLOBAL = LimitadorDePedidos([(19, 1), (98, 120)])  # um só para o programa inteiro (coleta + perfil)


class RiotAPI:
    def __init__(self, chave):
        self.chave = (chave or "").strip()
        self.limite = _LIMITE_GLOBAL

    @property
    def configurada(self):
        return self.chave.startswith("RGAPI-")

    def _get(self, host, caminho, params=None, tentativas=3):
        if not self.configurada:
            raise RiotErro(0, "Chave da Riot não configurada. Coloque a sua no arquivo .env.")
        url = f"https://{host}.api.riotgames.com{caminho}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for _ in range(tentativas):
            self.limite.aguardar_vez()
            pedido = urllib.request.Request(url, headers={"X-Riot-Token": self.chave, "User-Agent": "CounterPick-local"})
            try:
                with urllib.request.urlopen(pedido, timeout=15) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(min(int(e.headers.get("Retry-After", "2") or 2), 30))
                    continue
                if e.code in (401, 403):
                    raise RiotErro(e.code, "A Riot recusou a chave. Confira o RIOT_API_KEY no .env; se a chave foi trocada no portal (NEW API KEY), cole a nova.")
                if e.code == 404:
                    raise RiotErro(404, "Não encontrado na Riot.")
                if e.code >= 500:
                    time.sleep(1)
                    continue
                raise RiotErro(e.code, f"Erro {e.code} da Riot.")
            except urllib.error.URLError:
                raise RiotErro(0, "Sem conexão com a Riot. Verifique a internet.")
        raise RiotErro(429, "A Riot pediu para esperar (limite de pedidos). Tente de novo em instantes.")

    # --- chamadas usadas no teste da fase 1 ---
    def conta_por_riot_id(self, regiao, nome, tag):
        caminho = "/riot/account/v1/accounts/by-riot-id/{}/{}".format(
            urllib.parse.quote(nome, safe=""), urllib.parse.quote(tag, safe=""))
        return self._get(REGIONAL[regiao], caminho)

    def ranqueadas(self, regiao, puuid):
        return self._get(PLATAFORMA[regiao], f"/lol/league/v4/entries/by-puuid/{urllib.parse.quote(puuid, safe='')}")

    def ids_partidas(self, regiao, puuid, quantidade=5, fila=420):
        """fila=420 solo/duo, 440 flex; fila=None traz as duas ranqueadas (type=ranked)."""
        params = {"count": quantidade}
        if fila:
            params["queue"] = fila
        else:
            params["type"] = "ranked"
        return self._get(REGIONAL[regiao], f"/lol/match/v5/matches/by-puuid/{urllib.parse.quote(puuid, safe='')}/ids", params)

    def liga_elite(self, regiao, nivel):
        """nivel: challenger | grandmaster | master (fila solo/duo)."""
        return self._get(PLATAFORMA[regiao], f"/lol/league/v4/{nivel}leagues/by-queue/RANKED_SOLO_5x5")

    def jogadores_do_elo(self, regiao, tier, divisao="II", pagina=1):
        """Jogadores de um elo/divisão (Ferro a Diamante). Mestre+ usa liga_elite."""
        return self._get(PLATAFORMA[regiao], f"/lol/league/v4/entries/RANKED_SOLO_5x5/{tier}/{divisao}", {"page": pagina})

    def maestria_top(self, regiao, puuid, quantidade=10):
        return self._get(PLATAFORMA[regiao], f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{urllib.parse.quote(puuid, safe='')}/top",
                         {"count": quantidade})

    def ids_partidas_desde(self, regiao, puuid, desde_epoch, quantidade=20, fila=420):
        return self._get(REGIONAL[regiao], f"/lol/match/v5/matches/by-puuid/{urllib.parse.quote(puuid, safe='')}/ids",
                         {"count": quantidade, "queue": fila, "startTime": int(desde_epoch)})

    def partida(self, regiao, match_id):
        return self._get(REGIONAL[regiao], f"/lol/match/v5/matches/{urllib.parse.quote(match_id, safe='')}")
