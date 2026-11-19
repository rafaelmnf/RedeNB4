"""Servidor WebSocket que recebe a telemetria BLE do AP Aruba.

O AP é o cliente: conecta em ws://<servidor>:PORTA_AP e envia frames protobuf
binários. O servidor nunca envia comandos ao AP; ele só filtra pela allowlist.
"""
import logging
import time
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
VARREDURA_DESCONHECIDAS_S = 10     # procura Polar não cadastradas no máximo a cada 10 s
AVISO_DESCONHECIDA_S = 300         # repete o aviso de cada MAC não cadastrado a cada 5 min


class ServidorAP:
    def __init__(self, allowlist: Allowlist, processar, fabrica_sessoes: async_sessionmaker[AsyncSession],
                 dump: bool = False, arquivo_raw: Path | None = None, token: str = ""):
        """processar: função que recebe list[Leitura] (o pipeline).
        token: endpointToken esperado no cabeçalho de cada frame (vazio = não valida)."""
        self.token = token
        self.allowlist = allowlist
        self.processar = processar
        self._fabrica = fabrica_sessoes
        self.dump = dump
        self.arquivo_raw = arquivo_raw
        self._dumps_feitos = 0
        self._cabecalho_mostrado = False
        self.conexoes = 0
        # Polar vistas pelo AP mas não cadastradas: mac -> (horário, rssi). Útil para cadastrar.
        self.nao_cadastradas: dict[str, tuple[datetime, int | None]] = {}
        self._ultima_varredura = 0.0
        self._ultimo_aviso: dict[str, float] = {}

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
        if self.dump and not self._cabecalho_mostrado:
            self._cabecalho_mostrado = True
            print("\n===== CABEÇALHO DO PRIMEIRO FRAME =====")
            for linha in aruba_parser.resumir_frame(frame):
                print("  " + linha)
            print("=======================================\n")
        self._procurar_nao_cadastradas(frame, macs, agora)
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

    def _procurar_nao_cadastradas(self, frame: bytes, macs: frozenset[bytes], agora: datetime) -> None:
        relogio = time.monotonic()
        if relogio - self._ultima_varredura < VARREDURA_DESCONHECIDAS_S:
            return
        self._ultima_varredura = relogio
        for mac_b, rssi in aruba_parser.achar_polar_no_frame(frame).items():
            if mac_b in macs:
                continue
            mac = bytes_para_mac(mac_b)
            self.nao_cadastradas[mac] = (agora, rssi)
            if relogio - self._ultimo_aviso.get(mac, -AVISO_DESCONHECIDA_S) >= AVISO_DESCONHECIDA_S:
                self._ultimo_aviso[mac] = relogio
                log.warning("Pulseira Polar NÃO cadastrada detectada: %s (RSSI %s dBm). "
                            "Cadastre em /pulseiras para aceitar os dados dela.", mac, rssi)

    def token_valido(self, frame: bytes) -> bool:
        return not self.token or aruba_parser.extrair_token(frame) == self.token

    async def handler(self, websocket) -> None:
        peer = websocket.remote_address[0] if websocket.remote_address else "desconhecido"
        log.info("AP conectado: %s", peer)
        if self.dump:
            self._mostrar_requisicao(websocket)
        self.conexoes += 1
        ap_id = await self._ap_id(peer)
        try:
            async for msg in websocket:
                if not isinstance(msg, bytes):
                    continue
                if not self.token_valido(msg):
                    log.warning("Frame de %s com endpointToken inválido ou ausente; conexão recusada. "
                                "Confira TOKEN_AP no .env e o endpointToken no AP.", peer)
                    await websocket.close(1008, "token invalido")
                    break
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

    @staticmethod
    def _mostrar_requisicao(websocket) -> None:
        """--dump: mostra o caminho e os cabeçalhos do handshake do AP, para descobrir
        como o endpointToken é enviado. Valores de cabeçalhos sensíveis saem mascarados."""
        req = getattr(websocket, "request", None)
        if req is None:
            return
        print(f"\n===== HANDSHAKE DO AP: path={req.path} =====")
        for nome, valor in req.headers.raw_items():
            if nome.lower() in ("authorization", "cookie", "x-auth-token", "token"):
                valor = f"{valor[:10]}… ({len(valor)} caracteres)"
            print(f"  {nome}: {valor}")
        print("=============================================\n")

    def servir(self, host: str, porta: int):
        """Devolve o servidor (use com 'async with' ou guarde para fechar depois)."""
        return websockets.serve(self.handler, host, porta, max_size=None)
