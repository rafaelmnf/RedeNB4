"""Experimentos de cada laboratório, com período e participantes.

O experimento não se liga à pulseira. O BPM de um experimento sai das atribuições
dos participantes dentro do período (etapa de histórico). Um pesquisador pode estar
em vários experimentos ao mesmo tempo.
"""
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from ..models import Experimento, Laboratorio, Pesquisador, experimento_participantes
from .erros import VIOLACAO_CHECK, sqlstate

Situacao = Literal["agendado", "em_andamento", "encerrado"]


class ExperimentoNaoEncontrado(Exception):
    pass


class ExperimentoInvalido(Exception):
    """Laboratório ou pesquisador inexistente, ou período inválido."""


class ExperimentoJaEncerrado(Exception):
    pass


class ExperimentoNaoIniciado(Exception):
    pass


def situacao(e: Experimento, agora: datetime | None = None) -> Situacao:
    agora = agora or datetime.now(UTC)
    if e.inicio > agora:
        return "agendado"
    if e.fim is not None and e.fim <= agora:
        return "encerrado"
    return "em_andamento"


def _carregado(q):
    return q.options(joinedload(Experimento.laboratorio), selectinload(Experimento.participantes))


async def listar(sessao: AsyncSession, laboratorio_id: int | None = None,
                 situacao_: Situacao | None = None) -> list[Experimento]:
    q = _carregado(select(Experimento)).order_by(Experimento.inicio.desc(), Experimento.id.desc())
    if laboratorio_id is not None:
        q = q.where(Experimento.laboratorio_id == laboratorio_id)
    agora = func.now()
    if situacao_ == "agendado":
        q = q.where(Experimento.inicio > agora)
    elif situacao_ == "em_andamento":
        q = q.where(Experimento.inicio <= agora, (Experimento.fim.is_(None)) | (Experimento.fim > agora))
    elif situacao_ == "encerrado":
        q = q.where(Experimento.fim <= agora)
    return list((await sessao.scalars(q)).unique().all())


async def obter(sessao: AsyncSession, experimento_id: int) -> Experimento:
    e = await sessao.scalar(
        _carregado(select(Experimento)).where(Experimento.id == experimento_id).execution_options(
            populate_existing=True)
    )
    if e is None:
        raise ExperimentoNaoEncontrado(experimento_id)
    return e


async def _participantes(sessao: AsyncSession, ids: list[int]) -> list[Pesquisador]:
    ids = list(dict.fromkeys(ids))
    if not ids:
        return []
    encontrados = list((await sessao.scalars(select(Pesquisador).where(Pesquisador.id.in_(ids)))).all())
    faltando = set(ids) - {p.id for p in encontrados}
    if faltando:
        raise ExperimentoInvalido(f"Pesquisador(es) não encontrado(s): {sorted(faltando)}")
    return encontrados


async def _validar_laboratorio(sessao: AsyncSession, laboratorio_id: int) -> None:
    if await sessao.get(Laboratorio, laboratorio_id) is None:
        raise ExperimentoInvalido(f"Laboratório {laboratorio_id} não encontrado")


async def _commit(sessao: AsyncSession) -> None:
    try:
        await sessao.commit()
    except IntegrityError as exc:
        await sessao.rollback()
        if sqlstate(exc) == VIOLACAO_CHECK:
            raise ExperimentoInvalido("O fim deve ser depois do início") from None
        raise


async def criar(sessao: AsyncSession, laboratorio_id: int, nome: str, inicio: datetime,
                descricao: str | None = None, fim: datetime | None = None,
                participantes: list[int] | None = None) -> Experimento:
    await _validar_laboratorio(sessao, laboratorio_id)
    e = Experimento(laboratorio_id=laboratorio_id, nome=nome.strip(), descricao=descricao,
                    inicio=inicio, fim=fim)
    e.participantes = await _participantes(sessao, participantes or [])
    sessao.add(e)
    await _commit(sessao)
    return await obter(sessao, e.id)


async def atualizar(sessao: AsyncSession, experimento_id: int, participantes: list[int] | None = None,
                    **campos) -> Experimento:
    """Atualiza os campos informados. `participantes`, se informado, substitui a lista."""
    e = await obter(sessao, experimento_id)
    if "laboratorio_id" in campos:
        await _validar_laboratorio(sessao, campos["laboratorio_id"])
    if "nome" in campos:
        campos["nome"] = campos["nome"].strip()
    for nome, valor in campos.items():
        setattr(e, nome, valor)
    if participantes is not None:
        e.participantes = await _participantes(sessao, participantes)
    await _commit(sessao)
    return await obter(sessao, experimento_id)


async def encerrar(sessao: AsyncSession, experimento_id: int) -> Experimento:
    e = await obter(sessao, experimento_id)
    s = situacao(e)
    if s == "encerrado":
        raise ExperimentoJaEncerrado(experimento_id)
    if s == "agendado":
        raise ExperimentoNaoIniciado(experimento_id)
    e.fim = datetime.now(UTC)
    await _commit(sessao)
    return await obter(sessao, experimento_id)


async def remover(sessao: AsyncSession, experimento_id: int) -> None:
    e = await obter(sessao, experimento_id)
    await sessao.delete(e)      # participantes saem por ON DELETE CASCADE
    await sessao.commit()


async def participa_de_algum(sessao: AsyncSession, pesquisador_id: int) -> bool:
    return bool(await sessao.scalar(select(exists().where(
        experimento_participantes.c.pesquisador_id == pesquisador_id))))
