"""Consultas de leituras de BPM para os gráficos."""
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_PONTOS = 720
PASSOS_S = (2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 21600, 86400)


def passo_automatico(de: datetime, ate: datetime, max_pontos: int = MAX_PONTOS) -> int:
    """Menor passo 'redondo' que deixa a série com no máximo `max_pontos` pontos (com 1%
    de folga: '24 h' calculado no navegador chega alguns segundos maior)."""
    duracao = max((ate - de).total_seconds(), 1)
    for passo in PASSOS_S:
        if duracao / passo <= max_pontos * 1.01:
            return passo
    return PASSOS_S[-1]


async def agregado(sessao: AsyncSession, pulseira_id: int, de: datetime, ate: datetime,
                   passo_s: int) -> list[dict]:
    """BPM médio, mínimo e máximo por intervalo de `passo_s` segundos (date_bin)."""
    r = await sessao.execute(text("""
        SELECT date_bin(make_interval(secs => :passo), ts, :de) AS ts,
               avg(bpm)::float AS bpm_medio, min(bpm) AS bpm_min, max(bpm) AS bpm_max, count(*) AS n
        FROM leituras_bpm
        WHERE pulseira_id = :pid AND ts >= :de AND ts < :ate
        GROUP BY 1 ORDER BY 1
    """), {"passo": passo_s, "de": de, "ate": ate, "pid": pulseira_id})
    return [dict(linha._mapping) for linha in r]


async def recentes(sessao: AsyncSession, janela: timedelta) -> dict[int, list[tuple[float, int]]]:
    """Leituras brutas das pulseiras ativas na janela: {pulseira_id: [(epoch_s, bpm), ...]}."""
    r = await sessao.execute(text("""
        SELECT l.pulseira_id, extract(epoch FROM l.ts)::float AS t, l.bpm
        FROM leituras_bpm l JOIN pulseiras p ON p.id = l.pulseira_id
        WHERE l.ts >= now() - make_interval(secs => :segundos) AND p.ativa AND p.removida_em IS NULL
        ORDER BY l.ts
    """), {"segundos": janela.total_seconds()})
    series: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for pid, t, bpm in r:
        series[pid].append((t, bpm))
    return dict(series)


async def nomes_aps(sessao: AsyncSession) -> dict[int, str]:
    return {i: n for i, n in await sessao.execute(text("SELECT id, nome FROM aps"))}
