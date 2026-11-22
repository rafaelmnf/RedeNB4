"""Estado ao vivo: snapshot (GET /api/status) e WebSocket /ws/ao-vivo.

Mensagens do servidor (JSON):
  {"tipo": "snapshot", "pulseiras": [Cartao, ...]}   na conexão e quando o cliente pede
  {"tipo": "leitura", "cartao": Cartao, "ts": iso, "bpm": int}
  {"tipo": "status", "cartao": Cartao}               offline/online, fora do braço
  {"tipo": "cadastro"}                               pulseiras ou vínculos mudaram
Mensagem do cliente: {"tipo": "snapshot"} pede um snapshot novo.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from ...servicos.broadcaster import DESCONECTAR, serializar
from ..ao_vivo import cartoes
from ..schemas import CartaoSaida

log = logging.getLogger(__name__)
router = APIRouter(tags=["ao vivo"])


def _cartoes(app) -> list[CartaoSaida]:
    s = app.state
    return cartoes(s.allowlist, s.pipeline, s.config, s.pipeline.nomes_aps)


def snapshot(app) -> str:
    return serializar({"tipo": "snapshot", "pulseiras": [c.model_dump(mode="json") for c in _cartoes(app)]})


@router.get("/api/status", response_model=list[CartaoSaida])
async def status_atual(request: Request):
    """Estado atual de todas as pulseiras ativas (o mesmo que o snapshot do WebSocket)."""
    return _cartoes(request.app)


@router.websocket("/ws/ao-vivo")
async def ao_vivo(ws: WebSocket):
    await ws.accept()
    broadcaster = ws.app.state.broadcaster
    fila = broadcaster.registrar()

    async def receber():
        while True:
            texto = await ws.receive_text()
            try:
                pedido = json.loads(texto)
            except ValueError:
                continue
            if isinstance(pedido, dict) and pedido.get("tipo") == "snapshot":
                await fila.put(snapshot(ws.app))

    leitor = asyncio.create_task(receber())
    try:
        await ws.send_text(snapshot(ws.app))
        while True:
            proxima = asyncio.create_task(fila.get())
            await asyncio.wait({proxima, leitor}, return_when=asyncio.FIRST_COMPLETED)
            if not proxima.done():
                proxima.cancel()
                break                      # o navegador fechou (ou a leitura falhou)
            texto = proxima.result()
            if texto is DESCONECTAR:
                await ws.close(1013, "fila cheia")
                break
            await ws.send_text(texto)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        broadcaster.remover(fila)
        leitor.cancel()
