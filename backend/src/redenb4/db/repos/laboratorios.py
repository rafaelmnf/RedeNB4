"""Cadastro de laboratórios."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Experimento, Laboratorio
from .erros import VIOLACAO_UNICA, sqlstate


class LaboratorioDuplicado(Exception):
    pass


class LaboratorioNaoEncontrado(Exception):
    pass


class LaboratorioComExperimentos(Exception):
    pass


async def listar(sessao: AsyncSession) -> list[tuple[Laboratorio, int]]:
    """Laboratórios com o total de experimentos de cada um."""
    total = (
        select(func.count(Experimento.id))
        .where(Experimento.laboratorio_id == Laboratorio.id)
        .scalar_subquery()
    )
    q = select(Laboratorio, total).order_by(Laboratorio.nome)
    return [tuple(linha) for linha in (await sessao.execute(q)).all()]


async def total_experimentos(sessao: AsyncSession, laboratorio_id: int) -> int:
    return await sessao.scalar(
        select(func.count(Experimento.id)).where(Experimento.laboratorio_id == laboratorio_id)
    )


async def obter(sessao: AsyncSession, laboratorio_id: int) -> Laboratorio:
    lab = await sessao.get(Laboratorio, laboratorio_id)
    if lab is None:
        raise LaboratorioNaoEncontrado(laboratorio_id)
    return lab


async def _commit(sessao: AsyncSession, nome: str) -> None:
    try:
        await sessao.commit()
    except IntegrityError as exc:
        await sessao.rollback()
        if sqlstate(exc) == VIOLACAO_UNICA:
            raise LaboratorioDuplicado(nome) from None
        raise


async def cadastrar(sessao: AsyncSession, nome: str, descricao: str | None = None) -> Laboratorio:
    lab = Laboratorio(nome=nome.strip(), descricao=descricao)
    sessao.add(lab)
    await _commit(sessao, lab.nome)
    await sessao.refresh(lab)
    return lab


async def atualizar(sessao: AsyncSession, laboratorio_id: int, **campos) -> Laboratorio:
    lab = await obter(sessao, laboratorio_id)
    if "nome" in campos:
        campos["nome"] = campos["nome"].strip()
    for nome, valor in campos.items():
        setattr(lab, nome, valor)
    nome = lab.nome
    await _commit(sessao, nome)
    await sessao.refresh(lab)
    return lab


async def remover(sessao: AsyncSession, laboratorio_id: int) -> None:
    lab = await obter(sessao, laboratorio_id)
    if await total_experimentos(sessao, laboratorio_id):
        raise LaboratorioComExperimentos(laboratorio_id)
    await sessao.delete(lab)
    await sessao.commit()
