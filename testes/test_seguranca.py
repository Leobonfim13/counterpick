"""
Testes de segurança e robustez do CounterPick (sem internet).  Rodar:  python testes/test_seguranca.py
Trabalha numa CÓPIA do banco e desliga as consultas ao op.gg/Riot durante o teste.
"""
import os
import shutil
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import dados  # noqa: E402

_tmp = tempfile.mkdtemp()
_banco_real = os.path.join(RAIZ, "counterpick.db")
if os.path.exists(_banco_real):
    shutil.copy(_banco_real, os.path.join(_tmp, "cp.db"))
dados.BANCO = os.path.join(_tmp, "cp.db")
dados.completar_ordem = lambda *a, **k: None          # nada de internet nos testes
dados.sinergias = lambda *a, **k: None

import app as cp  # noqa: E402

cp.LOG_ACESSOS = os.path.join(_tmp, "acessos.log")
cp.buscar_confronto = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sem internet no teste"))
BASE = f"http://localhost:{cp.PORTA}"
H = {"X-CounterPick": "1"}


class Seguranca(unittest.TestCase):
    def setUp(self):
        cp.app.config["TESTING"] = True
        cp._limites.clear()
        self.c = cp.app.test_client()

    def get(self, url, ip="127.0.0.1", host=None, headers=H):
        base = f"http://{host}" if host else BASE
        return self.c.get(url, base_url=base, headers=headers, environ_base={"REMOTE_ADDR": ip})

    def post(self, url, json=None, ip="127.0.0.1", headers=H, data=None):
        return self.c.post(url, base_url=BASE, headers=headers, json=json, data=data, environ_base={"REMOTE_ADDR": ip})

    # --- quem pode entrar
    def test_so_este_pc_ou_tailscale(self):
        self.assertEqual(self.get("/api/status").status_code, 200)
        self.assertEqual(self.get("/api/status", ip="192.168.0.15").status_code, 403)   # rede de casa
        self.assertEqual(self.get("/api/status", ip="8.8.8.8").status_code, 403)        # internet
        self.assertEqual(self.get("/", ip="8.8.8.8").status_code, 403)

    def test_dns_rebinding(self):
        self.assertEqual(self.get("/api/status", host=f"evil.com:{cp.PORTA}").status_code, 403)
        self.assertEqual(self.get("/", host="localhost:9999").status_code, 403)

    def test_csrf_cabecalho_e_origem(self):
        self.assertEqual(self.get("/api/status", headers={}).status_code, 403)
        r = self.post("/api/recomendar", json={"rota": "MID"}, headers={**H, "Origin": "https://evil.com"})
        self.assertEqual(r.status_code, 403)

    def test_rotas_do_dono_bloqueadas_para_amigos(self):
        amigo = "100.101.102.103"                     # IP do Tailscale
        for url in ("/api/dados/atualizar", "/api/riot/coletar", "/api/riot/parar"):
            self.assertEqual(self.post(url, json={}, ip=amigo).status_code, 403, url)
        self.assertEqual(self.get("/api/riot/perfil?riot_id=abc%23BR1", ip=amigo).status_code, 403)
        self.assertFalse(self.get("/api/status", ip=amigo).get_json()["dono"])

    def test_limite_de_uso(self):
        codigos = [self.get("/api/perfil_riot?riot_id=x", ip="100.64.0.9").status_code for _ in range(8)]
        self.assertIn(429, codigos)

    def test_chave_nunca_vai_para_o_navegador(self):
        j = self.get("/api/status").get_json()
        self.assertLessEqual(set(j), {"local", "riot_configurada", "dono", "dono_riot_id"})
        amigo = self.get("/api/status", ip="100.101.102.103").get_json()
        self.assertNotIn("dono_riot_id", amigo)                        # amigo não descobre o Riot ID do dono
        texto = self.get("/api/status").get_data(as_text=True) + self.get("/api/dados/status").get_data(as_text=True)
        self.assertNotIn("RGAPI-", texto)

    # --- cabeçalhos
    def test_csp_sem_script_inline(self):
        r = self.get("/")
        csp = r.headers["Content-Security-Policy"]
        script_src = csp.split("script-src")[1].split(";")[0]
        self.assertNotIn("unsafe-inline", script_src)
        self.assertNotIn("unsafe-eval", script_src)
        html = r.get_data(as_text=True)
        self.assertIn('<script src="app.js"></script>', html)
        self.assertNotIn("<script>", html)
        self.assertIn("isn't endorsed by Riot Games", html)
        r.close()
        self.assertEqual(self.get("/app.js").status_code, 200)
        for h, v in (("X-Frame-Options", "DENY"), ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer")):
            self.assertEqual(self.get("/api/status").headers[h], v)

    # --- entradas malucas: sempre 4xx, nunca 500
    def test_lixo_nao_derruba(self):
        lixos = [None, [], [1, 2], "texto", 123,
                 {"rota": "MID", "inimigos": "abc", "aliados": {"x": 1}, "pool": 5, "perfil": "x", "draft": [1]},
                 {"rota": "MID", "perfil": [{"n": "Ahri", "g": "muitos", "wr": "NaN"}, {"n": "Ahri", "g": 1e400, "wr": "inf"}]},
                 {"rota": "MID", "modo": "draft", "draft": {"after": "zzz"}, "inimigos": [None, 5, "x"]},
                 {"rota": "MID", "meu": ["Ahri"], "aliados": [None, 3, {"name": None}]}]
        for corpo in lixos:
            for url in ("/api/recomendar", "/api/preparar"):
                r = self.post(url, json=corpo)
                self.assertLess(r.status_code, 500, (url, corpo, r.get_data(as_text=True)[:200]))
        r = self.post("/api/riot/coletar", json={"partidas": "muitas"})
        self.assertLess(r.status_code, 500)

    def test_riot_id_invalido(self):
        for rid in ("a#BR1", "nome/../x#BR1", "nome\x00#BR1", "semtag", "x" * 40 + "#BR1", "ok#B@D"):
            r = self.get("/api/perfil_opgg?riot_id=" + rid.replace("#", "%23"))
            self.assertEqual(r.status_code, 400, rid)

    def test_print_so_imagem_de_verdade(self):
        for corpo in (b"", b"MZ\x90\x00virus", b"RIFF\x00\x00\x00\x00WAVEfmt ", b"<svg onload=alert(1)>"):
            r = self.c.post("/api/ler_print", base_url=BASE, headers=H, data=corpo, environ_base={"REMOTE_ADDR": "127.0.0.1"})
            self.assertIn(r.status_code, (400, 501), corpo[:10])

    def test_bomba_de_imagem(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("OpenCV não instalado")
        import leitor_print
        fina = cv2.imencode(".png", np.zeros((10, 30000, 3), np.uint8))[1].tobytes()   # 10 px de altura
        with self.assertRaises(ValueError):
            leitor_print.ler(fina, {}, {})
        self.assertEqual(os.environ.get("OPENCV_IO_MAX_IMAGE_PIXELS"), str(40_000_000))


if __name__ == "__main__":
    unittest.main(verbosity=2)
