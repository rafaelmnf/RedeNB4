"""Consulta da auditoria (só admin)."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.repos import auditoria as repo
from ..deps import exigir_admin, obter_sessao
from ..schemas import AuditoriaSaida

router = APIRouter(prefix="/api/auditoria", tags=["auditoria"], dependencies=[Depends(exigir_admin)])


@router.get("", response_model=list[AuditoriaSaida])
async def listar(usuario_id: int | None = None, acao: str | None = None, de: datetime | None = None,
                 ate: datetime | None = None, limite: int = Query(500, ge=1, le=5000),
                 sessao: AsyncSession = Depends(obter_sessao)):
    """`acao` filtra pelo começo (ex.: 'pulseira' traz pulseira.criar, pulseira.editar...)."""
    return [
        AuditoriaSaida(id=r.id, ts=r.ts, usuario_id=r.usuario_id, usuario=nome, email=email, acao=r.acao,
                       entidade=r.entidade, entidade_id=r.entidade_id, detalhes=r.detalhes)
        for r, nome, email in await repo.listar(sessao, usuario_id, acao, de, ate, limite)
    ]


@router.get("/acoes", response_model=list[str])
async def acoes(sessao: AsyncSession = Depends(obter_sessao)):
    return await repo.acoes(sessao)
