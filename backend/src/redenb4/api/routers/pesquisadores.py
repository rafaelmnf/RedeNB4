"""Cadastro de pesquisadores. Desativar encerra o vínculo com a pulseira; excluir só é
permitido para quem nunca usou pulseira."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.repos import atribuicoes as repo_atr
from ...db.repos import pesquisadores as repo
from ..deps import obter_sessao
from ..schemas import PesquisadorAtualizar, PesquisadorCriar, PesquisadorSaida
from .vinculos import vinculo_pulseira

router = APIRouter(prefix="/api/pesquisadores", tags=["pesquisadores"])


async def _saida(sessao: AsyncSession, p) -> PesquisadorSaida:
    ativas = await repo_atr.listar(sessao, ativa=True, pesquisador_id=p.id)
    saida = PesquisadorSaida.model_validate(p)
    saida.atribuicao = vinculo_pulseira(ativas[0] if ativas else None)
    return saida


def _nao_encontrado(pesquisador_id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Pesquisador {pesquisador_id} não encontrado")


def _duplicado(email: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, f"Já existe um pesquisador com o e-mail {email}")


@router.get("", response_model=list[PesquisadorSaida])
async def listar(ativo: bool | None = None, sessao: AsyncSession = Depends(obter_sessao)):
    por_pesquisador = {a.pesquisador_id: a for a in await repo_atr.ativas(sessao)}
    saidas = []
    for p in await repo.listar(sessao, ativo):
        s = PesquisadorSaida.model_validate(p)
        s.atribuicao = vinculo_pulseira(por_pesquisador.get(p.id))
        saidas.append(s)
    return saidas


@router.get("/{pesquisador_id}", response_model=PesquisadorSaida)
async def obter(pesquisador_id: int, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        return await _saida(sessao, await repo.obter(sessao, pesquisador_id))
    except repo.PesquisadorNaoEncontrado:
        raise _nao_encontrado(pesquisador_id) from None


@router.post("", response_model=PesquisadorSaida, status_code=status.HTTP_201_CREATED)
async def cadastrar(dados: PesquisadorCriar, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        p = await repo.cadastrar(sessao, dados.nome, dados.email, dados.data_nascimento, dados.observacoes)
    except repo.PesquisadorDuplicado:
        raise _duplicado(dados.email) from None
    return await _saida(sessao, p)


@router.patch("/{pesquisador_id}", response_model=PesquisadorSaida)
async def atualizar(pesquisador_id: int, dados: PesquisadorAtualizar,
                    sessao: AsyncSession = Depends(obter_sessao)):
    campos = dados.model_dump(exclude_unset=True)
    for obrigatorio in ("nome", "email", "ativo"):   # não podem virar null
        if campos.get(obrigatorio, ...) is None:
            campos.pop(obrigatorio)
    try:
        return await _saida(sessao, await repo.atualizar(sessao, pesquisador_id, **campos))
    except repo.PesquisadorNaoEncontrado:
        raise _nao_encontrado(pesquisador_id) from None
    except repo.PesquisadorDuplicado:
        raise _duplicado(campos.get("email", "")) from None


@router.delete("/{pesquisador_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover(pesquisador_id: int, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        await repo.remover(sessao, pesquisador_id)
    except repo.PesquisadorNaoEncontrado:
        raise _nao_encontrado(pesquisador_id) from None
    except repo.PesquisadorComHistorico:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este pesquisador já usou pulseira e tem histórico de BPM. Desative em vez de excluir.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
