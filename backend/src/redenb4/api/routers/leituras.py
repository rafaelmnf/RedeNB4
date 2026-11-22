"""Leituras de BPM para os gráficos: janela recente (bruta) e histórico agregado."""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.repos import leituras as repo
from ..deps import obter_sessao
from ..schemas import PontoBpm, SerieBpm

router = APIRouter(prefix="/api/leituras", tags=["leituras"])

MAX_PERIODO = timedelta(days=31)


@router.get("/recentes", response_model=dict[int, list[tuple[float, int]]])
async def recentes(minutos: int = Query(15, ge=1, le=60), sessao: AsyncSession = Depends(obter_sessao)):
    """Pontos brutos `[epoch_s, bpm]` das pulseiras ativas, para preencher os gráficos ao vivo."""
    return await repo.recentes(sessao, timedelta(minutes=minutos))


@router.get("", response_model=SerieBpm)
async def serie(pulseira_id: int, de: datetime | None = None, ate: datetime | None = None,
                sessao: AsyncSession = Depends(obter_sessao)):
    """Série agregada (média, mínimo e máximo por intervalo). Padrão: última 1 h."""
    ate = ate or datetime.now(UTC)
    de = de or ate - timedelta(hours=1)
    if ate.tzinfo is None or de.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Informe as datas com fuso (ex.: ...Z)")
    if de >= ate:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "'de' deve ser antes de 'ate'")
    if ate - de > MAX_PERIODO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Período máximo: 31 dias")
    passo = repo.passo_automatico(de, ate)
    pontos = await repo.agregado(sessao, pulseira_id, de, ate, passo)
    return SerieBpm(pulseira_id=pulseira_id, de=de, ate=ate, passo_s=passo,
                    pontos=[PontoBpm(**p) for p in pontos])
