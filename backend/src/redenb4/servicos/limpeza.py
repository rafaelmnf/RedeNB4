"""Retenção das leituras: apaga de leituras_bpm o que for mais antigo que
RETENCAO_LEITURAS_DIAS. Roda na subida e depois a cada hora.

Só as leituras de BPM são apagadas. Pulseiras, vínculos, experimentos e alertas ficam.
O Postgres reaproveita o espaço liberado para as leituras novas (autovacuum), então a
tabela para de crescer em vez de encolher no disco.
"""
import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..db.repos.leituras import apagar_antigas
from ..ingestao.allowlist import esperar_algum

log = logging.getLogger(__name__)

INTERVALO_S = 3600


class LimpezaLeituras:
    def __init__(self, fabrica: async_sessionmaker[AsyncSession], retencao_dias: float,
                 intervalo_s: float = INTERVALO_S):
        self._fabrica = fabrica
        self._retencao = timedelta(days=retencao_dias)
        self._intervalo = intervalo_s

    async def rodar_uma_vez(self) -> int:
        limite = datetime.now(UTC) - self._retencao
        async with self._fabrica() as sessao:
            apagadas = await apagar_antigas(sessao, limite)
        if apagadas:
            log.info("Limpeza: %d leitura(s) anterior(es) a %s apagada(s)", apagadas,
                     limite.astimezone().strftime("%d/%m/%Y %H:%M"))
        return apagadas

    async def executar(self, parar: asyncio.Event) -> None:
        while not parar.is_set():
            try:
                await self.rodar_uma_vez()
            except Exception as exc:     # banco fora do ar: tenta de novo na próxima rodada
                log.warning("Limpeza das leituras antigas falhou (%s)", exc)
            await esperar_algum(parar, parar, self._intervalo)
