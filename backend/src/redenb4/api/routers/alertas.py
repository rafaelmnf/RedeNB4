"""Alertas: lista (abertos ou histórico) e reconhecimento."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Usuario
from ...db.repos import alertas as repo
from ..deps import obter_sessao, registrar_auditoria, usuario_atual
from ..schemas import AlertaSaida

router = APIRouter(prefix="/api/alertas", tags=["alertas"], dependencies=[Depends(usuario_atual)])


@router.get("", response_model=list[AlertaSaida])
async def listar(abertos: bool | None = None, pulseira_id: int | None = None, pesquisador_id: int | None = None,
                 de: datetime | None = None, ate: datetime | None = None, limite: int = Query(500, ge=1, le=5000),
                 sessao: AsyncSession = Depends(obter_sessao)):
    return await repo.listar(sessao, abertos, pulseira_id, pesquisador_id, de, ate, limite)


@router.post("/{alerta_id}/reconhecer", response_model=AlertaSaida)
async def reconhecer(alerta_id: int, request: Request, usuario: Usuario = Depends(usuario_atual)):
    """Marca o alerta como visto (admin ou leitor). Ele continua aberto até a condição acabar."""
    try:
        alerta = await request.app.state.alertas.reconhecer(alerta_id, f"{usuario.nome} <{usuario.email}>")
    except repo.AlertaNaoEncontrado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Alerta {alerta_id} não encontrado") from None
    except repo.AlertaJaReconhecido:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este alerta já foi reconhecido") from None
    await registrar_auditoria(request, usuario.id, "alerta.reconhecer", "alerta", alerta_id,
                              {"tipo": alerta.tipo, "pesquisador": alerta.pesquisador, "pulseira": alerta.pulseira})
    return alerta
