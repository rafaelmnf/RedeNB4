"""Alertas gravados. Nunca são apagados: só abertos, atualizados (valor extremo),
encerrados (fim) e reconhecidos."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Alerta


class AlertaNaoEncontrado(Exception):
    pass


class AlertaJaReconhecido(Exception):
    pass


@dataclass
class AlertaCompleto:
    """Alerta com os nomes da pulseira e do pesquisador, para a API e o WebSocket."""

    id: int
    tipo: str
    pulseira_id: int
    pulseira: str
    pesquisador_id: int
    pesquisador: str
    atribuicao_id: int
    inicio: datetime
    fim: datetime | None
    valor: int | None
    limite: int | None
    reconhecido_em: datetime | None
    reconhecido_por: str | None


_SELECT = """
    SELECT a.id, a.tipo, a.pulseira_id, coalesce(p.apelido, upper(p.mac::text)) AS pulseira,
           a.pesquisador_id, q.nome AS pesquisador, a.atribuicao_id, a.inicio, a.fim, a.valor,
           a.limite, a.reconhecido_em, a.reconhecido_por
    FROM alertas a
    JOIN pulseiras p ON p.id = a.pulseira_id
    JOIN pesquisadores q ON q.id = a.pesquisador_id
"""


async def obter(sessao: AsyncSession, alerta_id: int) -> AlertaCompleto:
    linha = (await sessao.execute(text(_SELECT + " WHERE a.id = :id"), {"id": alerta_id})).first()
    if linha is None:
        raise AlertaNaoEncontrado(alerta_id)
    return AlertaCompleto(**linha._mapping)


async def listar(sessao: AsyncSession, abertos: bool | None = None, pulseira_id: int | None = None,
                 pesquisador_id: int | None = None, de: datetime | None = None, ate: datetime | None = None,
                 limite: int = 500) -> list[AlertaCompleto]:
    filtros, params = [], {"limite": limite}
    if abertos is True:
        filtros.append("a.fim IS NULL")
    elif abertos is False:
        filtros.append("a.fim IS NOT NULL")
    if pulseira_id is not None:
        filtros.append("a.pulseira_id = :pulseira_id")
        params["pulseira_id"] = pulseira_id
    if pesquisador_id is not None:
        filtros.append("a.pesquisador_id = :pesquisador_id")
        params["pesquisador_id"] = pesquisador_id
    if de is not None:       # alertas que estavam abertos em algum momento do período
        filtros.append("(a.fim IS NULL OR a.fim >= :de)")
        params["de"] = de
    if ate is not None:
        filtros.append("a.inicio < :ate")
        params["ate"] = ate
    where = (" WHERE " + " AND ".join(filtros)) if filtros else ""
    r = await sessao.execute(text(_SELECT + where + " ORDER BY a.inicio DESC, a.id DESC LIMIT :limite"), params)
    return [AlertaCompleto(**linha._mapping) for linha in r]


async def abrir(sessao: AsyncSession, tipo: str, atribuicao_id: int, inicio: datetime, valor: int | None,
                limite: int | None) -> int:
    """Abre o alerta; pulseira e pesquisador vêm da atribuição."""
    novo_id = await sessao.scalar(text("""
        INSERT INTO alertas (tipo, pulseira_id, pesquisador_id, atribuicao_id, inicio, valor, limite)
        SELECT :tipo, pulseira_id, pesquisador_id, id, :inicio, :valor, :limite
        FROM atribuicoes WHERE id = :atribuicao_id
        RETURNING id
    """), {"tipo": tipo, "atribuicao_id": atribuicao_id, "inicio": inicio, "valor": valor, "limite": limite})
    await sessao.commit()
    if novo_id is None:
        raise AlertaNaoEncontrado(f"atribuição {atribuicao_id}")
    return novo_id


async def atualizar_valor(sessao: AsyncSession, alerta_id: int, valor: int) -> None:
    await sessao.execute(update(Alerta).where(Alerta.id == alerta_id).values(valor=valor))
    await sessao.commit()


async def encerrar(sessao: AsyncSession, alerta_id: int, fim: datetime) -> None:
    # greatest(): o fim nunca fica antes do início (ex.: sem sinal que termina no próprio contato)
    await sessao.execute(
        update(Alerta).where(Alerta.id == alerta_id, Alerta.fim.is_(None))
        .values(fim=func.greatest(fim, Alerta.inicio))
    )
    await sessao.commit()


async def encerrar_abertos_na_subida(sessao: AsyncSession) -> int:
    """Ao iniciar o servidor, encerra os alertas que ficaram abertos (o estado do motor
    se perdeu). Os que continuarem valendo são recriados pelo motor."""
    r = await sessao.execute(update(Alerta).where(Alerta.fim.is_(None)).values(fim=func.now()))
    await sessao.commit()
    return r.rowcount


async def reconhecer(sessao: AsyncSession, alerta_id: int, por: str | None = None) -> AlertaCompleto:
    alerta = await sessao.get(Alerta, alerta_id)
    if alerta is None:
        raise AlertaNaoEncontrado(alerta_id)
    if alerta.reconhecido_em is not None:
        raise AlertaJaReconhecido(alerta_id)
    alerta.reconhecido_em = func.now()
    alerta.reconhecido_por = por
    await sessao.commit()
    return await obter(sessao, alerta_id)


async def total_abertos(sessao: AsyncSession) -> int:
    return await sessao.scalar(select(func.count()).select_from(Alerta).where(Alerta.fim.is_(None)))
