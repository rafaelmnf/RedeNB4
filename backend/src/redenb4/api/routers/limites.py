"""Limites globais dos alertas. Alterar vale na hora para o motor (próxima leitura)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.repos import limites as repo
from ..deps import obter_sessao
from ..schemas import LimitesEntrada, LimitesSaida

router = APIRouter(prefix="/api/limites", tags=["alertas"])


@router.get("", response_model=LimitesSaida)
async def obter(request: Request, sessao: AsyncSession = Depends(obter_sessao)):
    return await repo.obter_ou_criar(sessao, request.app.state.config)


@router.put("", response_model=LimitesSaida)
async def atualizar(dados: LimitesEntrada, request: Request, sessao: AsyncSession = Depends(obter_sessao)):
    lim = await repo.atualizar(sessao, request.app.state.config, **dados.model_dump())
    request.app.state.alertas.motor.definir_limites(repo.para_dominio(lim))
    return lim
