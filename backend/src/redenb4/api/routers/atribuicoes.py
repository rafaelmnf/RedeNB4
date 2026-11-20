"""Vínculos pulseira ↔ pesquisador (quem está usando a pulseira agora). Cada mudança
dispara NOTIFY, e as leituras seguintes já saem com o atribuicao_id novo."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.repos import atribuicoes as repo
from ..deps import obter_sessao
from ..schemas import AtribuicaoCriar, AtribuicaoSaida
from .vinculos import atribuicao_saida

router = APIRouter(prefix="/api/atribuicoes", tags=["atribuicoes"])


@router.get("", response_model=list[AtribuicaoSaida])
async def listar(ativa: bool | None = None, pulseira_id: int | None = None, pesquisador_id: int | None = None,
                 sessao: AsyncSession = Depends(obter_sessao)):
    return [atribuicao_saida(a) for a in await repo.listar(sessao, ativa, pulseira_id, pesquisador_id)]


@router.post("", response_model=AtribuicaoSaida, status_code=status.HTTP_201_CREATED)
async def criar(dados: AtribuicaoCriar, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        return atribuicao_saida(await repo.criar(sessao, dados.pulseira_id, dados.pesquisador_id))
    except repo.AtribuicaoConflito as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except repo.AtribuicaoInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


@router.post("/{atribuicao_id}/encerrar", response_model=AtribuicaoSaida)
async def encerrar(atribuicao_id: int, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        return atribuicao_saida(await repo.encerrar(sessao, atribuicao_id))
    except repo.AtribuicaoNaoEncontrada:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Vínculo {atribuicao_id} não encontrado") from None
    except repo.AtribuicaoJaEncerrada:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este vínculo já foi encerrado") from None
