# Lista todos os serviços que a pulseira disponibiliza

import asyncio
import sys
from pathlib import Path

from bleak import BleakClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from device_config import load_polar_macs

POLAR_MACS = load_polar_macs()

# UUID Padrão GATT de Heart Rate
HR_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

def hr_data_handler(sender, data):
    """
    Handler universal para decodificação de pacotes GATT / PMD
    """
    # Exibe os bytes brutos recebidos para sabermos que os dados estão chegando
    raw_bytes = [hex(b) for b in data]
    print(f"📦 Pacote recebido ({len(data)} bytes): {raw_bytes}")
    
    flags = data[0]
    is_16bit_hr = flags & 0x01
    rr_present = flags & 0x10

    if is_16bit_hr:
        hr = int.from_bytes(data[1:3], byteorder='little')
        offset = 3
    else:
        hr = data[1]
        offset = 2

    print(f"   ❤️ BPM: {hr}")

    if rr_present:
        while offset + 2 <= len(data):
            raw_rr = int.from_bytes(data[offset:offset+2], byteorder='little')
            rr_ms = (raw_rr / 1024.0) * 1000.0
            print(f"   ⏱️ Intervalo R-R: {rr_ms:.1f} ms")
            offset += 2
    print("-" * 40)

async def main():
    for polar_mac in POLAR_MACS:
        print(f"Conectando e inspecionando o Polar Verity Sense ({polar_mac})...")
        client = BleakClient(polar_mac, timeout=20.0)

        try:
            await client.connect()
            print("✅ Conectado! Listando serviços e características disponíveis:\n")

            for service in client.services:
                print(f"🔹 Serviço: {service.uuid} ({service.description})")
                for char in service.characteristics:
                    props = ", ".join(char.properties)
                    print(f"    └─ Característica: {char.uuid} [{props}]")

            print("\n" + "="*50)
            print("Iniciando escuta no serviço de Frequência Cardíaca Padrão (0x2A37)...")
            print(" Mantenha a pulseira no braço bem ajustada!")
            print("="*50 + "\n")

            await client.start_notify(HR_MEASUREMENT_UUID, hr_data_handler)
            await asyncio.sleep(30.0)
            await client.stop_notify(HR_MEASUREMENT_UUID)

        except Exception as e:
            print(f"❌ Erro durante a operação com {polar_mac}: {e}")
        finally:
            if client.is_connected:
                await client.disconnect()
                print("\nConexão encerrada.")

if __name__ == "__main__":
    asyncio.run(main())