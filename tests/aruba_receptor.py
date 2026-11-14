import asyncio
import json
import base64
import sys
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from device_config import load_polar_macs

POLAR_MACS = frozenset(load_polar_macs())

async def aruba_handler(websocket):
    print(f"🔗 Conexão estabelecida com o AP Aruba! Recebendo dados...")
    
    try:
        async for message in websocket:
            try:
                # O Aruba envia os dados envelopados em JSON
                data = json.loads(message)
                
                # A lista de todos os dispositivos BLE que o AP está escutando
                ble_devices = data.get("bleData", [])
                
                for device in ble_devices:
                    mac = device.get("mac", "").upper()
                    
                    if mac in POLAR_MACS:
                        rssi = device.get("rssi", 0)
                        
                        # O payload de rádio (Manufacturer Data) vem em Base64
                        payload_b64 = device.get("data", "")
                        
                        if payload_b64:
                            # Decodificamos o Base64 para Bytes Hexadecimais
                            raw_bytes = base64.b64decode(payload_b64)
                            
                            # O BPM fica sempre no ÚLTIMO byte da mensagem do Broadcast da Polar
                            if len(raw_bytes) > 0:
                                bpm = raw_bytes[-1]
                                
                                # Filtra leituras vazias/desligadas
                                if bpm > 0:
                                    print(f"📡 Sinal (AP): {rssi} dBm | ❤️ Batimento: {bpm} BPM")

            except json.JSONDecodeError:
                continue # Ignora mensagens malformadas

    except websockets.exceptions.ConnectionClosed:
        print("❌ Conexão encerrada pelo AP.")

async def main():
    HOST = "0.0.0.0" # Escuta em todas as placas de rede do notebook
    PORT = 8080
    
    print(f"🚀 Servidor Middleware Iniciado!")
    print(f"Aguardando o AP Aruba se conectar na porta {PORT}...\n")
    print("Dica: Certifique-se de que o Firewall do Windows não está bloqueando a porta 8080.")
    
    async with websockets.serve(aruba_handler, HOST, PORT):
        await asyncio.Future() # Mantém o servidor rodando para sempre

if __name__ == "__main__":
    asyncio.run(main())