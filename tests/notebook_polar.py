# Teste de conexão com o notebook via GATT, conexão direta.

import asyncio
from bleak import BleakClient

# Configuração
POLAR_MAC = "24:AC:AC:22:1D:A2"

# UUID padrão GATT para medição de Frequência Cardíaca (padrão internacional)
HR_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


def hr_data_handler(sender, data):
    """
    Função chamada automaticamente a cada novo pacote de dados recebido da pulseira.
    Decodifica a Frequência Cardíaca (BPM) e os Intervalos R-R (HRV).
    """
    flags = data[0]
    
    # Bit 0: Formato do HR (0 = 8 bits, 1 = 16 bits)
    is_16bit_hr = flags & 0x01 
    
    # Bit 4: Presença de dados R-R (0 = Ausente, 1 = Presente)
    rr_present = flags & 0x10

    # Extrai o BPM
    if is_16bit_hr:
        hr = int.from_bytes(data[1:3], byteorder='little')
        offset = 3
    else:
        hr = data[1]
        offset = 2

    print(f"❤️  Frequência Cardíaca: {hr} BPM")

    # Extrai os Intervalos R-R (em milissegundos)
    if rr_present:
        while offset < len(data):
            raw_rr = int.from_bytes(data[offset:offset+2], byteorder='little')
            # O padrão BLE define que a unidade R-R é 1/1024 segundos
            rr_ms = (raw_rr / 1024.0) * 1000.0
            print(f"   ⏱️  Intervalo R-R (HRV): {rr_ms:.1f} ms")
            offset += 2
    else:
        print("   (Aguardando presença de pacote R-R...)")
    
    print("-" * 40)


async def main():
    print(f"Conectando ao Polar Verity Sense ({POLAR_MAC})...")
    print("Certifique-se de que a pulseira está LIGADA e não conectada ao celular.\n")

    # Aumentamos o timeout para o driver do Windows não cancelar a conexão
    client = BleakClient(POLAR_MAC, timeout=20.0)

    try:
        print("Estabelecendo vínculo de comunicação...")
        await client.connect()
        
        # Tenta parear formalmente com o Windows se ainda não estiver pareado
        try:
            print("Solicitando pareamento com a pulseira...")
            await client.pair()
        except Exception as pair_err:
            # Se já estiver pareado ou a pulseira não exigir PIN, o Windows segue em frente
            print(f"Status do pareamento: {pair_err}")

        print("\n✅ Conectado com sucesso ao Polar!")
        print("Iniciando captura de dados por 30 segundos...\n")

        # Assina as notificações
        await client.start_notify(HR_MEASUREMENT_UUID, hr_data_handler)
        
        # Mantém rodando
        await asyncio.sleep(30.0)
        
        await client.stop_notify(HR_MEASUREMENT_UUID)
        print("\nCaptura finalizada.")

    except Exception as e:
        print(f"\n❌ Erro ao conectar com o dispositivo: {e}")
    
    finally:
        # Garante que a conexão seja fechada de forma limpa no Windows
        if client.is_connected:
            await client.disconnect()
            print("Conexão encerrada com sucesso.")


if __name__ == "__main__":
    asyncio.run(main())