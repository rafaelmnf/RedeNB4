"""Experimentos de cada laboratório: descrição, período e participantes. Não se ligam
à pulseira; um pesquisador pode participar de vários experimentos ao mesmo tempo."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.repos import experimentos as repo
from ..deps import obter_sessao
from ..schemas import ExperimentoAtualizar, ExperimentoCriar, ExperimentoSaida, ParticipanteSaida

router = APIRouter(prefix="/api/experimentos", tags=["experimentos"])


def _saida(e) -> ExperimentoSaida:
    return ExperimentoSaida(
        id=e.id,
        laboratorio_id=e.laboratorio_id,
        laboratorio=e.laboratorio.nome,
        nome=e.nome,
        descricao=e.descricao,
        inicio=e.inicio,
        fim=e.fim,
        situacao=repo.situacao(e),
        participantes=[ParticipanteSaida.model_validate(p) for p in e.participantes],
        criado_em=e.criado_em,
    )


def _nao_encontrado(experimento_id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Experimento {experimento_id} não encontrado")


def _invalido(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


@router.get("", response_model=list[ExperimentoSaida])
async def listar(laboratorio_id: int | None = None, situacao: repo.Situacao | None = None,
                 sessao: AsyncSession = Depends(obter_sessao)):
    return [_saida(e) for e in await repo.listar(sessao, laboratorio_id, situacao)]


@router.get("/{experimento_id}", response_model=ExperimentoSaida)
async def obter(experimento_id: int, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        return _saida(await repo.obter(sessao, experimento_id))
    except repo.ExperimentoNaoEncontrado:
        raise _nao_encontrado(experimento_id) from None


@router.post("", response_model=ExperimentoSaida, status_code=status.HTTP_201_CREATED)
async def criar(dados: ExperimentoCriar, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        return _saida(await repo.criar(sessao, **dados.model_dump()))
    except repo.ExperimentoInvalido as exc:
        raise _invalido(exc) from None


@router.patch("/{experimento_id}", response_model=ExperimentoSaida)
async def atualizar(experimento_id: int, dados: ExperimentoAtualizar,
                    sessao: AsyncSession = Depends(obter_sessao)):
    campos = dados.model_dump(exclude_unset=True)
    for obrigatorio in ("laboratorio_id", "nome", "inicio", "participantes"):   # não viram null
        if campos.get(obrigatorio, ...) is None:
            campos.pop(obrigatorio)
    try:
        return _saida(await repo.atualizar(sessao, experimento_id, **campos))
    except repo.ExperimentoNaoEncontrado:
        raise _nao_encontrado(experimento_id) from None
    except repo.ExperimentoInvalido as exc:
        raise _invalido(exc) from None


@router.post("/{experimento_id}/encerrar", response_model=ExperimentoSaida)
async def encerrar(experimento_id: int, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        return _saida(await repo.encerrar(sessao, experimento_id))
    except repo.ExperimentoNaoEncontrado:
        raise _nao_encontrado(experimento_id) from None
    except repo.ExperimentoJaEncerrado:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este experimento já foi encerrado") from None
    except repo.ExperimentoNaoIniciado:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Este experimento ainda não começou. Edite as datas em vez de encerrar.") from None


@router.delete("/{experimento_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover(experimento_id: int, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        await repo.remover(sessao, experimento_id)
    except repo.ExperimentoNaoEncontrado:
        raise _nao_encontrado(experimento_id) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
