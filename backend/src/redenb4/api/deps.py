from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def obter_sessao(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.fabrica_sessoes() as sessao:
        yield sessao


def obter_pipeline(request: Request):
    return request.app.state.pipeline
