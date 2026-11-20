from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Ap


async def garantir_ap(sessao: AsyncSession, identificador: str) -> Ap:
    """Devolve o AP com esse identificador, criando-o na primeira conexão."""
    await sessao.execute(
        insert(Ap)
        .values(nome=f"AP {identificador}", identificador=identificador)
        .on_conflict_do_nothing(index_elements=[Ap.identificador])
    )
    await sessao.commit()
    return await sessao.scalar(select(Ap).where(Ap.identificador == identificador))
