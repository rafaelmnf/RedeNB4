"""Vínculos pulseira ↔ pesquisador.

Regras (garantidas no banco pelas constraints EXCLUDE da migração 0002):
- uma pulseira tem no máximo uma pessoa por vez, e uma pessoa no máximo uma pulseira;
- o início é sempre o momento da criação (now()); encerrar grava fim = now();
- vínculos nunca são apagados nem reescritos: só INSERT e UPDATE de 'fim' no ativo.
"""
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..models import Atribuicao, Pesquisador, Pulseira
from .erros import VIOLACAO_EXCLUSAO, sqlstate


class AtribuicaoConflito(Exception):
    """A pulseira ou a pessoa já tem um vínculo ativo."""


class AtribuicaoInvalida(Exception):
    """Pulseira ou pessoa inexistente ou desativada."""


class AtribuicaoNaoEncontrada(Exception):
    pass


class AtribuicaoJaEncerrada(Exception):
    pass


def _com_nomes(q):
    return q.options(joinedload(Atribuicao.pulseira), joinedload(Atribuicao.pesquisador))


def nome_pulseira(p: Pulseira) -> str:
    return p.apelido or str(p.mac).upper()


async def listar(sessao: AsyncSession, ativa: bool | None = None, pulseira_id: int | None = None,
                 pesquisador_id: int | None = None) -> list[Atribuicao]:
    q = _com_nomes(select(Atribuicao)).order_by(Atribuicao.inicio.desc(), Atribuicao.id.desc())
    if ativa is True:
        q = q.where(Atribuicao.fim.is_(None))
    elif ativa is False:
        q = q.where(Atribuicao.fim.is_not(None))
    if pulseira_id is not None:
        q = q.where(Atribuicao.pulseira_id == pulseira_id)
    if pesquisador_id is not None:
        q = q.where(Atribuicao.pesquisador_id == pesquisador_id)
    return list((await sessao.scalars(q)).all())


async def ativas(sessao: AsyncSession) -> list[Atribuicao]:
    return await listar(sessao, ativa=True)


async def obter(sessao: AsyncSession, atribuicao_id: int) -> Atribuicao:
    a = await sessao.scalar(_com_nomes(select(Atribuicao)).where(Atribuicao.id == atribuicao_id))
    if a is None:
        raise AtribuicaoNaoEncontrada(atribuicao_id)
    return a


async def _mensagem_conflito(sessao: AsyncSession, pulseira: Pulseira, pesquisador: Pesquisador) -> str | None:
    q = _com_nomes(select(Atribuicao)).where(
        Atribuicao.fim.is_(None),
        (Atribuicao.pulseira_id == pulseira.id) | (Atribuicao.pesquisador_id == pesquisador.id),
    )
    for a in (await sessao.scalars(q)).all():
        if a.pulseira_id == pulseira.id:
            return f"A pulseira {nome_pulseira(pulseira)} já está com {a.pesquisador.nome}. Desvincule antes."
        return f"{pesquisador.nome} já está com a pulseira {nome_pulseira(a.pulseira)}. Desvincule antes."
    return None


async def criar(sessao: AsyncSession, pulseira_id: int, pesquisador_id: int) -> Atribuicao:
    pulseira = await sessao.get(Pulseira, pulseira_id)
    if pulseira is None or pulseira.removida_em is not None:
        raise AtribuicaoInvalida(f"Pulseira {pulseira_id} não encontrada")
    if not pulseira.ativa:
        raise AtribuicaoInvalida(f"A pulseira {nome_pulseira(pulseira)} está desativada")
    pesquisador = await sessao.get(Pesquisador, pesquisador_id)
    if pesquisador is None:
        raise AtribuicaoInvalida(f"Pesquisador {pesquisador_id} não encontrado")
    if not pesquisador.ativo:
        raise AtribuicaoInvalida(f"{pesquisador.nome} está desativado(a)")

    # Checagem prévia só para dar uma mensagem clara; quem garante é a EXCLUDE.
    if msg := await _mensagem_conflito(sessao, pulseira, pesquisador):
        raise AtribuicaoConflito(msg)

    a = Atribuicao(pulseira_id=pulseira_id, pesquisador_id=pesquisador_id)
    sessao.add(a)
    try:
        await sessao.commit()
    except IntegrityError as exc:
        await sessao.rollback()
        if sqlstate(exc) == VIOLACAO_EXCLUSAO:   # corrida entre duas requisições
            raise AtribuicaoConflito(
                await _mensagem_conflito(sessao, pulseira, pesquisador) or "Vínculo conflitante"
            ) from None
        raise
    return await obter(sessao, a.id)


async def encerrar(sessao: AsyncSession, atribuicao_id: int) -> Atribuicao:
    a = await sessao.get(Atribuicao, atribuicao_id)
    if a is None:
        raise AtribuicaoNaoEncontrada(atribuicao_id)
    if a.fim is not None:
        raise AtribuicaoJaEncerrada(atribuicao_id)
    await sessao.execute(
        update(Atribuicao)
        .where(Atribuicao.id == atribuicao_id, Atribuicao.fim.is_(None))
        .values(fim=func.now())
    )
    await sessao.commit()
    sessao.expire(a)
    return await obter(sessao, atribuicao_id)


async def encerrar_ativas(sessao: AsyncSession, *, pulseira_id: int | None = None,
                          pesquisador_id: int | None = None) -> int:
    """Encerra o vínculo ativo da pulseira ou da pessoa, sem dar commit (faz parte da
    transação de quem chamou, ex.: desativar a pulseira). Devolve quantos encerrou."""
    if (pulseira_id is None) == (pesquisador_id is None):
        raise ValueError("informe pulseira_id ou pesquisador_id")
    filtro = (Atribuicao.pulseira_id == pulseira_id) if pulseira_id is not None \
        else (Atribuicao.pesquisador_id == pesquisador_id)
    r = await sessao.execute(update(Atribuicao).where(filtro, Atribuicao.fim.is_(None)).values(fim=func.now()))
    return r.rowcount


async def teve_atribuicao(sessao: AsyncSession, *, pulseira_id: int | None = None,
                          pesquisador_id: int | None = None) -> bool:
    q = select(Atribuicao.id).limit(1)
    if pulseira_id is not None:
        q = q.where(Atribuicao.pulseira_id == pulseira_id)
    if pesquisador_id is not None:
        q = q.where(Atribuicao.pesquisador_id == pesquisador_id)
    return (await sessao.scalar(q)) is not None
