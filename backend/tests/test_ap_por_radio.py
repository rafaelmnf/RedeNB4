"""O AP é identificado pelo MAC do rádio BLE (campo [6] de cada entrada), não pelo IP."""
from sqlalchemy import select

from redenb4.db.models import Ap
from redenb4.db.repos import pulseiras as repo_puls
from redenb4.dominio.mac import bytes_para_mac
from redenb4.ingestao.allowlist import Allowlist
from redenb4.ingestao.servidor_ap import ServidorAP
from redenb4.simulador import RADIO_AP_SIMULADO, entrada_dispositivo, mac_simulado, montar_frame


async def test_frame_registra_ap_pelo_radio_e_marca_as_leituras(fabrica):
    mac = mac_simulado(1)
    async with fabrica() as s:
        await repo_puls.cadastrar(s, bytes_para_mac(mac), None)
    al = Allowlist(fabrica)
    await al.recarregar()
    recebidas = []
    servidor = ServidorAP(al, recebidas.extend, fabrica)

    frame = montar_frame([entrada_dispositivo(mac, 75, -60, 1)])
    leituras = await servidor.processar_frame(frame)
    await servidor.processar_frame(montar_frame([entrada_dispositivo(mac, 76, -61, 2)]))

    radio = bytes_para_mac(RADIO_AP_SIMULADO)
    async with fabrica() as s:
        aps = (await s.scalars(select(Ap))).all()
    assert [a.identificador for a in aps] == [radio]          # um AP só, criado uma vez
    assert leituras[0].radio_ap == radio
    assert {x.ap_id for x in recebidas} == {aps[0].id}
