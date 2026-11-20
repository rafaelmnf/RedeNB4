# Código usado para achar o endereço MAC da pulseira

import asyncio
from bleak import BleakScanner

async def discover():
    print("🔎 Escaneando dispositivos Bluetooth ao redor (aguarde 5 segundos)...")
    devices = await BleakScanner.discover()
    
    found = False
    for d in devices:
        # Procura por 'Polar' no nome do dispositivo
        if d.name and "Polar" in d.name:
            print("\n✅ ENCONTRADO O POLAR!")
            print(f"  📌 Nome do Dispositivo: {d.name}")
            print(f"  🔑 ENDEREÇO/UUID PARA USAR NO CÓDIGO: {d.address}")
            found = True
        elif d.name:
            # Mostra outros dispositivos com nome para ajudar caso o Polar esteja com outro nome
            print(f"  Dispositivo encontrado: {d.name} | Endereço: {d.address}")

    if not found:
        print("\n❌ Nenhum dispositivo Polar foi encontrado no scanner.")
        print("Dicas de solução de problemas:")
        print("1. A pulseira está LIGADA com os LEDs piscando?")
        print("2. Desconecte o app 'nRF Connect' ou 'Polar Flow' do seu celular (se o celular estiver conectado nela, ela fica invisível para o notebook).")
        print("3. O Bluetooth do seu notebook está ativado?")

if __name__ == "__main__":
    asyncio.run(discover())