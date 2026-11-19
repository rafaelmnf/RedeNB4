"""Decodificação "crua" dos frames protobuf de telemetria BLE do Aruba (InstantOS 8.10).

Não usa o aruba_iot_pb2 gerado: um parser protobuf sem schema procura as
submensagens que contêm o MAC (6 bytes crus) de uma pulseira e extrai o BPM do
manufacturer data da Polar (company ID 0x006B). Lógica movida de App/servidor_ws.py.

Estrutura de uma entrada de dispositivo, confirmada com --dump no AP real:
    [1] bytes   MAC da pulseira (6 bytes)
    [2] varint  0
    [3] bytes   advertisement (estruturas AD: flags, manufacturer data 0x006B, UUIDs 0x180D/0xFEEE)
    [4] varint  RSSI em sint32 (ZigZag): 135 -> -68 dBm, 145 -> -73 dBm
    [5] varint  0
    [6] bytes   MAC do rádio BLE do AP que ouviu (6 bytes)
Entradas sem o campo [3] são de inventário (sem BPM).
"""
from collections.abc import Iterator
from dataclasses import dataclass

POLAR_COMPANY_ID = 0x006B   # Polar Electro Oy
BYTE_BPM = 15               # posição do BPM no payload do manufacturer data
CAMPO_RSSI = 4              # sint32 (ZigZag)
CAMPO_RADIO_AP = 6          # MAC do rádio BLE do AP


