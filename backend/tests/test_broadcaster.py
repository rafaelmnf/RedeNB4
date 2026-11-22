"""Fan-out das mensagens ao vivo."""
import json
from datetime import UTC, datetime

from redenb4.servicos.broadcaster import DESCONECTAR, Broadcaster, serializar


async def test_publicar_entrega_a_todos():
    b = Broadcaster()
    f1, f2 = b.registrar(), b.registrar()
    b.publicar({"tipo": "cadastro"})
    assert json.loads(f1.get_nowait()) == json.loads(f2.get_nowait()) == {"tipo": "cadastro"}
    b.remover(f1)
    b.publicar({"tipo": "x"})
    assert f1.empty() and not f2.empty()


async def test_cliente_lento_e_desconectado():
    b = Broadcaster(tamanho_fila=2)
    lento, rapido = b.registrar(), b.registrar()
    for i in range(2):
        b.publicar({"i": i})
    rapido.get_nowait()
    rapido.get_nowait()
    b.publicar({"i": 2})                      # a fila do lento estoura
    assert lento.get_nowait() is DESCONECTAR and lento.empty()
    assert b.clientes == 1
    assert json.loads(rapido.get_nowait()) == {"i": 2}


def test_datas_em_iso():
    ts = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
    assert json.loads(serializar({"ts": ts, "nome": "José"})) == {"ts": "2026-11-22T12:00:00+00:00", "nome": "José"}
