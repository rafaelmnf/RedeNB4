"""O parser do AP deve extrair MAC, BPM e RSSI dos frames gerados pelo simulador."""
from redenb4.ingestao import aruba_parser
from redenb4.simulador import entrada_dispositivo, mac_simulado, montar_frame

MAC1, MAC2 = mac_simulado(1), mac_simulado(2)
OUTRO = bytes.fromhex("112233445566")


def _frame():
    return montar_frame([
        entrada_dispositivo(MAC1, 72, -63, 1, "Polar Sense 1"),
        entrada_dispositivo(OUTRO, None, -80, 1, "Outro"),          # só inventário
        entrada_dispositivo(MAC2, 140, -88, 1, "Polar Sense 2"),
    ])


def test_extrai_bpm_e_rssi_dos_macs_da_allowlist():
    res = {a.mac: a for a in aruba_parser.decodificar_frame(_frame(), frozenset({MAC1, MAC2}))}
    assert set(res) == {MAC1, MAC2}
    assert (res[MAC1].bpm, res[MAC1].rssi) == (72, -63)
    assert (res[MAC2].bpm, res[MAC2].rssi) == (140, -88)
    assert len(res[MAC1].payload) == 16


def test_ignora_macs_fora_da_allowlist():
    res = aruba_parser.decodificar_frame(_frame(), frozenset({MAC2}))
    assert [a.mac for a in res] == [MAC2]


def test_allowlist_vazia_nao_decodifica_nada():
    assert aruba_parser.decodificar_frame(_frame(), frozenset()) == []


def test_entrada_de_inventario_sem_advertisement_e_ignorada():
    frame = montar_frame([entrada_dispositivo(MAC1, None, -60, 1, "Polar Sense 1")])
    assert aruba_parser.decodificar_frame(frame, frozenset({MAC1})) == []


def test_frame_truncado_ainda_entrega_entradas_completas():
    frame = _frame()
    # corta no meio da última entrada (o AP corta frames em ~4096 bytes)
    truncado = frame[: len(frame) - 10]
    res = aruba_parser.decodificar_frame(truncado, frozenset({MAC1, MAC2}))
    assert MAC1 in {a.mac for a in res}


def test_bpm_zero_fora_do_braco_e_decodificado():
    frame = montar_frame([entrada_dispositivo(MAC1, 0, -60, 1, "Polar Sense 1")])
    (a,) = aruba_parser.decodificar_frame(frame, frozenset({MAC1}))
    assert a.bpm == 0
