"""Fan-out das mensagens ao vivo para os navegadores conectados em /ws/ao-vivo.

Cada navegador tem uma fila. A mensagem é serializada uma vez só. Um navegador lento,
com a fila cheia, é desconectado; ao reconectar ele recebe um snapshot completo, então
nada fica inconsistente.
"""
import asyncio
import json
import logging
from datetime import date, datetime

log = logging.getLogger(__name__)

DESCONECTAR = object()      # sentinela: o consumidor da fila deve fechar a conexão


def _json_padrao(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    raise TypeError(f"Não serializável: {type(v).__name__}")


def serializar(msg: dict) -> str:
    return json.dumps(msg, default=_json_padrao, ensure_ascii=False, separators=(",", ":"))


class Broadcaster:
    def __init__(self, tamanho_fila: int = 500):
        self._tamanho = tamanho_fila
        self._filas: set[asyncio.Queue] = set()

    @property
    def clientes(self) -> int:
        return len(self._filas)

    def registrar(self) -> asyncio.Queue:
        fila: asyncio.Queue = asyncio.Queue(maxsize=self._tamanho)
        self._filas.add(fila)
        return fila

    def remover(self, fila: asyncio.Queue) -> None:
        self._filas.discard(fila)

    def publicar(self, msg: dict) -> None:
        if not self._filas:
            return
        texto = serializar(msg)
        for fila in list(self._filas):
            try:
                fila.put_nowait(texto)
            except asyncio.QueueFull:
                log.warning("Navegador lento: fila cheia, desconectando (vai reconectar e receber snapshot)")
                self._derrubar(fila)

    def _derrubar(self, fila: asyncio.Queue) -> None:
        self._filas.discard(fila)
        while not fila.empty():
            fila.get_nowait()
        fila.put_nowait(DESCONECTAR)
