import pytest

from redenb4.dominio.mac import MacInvalido, bytes_para_mac, mac_para_bytes, normalizar_mac


@pytest.mark.parametrize(
    "entrada",
    [
        "A0:9E:1A:12:34:56",
        "a0:9e:1a:12:34:56",
        "a0-9e-1a-12-34-56",
        "a09e.1a12.3456",
        "a09e1a123456",
        "  a0:9e:1a:12:34:56  ",
    ],
)
def test_aceita_formatos_e_normaliza(entrada):
    assert normalizar_mac(entrada) == "A0:9E:1A:12:34:56"


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "A0:9E:1A:12:34",           # curto
        "A0:9E:1A:12:34:56:78",     # longo
        "G0:9E:1A:12:34:56",        # não hexadecimal
        "A0:9E-1A:12:34:56",        # separadores misturados
        "A09E1A12345",              # 11 dígitos
        "A0 9E 1A 12 34 56",
    ],
)
def test_rejeita_invalidos(entrada):
    with pytest.raises(MacInvalido):
        normalizar_mac(entrada)


def test_rejeita_nao_texto():
    with pytest.raises(MacInvalido):
        normalizar_mac(None)  # type: ignore[arg-type]


def test_conversao_bytes_ida_e_volta():
    b = mac_para_bytes("a0-9e-1a-12-34-56")
    assert b == bytes.fromhex("A09E1A123456")
    assert bytes_para_mac(b) == "A0:9E:1A:12:34:56"
