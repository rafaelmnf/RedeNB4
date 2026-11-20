from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def criar_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def criar_fabrica_sessoes(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def dsn_asyncpg(url: str) -> str:
    """Converte a URL do SQLAlchemy ('postgresql+asyncpg://') para o DSN do asyncpg."""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)
