"""O parser do AP deve extrair MAC, BPM e RSSI dos frames gerados pelo simulador
e de entradas capturadas do AP real."""
from redenb4.ingestao import aruba_parser
from redenb4.simulador import campo_bytes, campo_varint, entrada_dispositivo, mac_simulado, montar_frame

MAC1, MAC2 = mac_simulado(1), mac_simulado(2)
OUTRO = bytes.fromhex("112233445566")


def _frame():
    return montar_frame([
        entrada_dispositivo(MAC1, 72, -63, 1),
        entrada_dispositivo(OUTRO, None, -80, 1),          # só inventário
        entrada_dispositivo(MAC2, 140, -88, 1),
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
    frame = montar_frame([entrada_dispositivo(MAC1, None, -60, 1)])
    assert aruba_parser.decodificar_frame(frame, frozenset({MAC1})) == []


def test_frame_truncado_ainda_entrega_entradas_completas():
    frame = _frame()
    # corta no meio da última entrada (o AP corta frames em ~4096 bytes)
    truncado = frame[: len(frame) - 10]
    res = aruba_parser.decodificar_frame(truncado, frozenset({MAC1, MAC2}))
    assert MAC1 in {a.mac for a in res}


def test_bpm_zero_fora_do_braco_e_decodificado():
    frame = montar_frame([entrada_dispositivo(MAC1, 0, -60, 1)])
    (a,) = aruba_parser.decodificar_frame(frame, frozenset({MAC1}))
    assert a.bpm == 0


# ------------------------------------------------- capturas do AP real (--dump)
# Entradas reais do AP; só o MAC da pulseira foi trocado por um fictício.
RADIO_AP_REAL = bytes.fromhex("40bd32c13cef")


def _entrada_real(adv_hex: str, rssi_varint: int) -> bytes:
    return (
        campo_bytes(1, MAC1)
        + campo_varint(2, 0)
        + campo_bytes(3, bytes.fromhex(adv_hex))
        + campo_varint(4, rssi_varint)
        + campo_varint(5, 0)
        + campo_bytes(6, RADIO_AP_REAL)
    )


def test_captura_real_bpm_rssi_e_radio_do_ap():
    entrada = _entrada_real("02010613ff6b007208e53ee003000000007a010123004505020d18eefe", 145)
    (a,) = aruba_parser.decodificar_frame(montar_frame([entrada]), frozenset({MAC1}))
    assert a.bpm == 0x45 == 69
    assert a.rssi == -73                 # ZigZag(145)
    assert a.radio_ap == RADIO_AP_REAL


def test_captura_real_fora_do_braco():
    entrada = _entrada_real("02010613ff6b007208e53ee003000000007a010133000005020d18eefe", 135)
    (a,) = aruba_parser.decodificar_frame(montar_frame([entrada]), frozenset({MAC1}))
    assert (a.bpm, a.rssi) == (0, -68)


def test_rssi_usa_campo_4_mesmo_com_outros_varints_na_faixa():
    # um varint anterior que também cairia em -120..-20 não deve enganar o parser
    no = [(2, 0, 135), (4, 0, 147)]
    assert aruba_parser.achar_rssi(no) == (-74, 4)


def test_rssi_cai_na_heuristica_sem_campo_4():
    assert aruba_parser.achar_rssi([(7, 0, 135)]) == (-68, 7)


def test_detecta_polar_nao_cadastrada_e_ignora_inventario():
    frame = _frame()
    achadas = aruba_parser.achar_polar_no_frame(frame)
    assert achadas == {MAC1: -63, MAC2: -88}          # OUTRO é só inventário


def test_resumo_do_cabecalho_mascara_textos():
    frame = montar_frame([entrada_dispositivo(m, 70, -60, 1) for m in (MAC1, MAC2, OUTRO)], token="segredo")
    linhas = aruba_parser.resumir_frame(frame)
    texto = "\n".join(linhas)
    assert "segredo" not in texto
    assert "texto 'se…' (7)" in texto
    assert "aparece 3x" in texto


def test_extrai_token_do_cabecalho():
    assert aruba_parser.extrair_token(montar_frame([], token="polar123")) == "polar123"
    assert aruba_parser.extrair_token(montar_frame([])) == ""
    assert aruba_parser.extrair_token(b"") is None
