"""
Servidor WebSocket para telemetria BLE do Aruba AP (InstantOS 8.10).

Decodifica o protobuf "cru" (sem precisar do aruba_iot_pb2.py), procura a
pulseira Polar Verity Sense e extrai o BPM do manufacturer data (ID 0x006B).

Uso:
    python servidor_ws.py            # modo normal: imprime BPM e grava CSV
    python servidor_ws.py --dump     # imprime a arvore protobuf da entrada da Polar
                                     # (use para descobrir onde esta o RSSI/BPM)
    python servidor_ws.py --raw      # alem disso, grava frames em raw_frames.bin
"""
import asyncio
import csv
import os
import sys
import time
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from device_config import load_polar_devices

HOST, PORT = "0.0.0.0", 8765
POLAR_DEVICES = tuple(
    (name, bytes.fromhex(mac.replace(":", ""))) for name, mac in load_polar_devices()
)
POLAR_MACS = tuple(mac for _, mac in POLAR_DEVICES)
POLAR_MAC_SET = frozenset(POLAR_MACS)
POLAR_COMPANY_ID = 0x006B                       # Polar Electro Oy
CSV_FILE = "bpm_log.csv"
RAW_FILE = "raw_frames.bin"
MAX_DUMPS = 3                                   # quantas entradas da Polar mostrar no --dump

DUMP = "--dump" in sys.argv
SAVE_RAW = "--raw" in sys.argv
_dumps_feitos = 0


# ---------------------------------------------------------------- protobuf cru
def _varint(buf, i):
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


def parse(buf, strict=False):
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


def achar_nos_com_mac(buf, mac, profundidade=0, tolerante=True):
    """Percorre recursivamente e devolve cada 'mensagem' que contem diretamente o MAC.
    O ultimo campo de cada nivel e lido de forma tolerante (o AP pode cortar o frame)."""
    campos = parse(buf, strict=not tolerante)
    if not campos or profundidade > 8:
        return []
    achados = []
    if any(wt == 2 and v == mac for _, wt, v in campos):
        achados.append(campos)
    ultimo = len(campos) - 1
    for idx, (_, wt, v) in enumerate(campos):
        if wt == 2 and len(v) >= 6 and v != mac:
            achados += achar_nos_com_mac(v, mac, profundidade + 1, tolerante=(idx == ultimo))
    return achados


def todos_bytes(campos, profundidade=0):
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
def parse_ad(b):
    """Divide um advertisement em estruturas AD: [(tipo, dados), ...]."""
    i, res = 0, []
    while i < len(b):
        n = b[i]
        if n == 0 or i + 1 + n > len(b):
            break
        res.append((b[i + 1], b[i + 2:i + 1 + n]))
        i += 1 + n
    return res


def extrair_bpm(no):
    """Procura o manufacturer data da Polar dentro do no e devolve (bpm, payload)."""
    for b in todos_bytes(no):
        for tipo, d in parse_ad(b):
            if tipo == 0xFF and len(d) >= 2:
                company = d[0] | (d[1] << 8)
                if company == POLAR_COMPANY_ID:
                    payload = d[2:]
                    if len(payload) >= 16:
                        return payload[15], payload
                    if payload:
                        return payload[-1], payload
    return None, None

def _zigzag(v):
    """Decodifica varints sint32 do Protobuf (ZigZag) para inteiros com sinal."""
    return (v >> 1) ^ -(v & 1)

def achar_rssi(no):
    """Procura o campo RSSI aplicando decodificação ZigZag nos varints."""
    for campo, wt, v in no:
        if wt == 0:
            # Tenta ler o varint com sint32 (ZigZag)
            s_zigzag = _zigzag(v)
            if -120 <= s_zigzag <= -20:
                return s_zigzag, campo
                
            # Tenta ler o varint com int32 direto (caso o AP envie como int32 em 2's complement)
            s_direct = v - (1 << 64) if v >= (1 << 63) else v
            if -120 <= s_direct <= -20:
                return s_direct, campo
                
    return None, None

# -------------------------------------------------------- Suavização e Distância
rssi_suavizado = {}
ALPHA = 0.25  # Fator de suavização (quanto menor, mais suave/estável; quanto maior, mais rápido reage)


def suavizar_rssi(mac, rssi_atual):
    """Aplica o filtro de Média Móvel Exponencial (EMA) no RSSI bruto."""
    if rssi_atual is None:
        return None
    if mac not in rssi_suavizado:
        rssi_suavizado[mac] = float(rssi_atual)
    else:
        rssi_suavizado[mac] = (
            (ALPHA * rssi_atual) + ((1 - ALPHA) * rssi_suavizado[mac])
        )
    return round(rssi_suavizado[mac], 1)

def estimar_distancia(rssi, tx_power=-60, n=2.0):
    """
    Calcula a distância aproximada em metros.
    tx_power: RSSI de referência a exatamente 1 metro (padrão ~ -60 dBm).
    n: Coeficiente do ambiente (1.8 a 2.2 para salas fechadas).
    """
    if rssi is None:
        return None
    dist = 10 ** ((tx_power - rssi) / (10 * n))
    return round(dist, 2)

