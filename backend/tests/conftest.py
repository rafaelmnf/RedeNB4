import asyncio
import os
import sys
from pathlib import Path

import pytest

# device_config.py fica na raiz do repositório (usado pelos scripts legados)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from redenb4.config import obter_config
from redenb4.db.sessao import dsn_asyncpg

BACKEND = Path(__file__).resolve().parents[1]


async def _recriar_schema(dsn: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn, timeout=3)
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def url_banco_teste() -> str:
    """Recria o banco de testes do zero e aplica as migrações. Pula os testes de
    integração se o Postgres (docker compose up -d db) não estiver no ar."""
    url = obter_config().test_database_url
    try:
        asyncio.run(_recriar_schema(dsn_asyncpg(url)))
    except Exception as exc:
        pytest.skip(f"Postgres de testes indisponível ({exc}); rode 'docker compose up -d db'")

    from alembic import command
    from alembic.config import Config as ConfigAlembic

    os.environ["ALEMBIC_DATABASE_URL"] = url
    try:
        command.upgrade(ConfigAlembic(str(BACKEND / "alembic.ini")), "head")
    finally:
        os.environ.pop("ALEMBIC_DATABASE_URL", None)
    return url


@pytest.fixture
async def fabrica(url_banco_teste):
    """Fábrica de sessões num banco limpo (tabelas truncadas a cada teste)."""
    from sqlalchemy import text

    from redenb4.db.sessao import criar_engine, criar_fabrica_sessoes

    engine = criar_engine(url_banco_teste)
    async with engine.begin() as conn:
        tabelas = (await conn.execute(text(
            "SELECT string_agg(quote_ident(tablename), ', ') FROM pg_tables "
            "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
        ))).scalar()
        if tabelas:
            await conn.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))
    yield criar_fabrica_sessoes(engine)
    await engine.dispose()

