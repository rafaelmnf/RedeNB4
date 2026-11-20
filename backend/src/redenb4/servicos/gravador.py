"""Gravação em lote das leituras com COPY (asyncpg)."""
import asyncio
import logging
from datetime import datetime

import asyncpg

from ..ingestao.allowlist import esperar_algum

log = logging.getLogger(__name__)

COLUNAS = ("ts", "pulseira_id", "bpm", "rssi", "ap_id", "atribuicao_id")
LIMITE_BUFFER = 200_000     # se o banco ficar fora muito tempo, descarta as mais antigas


class GravadorLote:
    def __init__(self, dsn: str, intervalo_s: float = 1.0, tamanho_lote: int = 500):
        self._dsn = dsn
        self._intervalo = intervalo_s
        self._tamanho = tamanho_lote
        self._buffer: list[tuple] = []
        self._cheio = asyncio.Event()
        self.total_gravado = 0

    def adicionar(self, ts: datetime, pulseira_id: int, bpm: int, rssi: float | None,
                  ap_id: int | None, atribuicao_id: int | None = None) -> None:
        self._buffer.append((ts, pulseira_id, bpm, rssi, ap_id, atribuicao_id))
        if len(self._buffer) > LIMITE_BUFFER:
            descartar = len(self._buffer) - LIMITE_BUFFER
            del self._buffer[:descartar]
            log.error("Buffer de leituras cheio: %d leituras antigas descartadas", descartar)
        if len(self._buffer) >= self._tamanho:
            self._cheio.set()

    async def _gravar(self, conn: asyncpg.Connection) -> None:
        if not self._buffer:
            return
        lote, self._buffer = self._buffer, []
        try:
            await conn.copy_records_to_table("leituras_bpm", records=lote, columns=COLUNAS)
            self.total_gravado += len(lote)
        except BaseException:
            self._buffer[:0] = lote          # devolve ao buffer para tentar de novo
            raise

    async def executar(self, parar: asyncio.Event) -> None:
        conn = None
        while True:
            try:
                if conn is None or conn.is_closed():
                    conn = await asyncpg.connect(self._dsn)
                await esperar_algum(self._cheio, parar, self._intervalo)
                self._cheio.clear()
                await self._gravar(conn)
                if parar.is_set():
                    break
            except Exception as exc:
                log.warning("Falha ao gravar leituras (%s); nova tentativa em 5 s", exc)
                if conn is not None:
                    conn.terminate()
                    conn = None
                if parar.is_set():
                    break
                await esperar_algum(parar, parar, 5)
        if conn is not None:
            await conn.close()
        if self._buffer:
            log.warning("%d leituras não gravadas ao encerrar", len(self._buffer))
