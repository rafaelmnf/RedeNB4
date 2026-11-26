"""Cadastro de laboratórios. Laboratório com experimentos não pode ser excluído."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.repos import laboratorios as repo
from ..deps import admin_auditado, obter_sessao, usuario_atual
from ..schemas import LaboratorioAtualizar, LaboratorioCriar, LaboratorioSaida

router = APIRouter(prefix="/api/laboratorios", tags=["laboratorios"], dependencies=[Depends(usuario_atual)])


async def _saida(sessao: AsyncSession, lab) -> LaboratorioSaida:
    saida = LaboratorioSaida.model_validate(lab)
    saida.total_experimentos = await repo.total_experimentos(sessao, lab.id)
    return saida


def _nao_encontrado(laboratorio_id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Laboratório {laboratorio_id} não encontrado")


def _duplicado(nome: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, f"Já existe um laboratório chamado {nome}")


@router.get("", response_model=list[LaboratorioSaida])
async def listar(sessao: AsyncSession = Depends(obter_sessao)):
    saidas = []
    for lab, total in await repo.listar(sessao):
        s = LaboratorioSaida.model_validate(lab)
        s.total_experimentos = total
        saidas.append(s)
    return saidas


@router.post("", response_model=LaboratorioSaida, status_code=status.HTTP_201_CREATED,
             dependencies=[admin_auditado("laboratorio.criar", "laboratorio")])
async def cadastrar(dados: LaboratorioCriar, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        return await _saida(sessao, await repo.cadastrar(sessao, dados.nome, dados.descricao))
    except repo.LaboratorioDuplicado:
        raise _duplicado(dados.nome) from None


@router.patch("/{laboratorio_id}", response_model=LaboratorioSaida,
             dependencies=[admin_auditado("laboratorio.editar", "laboratorio", "laboratorio_id")])
async def atualizar(laboratorio_id: int, dados: LaboratorioAtualizar,
                    sessao: AsyncSession = Depends(obter_sessao)):
    campos = dados.model_dump(exclude_unset=True)
    if campos.get("nome", ...) is None:
        campos.pop("nome")
    try:
        return await _saida(sessao, await repo.atualizar(sessao, laboratorio_id, **campos))
    except repo.LaboratorioNaoEncontrado:
        raise _nao_encontrado(laboratorio_id) from None
    except repo.LaboratorioDuplicado:
        raise _duplicado(campos.get("nome", "")) from None


@router.delete("/{laboratorio_id}", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[admin_auditado("laboratorio.remover", "laboratorio", "laboratorio_id")])
async def remover(laboratorio_id: int, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        await repo.remover(sessao, laboratorio_id)
    except repo.LaboratorioNaoEncontrado:
        raise _nao_encontrado(laboratorio_id) from None
    except repo.LaboratorioComExperimentos:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este laboratório tem experimentos. Exclua ou mova os experimentos antes.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
