"""Vigia: detecta quando uma pulseira fica sem sinal (ou volta).

Sem advertisements novos o pipeline não é chamado, então só uma tarefa periódica
percebe que a pulseira sumiu. Publica apenas as mudanças de online ↔ offline.
"""
import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from ..ingestao.allowlist import esperar_algum
from .pipeline import Pipeline, StatusPulseira


def agora_utc() -> datetime:
    return datetime.now(UTC)


class Vigia:
    def __init__(self, pipeline: Pipeline, limite_s: float, publicar: Callable[[StatusPulseira], None],
                 relogio: Callable[[], datetime] = agora_utc, intervalo_s: float = 1.0):
        self._pipeline = pipeline
        self._limite = limite_s
        self._publicar = publicar
        self._relogio = relogio
        self._intervalo = intervalo_s
        self._online: dict[int, bool] = {}

    def verificar(self) -> list[int]:
        """Uma rodada. Devolve os ids das pulseiras que mudaram de estado."""
        agora = self._relogio()
        mudaram = []
        status = self._pipeline.status
        for pid in list(self._online):
            if pid not in status:
                del self._online[pid]          # pulseira desativada ou removida
        for pid, st in list(status.items()):
            online = st.esta_online(agora, self._limite)
            antes = self._online.get(pid)
            self._online[pid] = online
            # Na primeira vez a leitura já foi publicada pelo pipeline; só mudanças interessam.
            if antes is not None and antes != online:
                mudaram.append(pid)
                self._publicar(st)
        return mudaram

    async def executar(self, parar: asyncio.Event) -> None:
        while not parar.is_set():
            self.verificar()
            await esperar_algum(parar, parar, self._intervalo)
