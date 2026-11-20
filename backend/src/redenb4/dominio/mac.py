"""Validação e normalização de endereços MAC."""
import re

_SEPARADORES = re.compile(r"[\s:\-.]")
_HEX12 = re.compile(r"[0-9A-Fa-f]{12}\Z")
_FORMATOS = (
    re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\Z"),
    re.compile(r"(?:[0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}\Z"),
    re.compile(r"(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}\Z"),
    _HEX12,
)


class MacInvalido(ValueError):
    pass


def normalizar_mac(texto: str) -> str:
    """Aceita AA:BB:CC:DD:EE:FF, aa-bb-cc-dd-ee-ff, aabb.ccdd.eeff ou aabbccddeeff.
    Devolve sempre 'AA:BB:CC:DD:EE:FF'. Levanta MacInvalido se o formato for inválido."""
    if not isinstance(texto, str):
        raise MacInvalido("MAC deve ser texto")
    bruto = texto.strip()
    if not any(f.fullmatch(bruto) for f in _FORMATOS):
        raise MacInvalido(f"MAC inválido: {texto!r}; use o formato AA:BB:CC:DD:EE:FF")
    hexa = _SEPARADORES.sub("", bruto).upper()
    return ":".join(hexa[i:i + 2] for i in range(0, 12, 2))


def mac_para_bytes(mac: str) -> bytes:
    return bytes.fromhex(normalizar_mac(mac).replace(":", ""))


def bytes_para_mac(b: bytes) -> str:
    return b.hex(":").upper()
