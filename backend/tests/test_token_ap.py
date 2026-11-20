"""Validação do endpointToken do AP."""
from redenb4.ingestao.servidor_ap import ServidorAP
from redenb4.simulador import montar_frame


def _servidor(token: str) -> ServidorAP:
    return ServidorAP(allowlist=None, processar=None, fabrica_sessoes=None, token=token)


def test_sem_token_configurado_aceita_tudo():
    assert _servidor("").token_valido(montar_frame([]))
    assert _servidor("").token_valido(b"lixo")


def test_com_token_aceita_so_o_correto():
    s = _servidor("polar123")
    assert s.token_valido(montar_frame([], token="polar123"))
    assert not s.token_valido(montar_frame([], token="outro"))
    assert not s.token_valido(montar_frame([]))
    assert not s.token_valido(b"lixo")
