"""Consultas dos gráficos: série agregada (date_bin) e janela recente."""
from datetime import UTC, datetime, timedelta

from redenb4.db.models import LeituraBpm
from redenb4.db.repos import leituras as repo
from redenb4.db.repos import pulseiras as repo_puls

T0 = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def test_passo_automatico_respeita_o_limite():
    assert repo.passo_automatico(T0, T0 + timedelta(hours=1)) == 5          # 720 pontos
    assert repo.passo_automatico(T0, T0 + timedelta(hours=24)) == 120       # 720 pontos
    assert repo.passo_automatico(T0, T0 + timedelta(minutes=5)) == 2
    # o navegador calcula "24 h atrás" alguns segundos antes de o servidor fixar o "agora"
    assert repo.passo_automatico(T0, T0 + timedelta(hours=24, seconds=3)) == 120
    for horas in (1, 3, 24, 24 * 7, 24 * 31):
        passo = repo.passo_automatico(T0, T0 + timedelta(hours=horas))
        assert horas * 3600 / passo <= repo.MAX_PONTOS * 1.01


async def test_agregado_por_intervalo(fabrica):
    async with fabrica() as s:
        p = await repo_puls.cadastrar(s, "A0:9E:1A:00:00:01", None)
        outra = await repo_puls.cadastrar(s, "A0:9E:1A:00:00:02", None)
        # dois baldes de 10 s: [60, 70, 80] e [100]; a outra pulseira não entra
        for seg, bpm in ((0, 60), (4, 70), (9, 80), (10, 100)):
            s.add(LeituraBpm(ts=T0 + timedelta(seconds=seg), pulseira_id=p.id, bpm=bpm))
        s.add(LeituraBpm(ts=T0, pulseira_id=outra.id, bpm=200))
        s.add(LeituraBpm(ts=T0 + timedelta(seconds=30), pulseira_id=p.id, bpm=50))   # fora do período
        await s.commit()
        pontos = await repo.agregado(s, p.id, T0, T0 + timedelta(seconds=20), 10)
    assert [(x["ts"], x["bpm_medio"], x["bpm_min"], x["bpm_max"], x["n"]) for x in pontos] == [
        (T0, 70.0, 60, 80, 3),
        (T0 + timedelta(seconds=10), 100.0, 100, 100, 1),
    ]


async def test_recentes_so_ativas_e_dentro_da_janela(fabrica):
    agora = datetime.now(UTC)
    async with fabrica() as s:
        ativa = await repo_puls.cadastrar(s, "A0:9E:1A:00:00:01", None)
        inativa = await repo_puls.cadastrar(s, "A0:9E:1A:00:00:02", None)
        s.add(LeituraBpm(ts=agora - timedelta(minutes=2), pulseira_id=ativa.id, bpm=70))
        s.add(LeituraBpm(ts=agora - timedelta(minutes=1), pulseira_id=ativa.id, bpm=72))
        s.add(LeituraBpm(ts=agora - timedelta(minutes=30), pulseira_id=ativa.id, bpm=90))   # antiga
        s.add(LeituraBpm(ts=agora - timedelta(minutes=1), pulseira_id=inativa.id, bpm=80))
        await s.commit()
        await repo_puls.atualizar(s, inativa.id, ativa=False)
        series = await repo.recentes(s, timedelta(minutes=5))
    assert list(series) == [ativa.id]
    assert [bpm for _, bpm in series[ativa.id]] == [70, 72]
    assert abs(series[ativa.id][-1][0] - (agora - timedelta(minutes=1)).timestamp()) < 1
