"""WebSocket /ws/ao-vivo e GET /api/status com o app de verdade (lifespan), contra o
banco de testes. A ingestão do AP não sobe; as leituras entram direto no pipeline."""
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from redenb4.api.app import criar_app
from redenb4.config import Config
from redenb4.db.repos import pulseiras as repo_puls
from redenb4.dominio.leitura import Leitura

MAC = "A0:9E:1A:00:00:01"


@pytest.fixture
async def cliente(fabrica, url_banco_teste):
    async with fabrica() as s:
        await repo_puls.cadastrar(s, MAC, "Pulseira 01")
    # O TestClient roda o app (com o lifespan) no próprio loop, numa thread separada.
    app = criar_app(Config(database_url=url_banco_teste), iniciar_ingestao=False)
    with TestClient(app) as c:
        yield c


def test_status_lista_pulseira_sem_dados(cliente):
    [cartao] = cliente.get("/api/status").json()
    assert cartao["mac"] == MAC and cartao["nome"] == "Pulseira 01"
    assert cartao["sem_dados"] and not cartao["online"] and cartao["pesquisador"] is None


def test_ws_snapshot_leitura_e_pedido_de_snapshot(cliente):
    app = cliente.app
    with cliente.websocket_connect("/ws/ao-vivo") as ws:
        msg = ws.receive_json()
        assert msg["tipo"] == "snapshot" and [c["mac"] for c in msg["pulseiras"]] == [MAC]

        # Uma leitura processada no loop do servidor chega como mensagem 'leitura'.
        leitura = Leitura(MAC, 77, -60, datetime.now(UTC), b"\x01", None)
        cliente.portal.call(app.state.pipeline.processar, [leitura])
        msg = ws.receive_json()
        assert msg["tipo"] == "leitura" and msg["bpm"] == 77
        assert msg["cartao"]["online"] and msg["cartao"]["ultimo_bpm"] == 77

        ws.send_json({"tipo": "snapshot"})
        msg = ws.receive_json()
        assert msg["tipo"] == "snapshot" and msg["pulseiras"][0]["ultimo_bpm"] == 77
