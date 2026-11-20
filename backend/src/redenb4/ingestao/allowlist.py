"""Allowlist dinâmica: os MACs aceitos pela ingestão vêm do banco e são recarregados
quando o Postgres avisa (LISTEN/NOTIFY) que pulseiras ou atribuições mudaram."""
import asyncio
import logging
from dataclasses import dataclass

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..db.repos import pulseiras as repo_pulseiras
from ..dominio.mac import mac_para_bytes, normalizar_mac

log = logging.getLogger(__name__)

CANAIS = ("pulseiras_alteradas", "atribuicoes_alteradas")
RECARGA_PERIODICA_S = 60    # rede de segurança caso algum NOTIFY se perca


async def esperar_algum(a: asyncio.Event, b: asyncio.Event, timeout: float) -> None:
    """Espera até que qualquer um dos eventos seja sinalizado ou o tempo acabe."""
    tarefas = [asyncio.create_task(a.wait()), asyncio.create_task(b.wait())]
    try:
        await asyncio.wait(tarefas, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tarefas:
            t.cancel()


@dataclass(frozen=True, slots=True)
class PulseiraAceita:
    pulseira_id: int
    mac: str
    apelido: str | None

    @property
    def nome(self) -> str:
        return self.apelido or self.mac


class Allowlist:
    def __init__(self, fabrica_sessoes: async_sessionmaker[AsyncSession]):
        self._fabrica = fabrica_sessoes
        self._por_mac: dict[bytes, PulseiraAceita] = {}
        self.macs: frozenset[bytes] = frozenset()
        self._ouvintes = []
        self._lock = asyncio.Lock()

    def ao_mudar(self, callback) -> None:
        """Registra uma função chamada (sem argumentos) depois de cada recarga."""
        self._ouvintes.append(callback)

    def obter(self, mac: bytes) -> PulseiraAceita | None:
        return self._por_mac.get(mac)

    def __len__(self) -> int:
        return len(self._por_mac)

    async def recarregar(self) -> None:
        async with self._lock:
            async with self._fabrica() as sessao:
                ativas = await repo_pulseiras.listar_ativas(sessao)
            novo = {}
            for p in ativas:
                mac = normalizar_mac(str(p.mac))
                novo[mac_para_bytes(mac)] = PulseiraAceita(p.id, mac, p.apelido)
            adicionadas = novo.keys() - self._por_mac.keys()
            retiradas = self._por_mac.keys() - novo.keys()
            self._por_mac = novo
            self.macs = frozenset(novo)
        for m in adicionadas:
            log.info("Allowlist: +%s (%s)", novo[m].mac, novo[m].nome)
        for m in retiradas:
            log.info("Allowlist: -%s", m.hex(":").upper())
        for cb in self._ouvintes:
            cb()

    async def escutar(self, dsn: str, parar: asyncio.Event) -> None:
        """Mantém uma conexão LISTEN aberta; reconecta se cair. Recarrega também
        periodicamente, por segurança."""
        pendente = asyncio.Event()

        def _notificado(*_):
            pendente.set()

        while not parar.is_set():
            conn = None
            try:
                conn = await asyncpg.connect(dsn)
                for canal in CANAIS:
                    await conn.add_listener(canal, _notificado)
                await self.recarregar()          # pode ter perdido avisos enquanto estava fora
                while not parar.is_set():
                    await esperar_algum(pendente, parar, RECARGA_PERIODICA_S)
                    if parar.is_set():
                        break
                    pendente.clear()
                    await asyncio.sleep(0.1)     # agrupa rajadas de NOTIFY
                    await self.recarregar()
            except Exception as exc:  # banco fora do ar, conexão caiu etc.
                log.warning("LISTEN indisponível (%s); nova tentativa em 5 s", exc)
                await esperar_algum(parar, parar, 5)
            finally:
                if conn is not None:
                    await conn.close()
