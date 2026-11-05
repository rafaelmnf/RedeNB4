import asyncio
from bleak import BleakScanner

# O MAC da sua pulseira
POLAR_MAC = "24:AC:AC:22:1D:A2"

def escuta_passiva_callback(device, advertisement_data):
    """
    Filtra os pacotes no ar e extrai o BPM diretamente do payload Hexadecimal.
    """
    if device.address.upper() == POLAR_MAC.upper():
        
        forca_sinal = advertisement_data.rssi
        
        # ID 107 (0x006B) = Polar Electro Oy
        if 107 in advertisement_data.manufacturer_data:
            dados_polar = advertisement_data.manufacturer_data[107]
            
            # O pacote padrão de Broadcast do Verity Sense tem 16 bytes.
            # O batimento cardíaco é sempre transmitido no ÚLTIMO byte (índice 15).
            if len(dados_polar) >= 16:
                
                # Pegamos o byte na posição 15 (que equivale ao 16º item do array).
                # O Python já converte nativamente o byte de hex para decimal!
                bpm = dados_polar[15] 
                
                # Ignora leituras vazias (quando a pulseira está fora do braço, ela envia 0 BPM)
                if bpm > 0:
                    print(f"📡 Sinal: {forca_sinal} dBm | ❤️ Batimento: {bpm} BPM")

async def main():
    print("Iniciando Gateway em Modo BROADCAST (Escuta Passiva)...")
    print(f"Alvo: {POLAR_MAC}")
    print("A pulseira não será conectada, apenas 'ouvida' no ar.\n")

    scanner = BleakScanner(detection_callback=escuta_passiva_callback)
    
    try:
        await scanner.start()
        print("🎧 Escutando pacotes... (Pressione Ctrl+C para sair)")
        
        while True:
            await asyncio.sleep(1.0)
            
    except asyncio.CancelledError:
        pass
    finally:
        await scanner.stop()
        print("\nEscuta finalizada.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript parado pelo usuário.")