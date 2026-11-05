import asyncio
import json
import time
import websockets

HOST, PORT = "0.0.0.0", 8765
LOG_FILE = "aruba_dump.bin"

async def handler(websocket):
    # compatível com websockets >= 13 (request.path) e versões antigas
    path = getattr(getattr(websocket, "request", None), "path", "?")
    print(f"\n🔗 Conexão de {websocket.remote_address} | path={path}")
    try:
        print("Headers:", dict(websocket.request.headers))
    except Exception:
        pass

    n = 0
    try:
        async for message in websocket:
            n += 1
            ts = time.strftime("%H:%M:%S")
            if isinstance(message, bytes):
                print(f"[{ts}] #{n} BINÁRIO ({len(message)} bytes)")
                print("   hex:", message[:120].hex(), "..." if len(message) > 120 else "")
                with open(LOG_FILE, "ab") as f:
                    f.write(len(message).to_bytes(4, "big") + message)
                # indica se o MAC da pulseira aparece nos bytes
                mac_bytes = bytes.fromhex("24ACAC221DA2")
                print("   contém MAC da Polar?", mac_bytes in message)
            else:
                print(f"[{ts}] #{n} TEXTO ({len(message)} chars)")
                try:
                    print(json.dumps(json.loads(message), indent=2)[:1500])
                except json.JSONDecodeError:
                    print("   ", message[:500])
    except websockets.exceptions.ConnectionClosed:
        print("❌ Conexão encerrada.")

async def main():
    print(f"🚀 Escutando em {HOST}:{PORT} ...")
    async with websockets.serve(handler, HOST, PORT, max_size=None):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())