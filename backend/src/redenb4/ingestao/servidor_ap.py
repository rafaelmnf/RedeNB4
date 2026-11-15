"""Servidor WebSocket que recebe a telemetria BLE do AP Aruba.

O AP é o cliente: conecta em ws://<servidor>:PORTA_AP e envia frames protobuf
binários. O servidor nunca envia comandos ao AP; ele só filtra pela allowlist.
"""
import logging
from datetime import UTC, datetime
from pathlib import Path

import websockets
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..db.repos.aps import garantir_ap
from ..dominio.leitura import Leitura
from ..dominio.mac import bytes_para_mac
from . import aruba_parser
from .allowlist import Allowlist

log = logging.getLogger(__name__)
MAX_DUMPS = 3


class ServidorAP:
    def __init__(self, allowlist: Allowlist, processar, fabrica_sessoes: async_sessionmaker[AsyncSession],
                 dump: bool = False, arquivo_raw: Path | None = None):
        """processar: função que recebe list[Leitura] (o pipeline)."""
        self.allowlist = allowlist
        self.processar = processar
        self._fabrica = fabrica_sessoes
        self.dump = dump
        self.arquivo_raw = arquivo_raw
        self._dumps_feitos = 0
        self.conexoes = 0

    async def _ap_id(self, identificador: str) -> int | None:
        try:
            async with self._fabrica() as sessao:
                return (await garantir_ap(sessao, identificador)).id
        except Exception:
            log.exception("Não foi possível registrar o AP %s", identificador)
            return None

    def processar_frame(self, frame: bytes, ap_id: int | None, agora: datetime | None = None) -> list[Leitura]:
        """Decodifica um frame e entrega as leituras ao pipeline. Separado do handler para teste."""
        agora = agora or datetime.now(UTC)
        macs = self.allowlist.macs
        if self.dump and self._dumps_feitos < MAX_DUMPS:
            for _, no in aruba_parser.achar_nos_com_macs(frame, macs):
                if aruba_parser.extrair_bpm(no)[0] is not None and self._dumps_feitos < MAX_DUMPS:
                    self._dumps_feitos += 1
                    print("\n===== ENTRADA COM ADVERTISEMENT =====")
                    aruba_parser.mostrar_no(no, macs)
                    print("=====================================\n")
        leituras = [
            Leitura(bytes_para_mac(a.mac), a.bpm, a.rssi, agora, a.payload, ap_id)
            for a in aruba_parser.decodificar_frame(frame, macs)
        ]
        if leituras:
            self.processar(leituras)
        return leituras

    async def handler(self, websocket) -> None:
        peer = websocket.remote_address[0] if websocket.remote_address else "desconhecido"
        log.info("AP conectado: %s", peer)
        self.conexoes += 1
        ap_id = await self._ap_id(peer)
        try:
            async for msg in websocket:
                if not isinstance(msg, bytes):
                    continue
                if self.arquivo_raw is not None:
                    with self.arquivo_raw.open("ab") as f:
                        f.write(len(msg).to_bytes(4, "big") + msg)
                try:
                    self.processar_frame(msg, ap_id)
                except Exception:
                    log.exception("Erro ao processar frame do AP %s", peer)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.conexoes -= 1
            log.info("AP desconectado: %s", peer)

    def servir(self, host: str, porta: int):
        """Devolve o servidor (use com 'async with' ou guarde para fechar depois)."""
        return websockets.serve(self.handler, host, porta, max_size=None)