# --------------------------------------------------------------------- dump
def mostrar(buf, indent=0):
    pad = "  " * indent
    for campo, wt, v in parse(buf):
        if wt == 0:
            print(f"{pad}[{campo}] varint = {v}")
        elif wt == 2:
            if v in POLAR_MAC_SET:
                print(f"{pad}[{campo}] bytes = {v.hex()}   <-- MAC DA POLAR")
            elif len(v) >= 3 and all(32 <= c < 127 for c in v):
                print(f"{pad}[{campo}] string = {v.decode()!r}")
            elif len(v) >= 4 and parse(v, strict=True):
                print(f"{pad}[{campo}] mensagem ({len(v)} bytes):")
                mostrar(v, indent + 1)
            else:
                extra = ""
                ad = parse_ad(v)
                if ad and sum(1 + len(d) + 1 for _, d in ad) == len(v):
                    extra = "   (AD: " + ", ".join(f"0x{t:02x}:{d.hex()}" for t, d in ad) + ")"
                print(f"{pad}[{campo}] bytes({len(v)}) = {v.hex()}{extra}")
        else:
            print(f"{pad}[{campo}] fixed(wt={wt}) = {v.hex()}")


# ------------------------------------------------------------------ handler
async def handler(websocket):
    global _dumps_feitos
    peer = websocket.remote_address
    print(f"🔗 AP conectado: {peer}")
    novo_csv = not os.path.exists(CSV_FILE)
    n = 0
    ultimo_payload = {}
    with open(CSV_FILE, "a", newline="") as fcsv:
        w = csv.writer(fcsv)
        if novo_csv:
            w.writerow(
                ["hora", "mac", "bpm", "rssi_bruto", "rssi_suavizado", "distancia", "payload_hex"]
            )
        try:
            async for msg in websocket:
                n += 1
                if not isinstance(msg, bytes):
                    continue
                if SAVE_RAW:
                    with open(RAW_FILE, "ab") as f:
                        f.write(len(msg).to_bytes(4, "big") + msg)

                for device_name, mac in POLAR_DEVICES:
                    for no in achar_nos_com_mac(msg, mac):
                        bpm, payload = extrair_bpm(no)
                        if bpm is None:
                            continue                      # entrada de inventario (sem advertisement)

                        if DUMP and _dumps_feitos < MAX_DUMPS:
                            _dumps_feitos += 1
                            print(f"\n===== ENTRADA COM ADVERTISEMENT (frame #{n}) =====")
                            mostrar_no(no)
                            print("=========================================\n")

                        if payload == ultimo_payload.get(mac):
                            continue                      # mesmo advertisement repetido
                        ultimo_payload[mac] = payload

                        rssi_bruto, _ = achar_rssi(no)
                        if rssi_bruto is not None:
                            rssi_filtro = suavizar_rssi(mac, rssi_bruto)
                            distancia = estimar_distancia(rssi_filtro, tx_power=-60, n=2.0)

                            hora = time.strftime("%H:%M:%S")
                            if bpm == 0:
                                print(f"[{hora}] {device_name} ({mac.hex(':')}) fora do braço (BPM 0)")
                                continue

                            print(f"[{hora}] {device_name} ({mac.hex(':')}) | ❤️ {bpm} BPM | RSSI : {rssi_filtro:>5} dBm | Distância: {distancia:>4} m")
                            w.writerow(
                                [hora, mac.hex(":").upper(), bpm, rssi_bruto, rssi_filtro, distancia, payload.hex()]
                            )
                        fcsv.flush()
        except websockets.exceptions.ConnectionClosed:
            print("❌ Conexão encerrada pelo AP.")


def mostrar_no(no):
    """Imprime os campos de um no ja parseado (reaproveita 'mostrar' reserializando)."""
    for campo, wt, v in no:
        if wt == 0:
            print(f"[{campo}] varint = {v}")
        elif wt == 2:
            if v in POLAR_MAC_SET:
                print(f"[{campo}] bytes = {v.hex()}   <-- MAC DA POLAR")
            elif len(v) >= 4 and parse(v, strict=True):
                print(f"[{campo}] mensagem ({len(v)} bytes):")
                mostrar(v, 1)
            else:
                ad = parse_ad(v)
                extra = ""
                if ad and sum(1 + len(d) + 1 for _, d in ad) == len(v):
                    extra = "   (AD: " + ", ".join(f"0x{t:02x}:{d.hex()}" for t, d in ad) + ")"
                print(f"[{campo}] bytes({len(v)}) = {v.hex()}{extra}")
        else:
            print(f"[{campo}] fixed(wt={wt}) = {v.hex()}")


async def main():
    print(f"🚀 Escutando em ws://{HOST}:{PORT}/telemetry  ({len(POLAR_MACS)} dispositivos configurados)")
    print("Dispositivos: " + ", ".join(name for name, _ in POLAR_DEVICES))
    if DUMP:
        print("Modo --dump ativo: vou mostrar a estrutura das primeiras entradas da Polar.")
    async with websockets.serve(handler, HOST, PORT, max_size=None):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor encerrado.")