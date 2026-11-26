"""Serviço de alertas: liga o motor (regras puras) ao banco e aos navegadores.

O pipeline e o vigia são síncronos, então os eventos do motor entram numa fila e uma
tarefa os grava em ordem. Depois de gravar, cada mudança é publicada para os navegadores.
Os alertas abertos ficam também em memória, para o snapshot do dashboard.
"""
import asyncio
import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..db.repos import alertas as repo
from ..db.repos.alertas import AlertaCompleto
from ..dominio.alertas import AlertaAtualizado, AlertaEncerrado, AlertaIniciado, Evento, MotorAlertas

log = logging.getLogger(__name__)

DESCRICAO = {"bpm_alto": "BPM alto", "bpm_baixo": "BPM baixo", "sem_sinal": "sem sinal",
             "fora_do_braco": "fora do braço"}

Publicar = Callable[[str, AlertaCompleto], None]     # (evento, alerta): inicio|atualizacao|fim|reconhecido


class ServicoAlertas:
    def __init__(self, fabrica: async_sessionmaker[AsyncSession], motor: MotorAlertas, publicar: Publicar):
        self._fabrica = fabrica
        self.motor = motor
        self._publicar = publicar
        self._fila: asyncio.Queue[Evento] = asyncio.Queue()
        self._abertos: dict[int, AlertaCompleto] = {}            # alerta_id -> alerta
        self._ids: dict[tuple[int, str], int] = {}               # (atribuicao_id, tipo) -> alerta_id

    def tratar(self, eventos: list[Evento]) -> None:
        for e in eventos:
            self._fila.put_nowait(e)

    def abertos(self) -> list[AlertaCompleto]:
        return sorted(self._abertos.values(), key=lambda a: a.inicio)

    async def iniciar(self) -> None:
        async with self._fabrica() as sessao:
            n = await repo.encerrar_abertos_na_subida(sessao)
        if n:
            log.info("%d alerta(s) aberto(s) da execução anterior encerrado(s); "
                     "os que continuarem valendo serão recriados", n)

    async def executar(self, parar: asyncio.Event) -> None:
        while not (parar.is_set() and self._fila.empty()):
            try:
                evento = await asyncio.wait_for(self._fila.get(), timeout=0.5)
            except TimeoutError:
                continue
            try:
                await self._gravar(evento)
            except Exception:
                log.exception("Falha ao gravar o alerta %s", evento)

    async def esvaziar(self) -> None:
        """Grava tudo o que está na fila (usado nos testes)."""
        while not self._fila.empty():
            await self._gravar(self._fila.get_nowait())

    async def _gravar(self, e: Evento) -> None:
        chave = (e.atribuicao_id, e.tipo)
        async with self._fabrica() as sessao:
            if isinstance(e, AlertaIniciado):
                alerta_id = await repo.abrir(sessao, e.tipo, e.atribuicao_id, e.inicio, e.valor, e.limite)
                alerta = await repo.obter(sessao, alerta_id)
                self._ids[chave] = alerta_id
                self._abertos[alerta_id] = alerta
                log.warning("ALERTA %s: %s (%s)%s", DESCRICAO[e.tipo], alerta.pesquisador, alerta.pulseira,
                            f" | BPM {e.valor}, limite {e.limite}" if e.valor is not None else "")
                self._publicar("inicio", alerta)
            elif isinstance(e, AlertaAtualizado):
                alerta_id = self._ids.get(chave)
                if alerta_id is None:
                    return
                await repo.atualizar_valor(sessao, alerta_id, e.valor)
                self._abertos[alerta_id].valor = e.valor
                self._publicar("atualizacao", self._abertos[alerta_id])
            elif isinstance(e, AlertaEncerrado):
                alerta_id = self._ids.pop(chave, None)
                if alerta_id is None:
                    return
                await repo.encerrar(sessao, alerta_id, e.fim)
                alerta = await repo.obter(sessao, alerta_id)
                self._abertos.pop(alerta_id, None)
                log.info("Alerta encerrado: %s de %s (%s)", DESCRICAO[e.tipo], alerta.pesquisador, alerta.pulseira)
                self._publicar("fim", alerta)

    async def reconhecer(self, alerta_id: int, por: str | None = None) -> AlertaCompleto:
        async with self._fabrica() as sessao:
            alerta = await repo.reconhecer(sessao, alerta_id, por)
        if alerta_id in self._abertos:
            self._abertos[alerta_id] = alerta
        self._publicar("reconhecido", alerta)
        return alerta
