"""Leitura do SQLSTATE dos erros do Postgres que chegam pelo SQLAlchemy + asyncpg."""
from sqlalchemy.exc import DBAPIError

VIOLACAO_UNICA = "23505"
VIOLACAO_EXCLUSAO = "23P01"     # constraint EXCLUDE (sobreposição de períodos)
VIOLACAO_CHECK = "23514"


def sqlstate(exc: DBAPIError) -> str | None:
    orig = exc.orig
    for candidato in (orig, getattr(orig, "__cause__", None)):
        codigo = getattr(candidato, "sqlstate", None) or getattr(candidato, "pgcode", None)
        if codigo:
            return codigo
    return None
