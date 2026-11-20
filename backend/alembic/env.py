import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from redenb4.config import obter_config
from redenb4.db.models import Base

target_metadata = Base.metadata


def _url() -> str:
    # ALEMBIC_DATABASE_URL permite migrar outro banco (ex.: o de testes)
    return os.environ.get("ALEMBIC_DATABASE_URL") or obter_config().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _rodar(conexao) -> None:
    context.configure(connection=conexao, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as conexao:
        await conexao.run_sync(_rodar)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
