"""Cadastro de pulseiras. Toda alteração dispara NOTIFY no banco (trigger), que
atualiza a allowlist da ingestão sem reiniciar o servidor."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.repos import atribuicoes as repo_atr
from ...db.repos import pulseiras as repo
from ..ao_vivo import status_saida
from ..deps import obter_pipeline, obter_sessao
from ..schemas import PulseiraAtualizar, PulseiraCriar, PulseiraSaida, RemocaoSaida, StatusSaida
from .vinculos import vinculo_pesquisador

router = APIRouter(prefix="/api/pulseiras", tags=["pulseiras"])


def _status(pipeline, pulseira_id: int) -> StatusSaida | None:
    if pipeline is None:
        return None
    return status_saida(pipeline.status.get(pulseira_id), pipeline.config, pipeline.nomes_aps)


def _saida(p, pipeline, ativa=None) -> PulseiraSaida:
    saida = PulseiraSaida.model_validate(p)
    saida.atribuicao = vinculo_pesquisador(ativa)
    saida.status = _status(pipeline, p.id)
    return saida


async def _saida_unica(sessao: AsyncSession, p, pipeline) -> PulseiraSaida:
    ativas = await repo_atr.listar(sessao, ativa=True, pulseira_id=p.id)
    return _saida(p, pipeline, ativas[0] if ativas else None)


def _nao_encontrada(pulseira_id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Pulseira {pulseira_id} não encontrada")


@router.get("", response_model=list[PulseiraSaida])
async def listar(sessao: AsyncSession = Depends(obter_sessao), pipeline=Depends(obter_pipeline)):
    por_pulseira = {a.pulseira_id: a for a in await repo_atr.ativas(sessao)}
    return [_saida(p, pipeline, por_pulseira.get(p.id)) for p in await repo.listar(sessao)]


@router.get("/{pulseira_id}", response_model=PulseiraSaida)
async def obter(pulseira_id: int, sessao: AsyncSession = Depends(obter_sessao),
                pipeline=Depends(obter_pipeline)):
    try:
        return await _saida_unica(sessao, await repo.obter(sessao, pulseira_id), pipeline)
    except repo.PulseiraNaoEncontrada:
        raise _nao_encontrada(pulseira_id) from None


@router.post("", response_model=PulseiraSaida, status_code=status.HTTP_201_CREATED)
async def cadastrar(dados: PulseiraCriar, sessao: AsyncSession = Depends(obter_sessao),
                    pipeline=Depends(obter_pipeline)):
    try:
        p = await repo.cadastrar(sessao, dados.mac, dados.apelido)
    except repo.PulseiraDuplicada:
        raise HTTPException(status.HTTP_409_CONFLICT, f"O MAC {dados.mac} já está cadastrado") from None
    return await _saida_unica(sessao, p, pipeline)


@router.patch("/{pulseira_id}", response_model=PulseiraSaida)
async def atualizar(pulseira_id: int, dados: PulseiraAtualizar,
                    sessao: AsyncSession = Depends(obter_sessao), pipeline=Depends(obter_pipeline)):
    campos = dados.model_dump(exclude_unset=True)
    if campos.get("ativa") is None:
        campos.pop("ativa", None)
    try:
        return await _saida_unica(sessao, await repo.atualizar(sessao, pulseira_id, **campos), pipeline)
    except repo.PulseiraNaoEncontrada:
        raise _nao_encontrada(pulseira_id) from None


@router.delete("/{pulseira_id}", response_model=RemocaoSaida)
async def remover(pulseira_id: int, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        return RemocaoSaida(resultado=await repo.remover(sessao, pulseira_id))
    except repo.PulseiraNaoEncontrada:
        raise _nao_encontrada(pulseira_id) from None
