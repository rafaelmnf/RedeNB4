"""Cadastro de pesquisadores (pessoas que usam as pulseiras)."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Pesquisador
from . import atribuicoes, experimentos
from .erros import VIOLACAO_UNICA, sqlstate


class PesquisadorDuplicado(Exception):
    pass


class PesquisadorNaoEncontrado(Exception):
    pass


class PesquisadorComHistorico(Exception):
    """Já usou pulseira ou participa de experimento: não pode ser excluído, só desativado."""


def normalizar_email(email: str) -> str:
    return email.strip().lower()


async def listar(sessao: AsyncSession, ativo: bool | None = None) -> list[Pesquisador]:
    q = select(Pesquisador).order_by(Pesquisador.nome, Pesquisador.id)
    if ativo is not None:
        q = q.where(Pesquisador.ativo.is_(ativo))
    return list((await sessao.scalars(q)).all())


async def obter(sessao: AsyncSession, pesquisador_id: int) -> Pesquisador:
    p = await sessao.get(Pesquisador, pesquisador_id)
    if p is None:
        raise PesquisadorNaoEncontrado(pesquisador_id)
    return p


async def _commit(sessao: AsyncSession, email: str) -> None:
    try:
        await sessao.commit()
    except IntegrityError as exc:
        await sessao.rollback()
        if sqlstate(exc) == VIOLACAO_UNICA:
            raise PesquisadorDuplicado(email) from None
        raise


async def cadastrar(sessao: AsyncSession, nome: str, email: str, data_nascimento: date | None = None,
                    observacoes: str | None = None) -> Pesquisador:
    email = normalizar_email(email)
    p = Pesquisador(nome=nome.strip(), email=email, data_nascimento=data_nascimento,
                    observacoes=observacoes, ativo=True)
    sessao.add(p)
    await _commit(sessao, email)
    await sessao.refresh(p)
    return p


async def atualizar(sessao: AsyncSession, pesquisador_id: int, **campos) -> Pesquisador:
    """Atualiza os campos informados. Desativar encerra o vínculo com a pulseira."""
    p = await obter(sessao, pesquisador_id)
    if "email" in campos:
        campos["email"] = normalizar_email(campos["email"])
    if "nome" in campos:
        campos["nome"] = campos["nome"].strip()
    for nome, valor in campos.items():
        setattr(p, nome, valor)
    if campos.get("ativo") is False:
        await atribuicoes.encerrar_ativas(sessao, pesquisador_id=pesquisador_id)
    await _commit(sessao, campos.get("email", p.email))
    await sessao.refresh(p)
    return p


async def remover(sessao: AsyncSession, pesquisador_id: int) -> None:
    """Exclui quem nunca usou pulseira nem participou de experimento. Os demais só
    podem ser desativados, para não perder o histórico."""
    p = await obter(sessao, pesquisador_id)
    if await atribuicoes.teve_atribuicao(sessao, pesquisador_id=pesquisador_id):
        raise PesquisadorComHistorico("Este pesquisador já usou pulseira e tem histórico de BPM.")
    if await experimentos.participa_de_algum(sessao, pesquisador_id):
        raise PesquisadorComHistorico("Este pesquisador participa de experimento.")
    await sessao.delete(p)
    await sessao.commit()
