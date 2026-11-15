"""Simulador de pulseiras Polar: gera frames no formato do AP Aruba e envia pela
mesma porta de ingestão (ws://localhost:8765), passando pelo parser real.

    uv run redenb4 simular --n 5 --cadastrar
    uv run redenb4 simular --n 3 --alto 2 --sumir 3
"""
import asyncio
import json
import random
import urllib.error
import urllib.request

OUI_POLAR = bytes.fromhex("A09E1A")


# ------------------------------------------------------------ codificação protobuf
def _varint(v: int) -> bytes:
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _zigzag(v: int) -> int:
    return (v << 1) ^ (v >> 63)


def campo_varint(numero: int, valor: int) -> bytes:
    return _varint(numero << 3) + _varint(valor)


def campo_bytes(numero: int, valor: bytes) -> bytes:
    return _varint((numero << 3) | 2) + _varint(len(valor)) + valor


def mac_simulado(indice: int) -> bytes:
    return OUI_POLAR + indice.to_bytes(3, "big")


def advertisement_polar(bpm: int, sequencia: int) -> bytes:
    """Estruturas AD: flags + manufacturer data (0xFF) da Polar (0x006B), BPM no byte 15."""
    payload = bytearray(16)
    payload[0] = sequencia & 0xFF          # muda a cada envio (evita a deduplicação de payload)
    payload[15] = bpm & 0xFF
    manuf = b"\xff" + (0x006B).to_bytes(2, "little") + bytes(payload)
    return b"\x02\x01\x06" + bytes([len(manuf)]) + manuf


def entrada_dispositivo(mac: bytes, bpm: int | None, rssi: int, sequencia: int, nome: str) -> bytes:
    """Uma entrada de dispositivo; bpm=None gera só inventário (sem advertisement)."""
    corpo = campo_bytes(1, mac) + campo_bytes(2, nome.encode()) + campo_varint(3, 1_700_000_000 + sequencia)
    corpo += campo_varint(5, _zigzag(rssi))
    if bpm is not None:
        corpo += campo_bytes(9, advertisement_polar(bpm, sequencia))
    return corpo


def montar_frame(entradas: list[bytes]) -> bytes:
    cabecalho = campo_bytes(1, b"simulador-redenb4") + campo_varint(2, 1)
    return cabecalho + b"".join(campo_bytes(4, e) for e in entradas)


# ------------------------------------------------------------ simulação
class PulseiraSimulada:
    def __init__(self, indice: int):
        self.indice = indice
        self.mac = mac_simulado(indice)
        self.bpm = random.uniform(65, 85)
        self.rssi = random.uniform(-75, -55)
        self.modo = "normal"                # normal | alto | baixo | sumir | fora

    @property
    def mac_texto(self) -> str:
        return self.mac.hex(":").upper()

    def passo(self) -> tuple[int | None, int]:
        alvo = {"alto": 170, "baixo": 40}.get(self.modo, 75)
        self.bpm += (alvo - self.bpm) * 0.15 + random.gauss(0, 1.5)
        self.rssi = max(-95, min(-40, self.rssi + random.gauss(0, 1.5)))
        bpm = 0 if self.modo == "fora" else round(max(30, min(220, self.bpm)))
        return bpm, round(self.rssi)


def cadastrar(api: str, pulseiras: list[PulseiraSimulada]) -> None:
    for p in pulseiras:
        corpo = json.dumps({"mac": p.mac_texto, "apelido": f"Simulada {p.indice:02d}"}).encode()
        req = urllib.request.Request(f"{api}/api/pulseiras", data=corpo, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5):
                print(f"  + cadastrada {p.mac_texto}")
        except urllib.error.HTTPError as exc:
            print(f"  = {p.mac_texto}: {exc.code} {'já cadastrada' if exc.code == 409 else exc.reason}")
        except urllib.error.URLError as exc:
            raise SystemExit(f"API indisponível em {api}: {exc.reason}") from None


async def simular(url: str, n: int, intervalo: float, modos: dict[int, str], api: str | None) -> None:
    import websockets

    pulseiras = [PulseiraSimulada(i + 1) for i in range(n)]
    for p in pulseiras:
        p.modo = modos.get(p.indice, "normal")
    if api:
        cadastrar(api, pulseiras)
    print("Pulseiras simuladas:")
    for p in pulseiras:
        print(f"  {p.indice:2d}  {p.mac_texto}  modo={p.modo}")

    sequencia = 0
    while True:
        try:
            async with websockets.connect(url, max_size=None) as ws:
                print(f"Conectado a {url}; enviando a cada {intervalo}s (Ctrl+C para parar)")
                while True:
                    sequencia += 1
                    entradas = []
                    for p in pulseiras:
                        bpm, rssi = p.passo()
                        if p.modo != "sumir":
                            entradas.append(entrada_dispositivo(p.mac, bpm, rssi, sequencia, f"Polar Sense {p.indice}"))
                    # um dispositivo qualquer só de inventário, como o AP real manda
                    entradas.append(entrada_dispositivo(bytes.fromhex("112233445566"), None, -80, sequencia, "Outro"))
                    await ws.send(montar_frame(entradas))
                    await asyncio.sleep(intervalo)
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            print(f"Sem conexão com {url} ({exc}); tentando de novo em 3 s")
            await asyncio.sleep(3)


def executar(args) -> None:
    modos = {}
    for modo in ("alto", "baixo", "sumir", "fora"):
        for indice in getattr(args, modo) or []:
            modos[indice] = modo
    api = args.api if args.cadastrar else None
    try:
        asyncio.run(simular(args.url, args.n, args.intervalo, modos, api))
    except KeyboardInterrupt:
        print("\nSimulador encerrado.")
