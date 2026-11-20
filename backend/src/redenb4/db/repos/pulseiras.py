"""Acesso a dados das pulseiras."""
from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...dominio.mac import normalizar_mac
from ..models import LeituraBpm, Pulseira


class PulseiraDuplicada(Exception):
    pass


class PulseiraNaoEncontrada(Exception):
    pass


async def listar(sessao: AsyncSession, incluir_removidas: bool = False) -> list[Pulseira]:
    q = select(Pulseira).order_by(Pulseira.id)
    if not incluir_removidas:
        q = q.where(Pulseira.removida_em.is_(None))
    return list((await sessao.scalars(q)).all())


async def listar_ativas(sessao: AsyncSession) -> list[Pulseira]:
    q = select(Pulseira).where(Pulseira.ativa.is_(True), Pulseira.removida_em.is_(None))
    return list((await sessao.scalars(q)).all())


async def obter(sessao: AsyncSession, pulseira_id: int) -> Pulseira:
    p = await sessao.get(Pulseira, pulseira_id)
    if p is None or p.removida_em is not None:
        raise PulseiraNaoEncontrada(pulseira_id)
    return p


async def cadastrar(sessao: AsyncSession, mac: str, apelido: str | None) -> Pulseira:
    """Cadastra um MAC. Se ele já existiu e foi removido, restaura o mesmo registro,
    preservando o histórico da pulseira física."""
    mac = normalizar_mac(mac)
    existente = await sessao.scalar(select(Pulseira).where(Pulseira.mac == mac))
    if existente is not None:
        if existente.removida_em is None:
            raise PulseiraDuplicada(mac)
        existente.removida_em = None
        existente.ativa = True
        existente.apelido = apelido
        p = existente
    else:
        p = Pulseira(mac=mac, apelido=apelido, ativa=True)
        sessao.add(p)
    await sessao.commit()
    await sessao.refresh(p)
    return p


async def atualizar(sessao: AsyncSession, pulseira_id: int, **campos) -> Pulseira:
    p = await obter(sessao, pulseira_id)
    for nome, valor in campos.items():
        setattr(p, nome, valor)
    await sessao.commit()
    await sessao.refresh(p)
    return p


async def tem_historico(sessao: AsyncSession, pulseira_id: int) -> bool:
    return bool(await sessao.scalar(select(exists().where(LeituraBpm.pulseira_id == pulseira_id))))


async def remover(sessao: AsyncSession, pulseira_id: int) -> str:
    """Remove a pulseira. Com histórico: soft delete. Sem histórico: DELETE.
    Devolve 'arquivada' ou 'excluida'."""
    p = await obter(sessao, pulseira_id)
    if await tem_historico(sessao, pulseira_id):
        p.removida_em = datetime.now(UTC)
        p.ativa = False
        resultado = "arquivada"
    else:
        await sessao.delete(p)
        resultado = "excluida"
    await sessao.commit()
    return resultado