# ---------------------------------------------------------------- protobuf cru
def _varint(buf: bytes, i: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        if i >= len(buf):
            raise ValueError("varint truncado")
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7
        if shift > 70:
            raise ValueError("varint invalido")


def parse(buf: bytes, strict: bool = False):
    """Retorna lista de (campo, wiretype, valor).
    strict=True: devolve None se o buffer nao for um protobuf valido completo.
    strict=False: tolerante, aceita ultimo campo truncado (frames cortados em 4096)."""
    out, i = [], 0
    while i < len(buf):
        try:
            key, i = _varint(buf, i)
            campo, wt = key >> 3, key & 7
            if campo == 0:
                raise ValueError("campo 0")
            if wt == 0:
                v, i = _varint(buf, i)
            elif wt == 2:
                n, i = _varint(buf, i)
                if i + n > len(buf):
                    if strict:
                        return None
                    v, i = buf[i:], len(buf)          # entrada truncada: pega o que tem
                else:
                    v, i = buf[i:i + n], i + n
            elif wt == 1:
                if i + 8 > len(buf):
                    raise ValueError("fixed64 truncado")
                v, i = buf[i:i + 8], i + 8
            elif wt == 5:
                if i + 4 > len(buf):
                    raise ValueError("fixed32 truncado")
                v, i = buf[i:i + 4], i + 4
            else:
                raise ValueError("wiretype invalido")
        except ValueError:
            if strict:
                return None
            break
        out.append((campo, wt, v))
    return out


def achar_nos_com_macs(buf: bytes, macs: frozenset[bytes] | set[bytes], profundidade: int = 0,
                       tolerante: bool = True) -> list[tuple[bytes, list]]:
    """Percorre o frame uma única vez e devolve (mac, campos) para cada mensagem que
    contém diretamente um dos MACs. O último campo de cada nível é lido de forma
    tolerante (o AP pode cortar o frame)."""
    campos = parse(buf, strict=not tolerante)
    if not campos or profundidade > 8:
        return []
    achados = []
    for _, wt, v in campos:
        if wt == 2 and v in macs:
            achados.append((bytes(v), campos))
    ultimo = len(campos) - 1
    for idx, (_, wt, v) in enumerate(campos):
        if wt == 2 and len(v) >= 6 and v not in macs:
            achados += achar_nos_com_macs(v, macs, profundidade + 1, tolerante=(idx == ultimo))
    return achados


def todos_bytes(campos, profundidade: int = 0) -> Iterator[bytes]:
    """Todos os campos bytes de um no, incluindo os de submensagens."""
    ultimo = len(campos) - 1
    for idx, (_, wt, v) in enumerate(campos):
        if wt == 2:
            yield v
            if profundidade < 6 and len(v) >= 4:
                sub = parse(v, strict=(idx != ultimo))
                if sub:
                    yield from todos_bytes(sub, profundidade + 1)


# ------------------------------------------------------------ advertisement BLE
def parse_ad(b: bytes) -> list[tuple[int, bytes]]:
    """Divide um advertisement em estruturas AD: [(tipo, dados), ...]."""
    i, res = 0, []
    while i < len(b):
        n = b[i]
        if n == 0 or i + 1 + n > len(b):
            break
        res.append((b[i + 1], b[i + 2:i + 1 + n]))
        i += 1 + n
    return res


def extrair_bpm(no) -> tuple[int | None, bytes | None]:
    """Procura o manufacturer data da Polar dentro do no e devolve (bpm, payload)."""
    for b in todos_bytes(no):
        for tipo, d in parse_ad(b):
            if tipo == 0xFF and len(d) >= 2:
                company = d[0] | (d[1] << 8)
                if company == POLAR_COMPANY_ID:
                    payload = d[2:]
                    if len(payload) > BYTE_BPM:
                        return payload[BYTE_BPM], bytes(payload)
                    if payload:
                        return payload[-1], bytes(payload)
    return None, None


def _zigzag(v: int) -> int:
    """Decodifica varints sint32 do Protobuf (ZigZag) para inteiros com sinal."""
    return (v >> 1) ^ -(v & 1)


def achar_rssi(no) -> tuple[int | None, int | None]:
    """Lê o RSSI do campo 4 (sint32, confirmado no AP real). Se o campo não existir ou
    estiver fora da faixa, cai na heurística antiga: primeiro varint que decodifica
    (ZigZag ou complemento de 2) em -120..-20 dBm. Devolve (rssi, numero_do_campo)."""
    for campo, wt, v in no:
        if campo == CAMPO_RSSI and wt == 0:
            rssi = _zigzag(v)
            if -120 <= rssi <= -20:
                return rssi, campo
            break
    for campo, wt, v in no:
        if wt == 0:
            s_zigzag = _zigzag(v)
            if -120 <= s_zigzag <= -20:
                return s_zigzag, campo
            s_direct = v - (1 << 64) if v >= (1 << 63) else v
            if -120 <= s_direct <= -20:
                return s_direct, campo
    return None, None


# ------------------------------------------------------------ API de alto nível
@dataclass(frozen=True, slots=True)
class Advertisement:
    mac: bytes
    bpm: int
    rssi: int | None
    payload: bytes
    radio_ap: bytes | None = None   # campo 6: identifica o AP que ouviu (útil com mais de um AP)


def achar_radio_ap(no) -> bytes | None:
    for campo, wt, v in no:
        if campo == CAMPO_RADIO_AP and wt == 2 and len(v) == 6:
            return bytes(v)
    return None


def decodificar_frame(frame: bytes, macs: frozenset[bytes] | set[bytes]) -> list[Advertisement]:
    """Extrai os advertisements Polar dos MACs informados. Entradas de inventário
    (sem advertisement) são ignoradas."""
    if not macs:
        return []
    res = []
    for mac, no in achar_nos_com_macs(frame, macs):
        bpm, payload = extrair_bpm(no)
        if bpm is None:
            continue
        rssi, _ = achar_rssi(no)
        res.append(Advertisement(mac, bpm, rssi, payload, achar_radio_ap(no)))
    return res


# --------------------------------------------------------------------- dump
def mostrar(buf: bytes, macs: frozenset[bytes] = frozenset(), indent: int = 0) -> None:
    """Imprime a árvore protobuf de um buffer (diagnóstico, --dump)."""
    _mostrar_campos(parse(buf), macs, indent)


def mostrar_no(no, macs: frozenset[bytes] = frozenset()) -> None:
    _mostrar_campos(no, macs, 0)


def _mostrar_campos(campos, macs, indent):
    pad = "  " * indent
    for campo, wt, v in campos:
        if wt == 0:
            print(f"{pad}[{campo}] varint = {v}")
        elif wt == 2:
            if v in macs:
                print(f"{pad}[{campo}] bytes = {v.hex()}   <-- MAC DA POLAR")
            elif len(v) >= 3 and all(32 <= c < 127 for c in v):
                print(f"{pad}[{campo}] string = {v.decode()!r}")
            elif len(v) >= 4 and parse(v, strict=True):
                print(f"{pad}[{campo}] mensagem ({len(v)} bytes):")
                _mostrar_campos(parse(v), macs, indent + 1)
            else:
                extra = ""
                ad = parse_ad(v)
                if ad and sum(1 + len(d) + 1 for _, d in ad) == len(v):
                    extra = "   (AD: " + ", ".join(f"0x{t:02x}:{d.hex()}" for t, d in ad) + ")"
                print(f"{pad}[{campo}] bytes({len(v)}) = {v.hex()}{extra}")
        else:
            print(f"{pad}[{campo}] fixed(wt={wt}) = {v.hex()}")
