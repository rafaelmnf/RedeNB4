"""Estado ao vivo: snapshot (GET /api/status) e WebSocket /ws/ao-vivo.

Mensagens do servidor (JSON):
  {"tipo": "snapshot", "pulseiras": [Cartao, ...], "alertas": [Alerta abertos, ...]}
  {"tipo": "leitura", "cartao": Cartao, "ts": iso, "bpm": int}
  {"tipo": "status", "cartao": Cartao}               offline/online, fora do braço
  {"tipo": "cadastro"}                               pulseiras ou vínculos mudaram
  {"tipo": "alerta", "evento": "inicio|atualizacao|fim|reconhecido", "alerta": Alerta}
Mensagem do cliente: {"tipo": "snapshot"} pede um snapshot novo.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from ...servicos.broadcaster import DESCONECTAR, serializar
from ..ao_vivo import cartoes
from ..deps import carregar_usuario, usuario_atual
from ..schemas import AlertaSaida, CartaoSaida
from ..sessao import NOME_COOKIE, ler_token

log = logging.getLogger(__name__)
router = APIRouter(tags=["ao vivo"])

SEM_SESSAO = 4401              # código de fechamento: o navegador vai para a tela de login
CONFERIR_SESSAO_S = 60


def _cartoes(app) -> list[CartaoSaida]:
    s = app.state
    return cartoes(s.allowlist, s.pipeline, s.config, s.pipeline.nomes_aps)


def snapshot(app) -> str:
    return serializar({
        "tipo": "snapshot",
        "pulseiras": [c.model_dump(mode="json") for c in _cartoes(app)],
        "alertas": [AlertaSaida.model_validate(a).model_dump(mode="json") for a in app.state.alertas.abertos()],
    })


@router.get("/api/status", response_model=list[CartaoSaida], dependencies=[Depends(usuario_atual)])
async def status_atual(request: Request):
    """Estado atual de todas as pulseiras ativas (o mesmo que o snapshot do WebSocket)."""
    return _cartoes(request.app)


@router.websocket("/ws/ao-vivo")
async def ao_vivo(ws: WebSocket):
    await ws.accept()
    lido = ler_token(ws.cookies.get(NOME_COOKIE), ws.app.state.config.segredo_sessao)
    if lido is None or await carregar_usuario(ws.app, *lido) is None:
        await ws.close(SEM_SESSAO, "faça login")
        return
    broadcaster = ws.app.state.broadcaster
    fila = broadcaster.registrar()

    async def vigiar_sessao():
        """Termina quando a sessão deixa de valer (usuário desativado, senha trocada...)."""
        while True:
            await asyncio.sleep(CONFERIR_SESSAO_S)
            if await carregar_usuario(ws.app, *lido) is None:
                return

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
    sessao = asyncio.create_task(vigiar_sessao())
    try:
        await ws.send_text(snapshot(ws.app))
        while True:
            proxima = asyncio.create_task(fila.get())
            await asyncio.wait({proxima, leitor, sessao}, return_when=asyncio.FIRST_COMPLETED)
            if sessao.done():
                proxima.cancel()
                await ws.close(SEM_SESSAO, "sessão encerrada")
                break
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
        sessao.cancel()
