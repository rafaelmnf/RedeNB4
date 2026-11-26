"""Retenção das leituras: só o que passou do prazo é apagado, em lotes."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from redenb4.db.models import LeituraBpm
from redenb4.db.repos import leituras as repo
from redenb4.db.repos import pulseiras as repo_puls
from redenb4.servicos.limpeza import LimpezaLeituras


async def test_apaga_so_as_antigas_em_lotes(fabrica):
    agora = datetime.now(UTC)
    async with fabrica() as s:
        p = await repo_puls.cadastrar(s, "A0:9E:1A:00:00:01", None)
        for h in range(7):                      # 7 leituras velhas (3 a 9 dias)
            s.add(LeituraBpm(ts=agora - timedelta(days=3 + h), pulseira_id=p.id, bpm=70))
        for minutos in (1, 60, 47 * 60):        # 3 recentes (até 47 h)
            s.add(LeituraBpm(ts=agora - timedelta(minutes=minutos), pulseira_id=p.id, bpm=80))
        await s.commit()
        assert await repo.apagar_antigas(s, agora - timedelta(days=2), lote=3) == 7     # 3 + 3 + 1
        restantes = (await s.execute(select(func.count(), func.min(LeituraBpm.ts)))).one()
    assert restantes[0] == 3 and restantes[1] > agora - timedelta(days=2)


async def test_servico_usa_a_retencao_configurada(fabrica):
    agora = datetime.now(UTC)
    async with fabrica() as s:
        p = await repo_puls.cadastrar(s, "A0:9E:1A:00:00:01", None)
        s.add(LeituraBpm(ts=agora - timedelta(hours=30), pulseira_id=p.id, bpm=70))
        s.add(LeituraBpm(ts=agora - timedelta(hours=10), pulseira_id=p.id, bpm=70))
        await s.commit()
    assert await LimpezaLeituras(fabrica, retencao_dias=2).rodar_uma_vez() == 0
    assert await LimpezaLeituras(fabrica, retencao_dias=1).rodar_uma_vez() == 1
