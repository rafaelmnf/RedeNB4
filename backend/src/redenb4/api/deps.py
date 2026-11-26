"""Dependências comuns: sessão de banco, pipeline, usuário logado, papéis e auditoria."""
import json
import logging
from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Usuario
from ..db.repos import auditoria as repo_auditoria
from .sessao import ler_cookie, sessao_valida

log = logging.getLogger(__name__)


async def obter_sessao(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.fabrica_sessoes() as sessao:
        yield sessao


def obter_pipeline(request: Request):
    return request.app.state.pipeline


async def carregar_usuario(app, uid: int, versao: int) -> Usuario | None:
    """Usuário da sessão, se ela ainda vale (ativo e mesma versao_sessao)."""
    async with app.state.fabrica_sessoes() as sessao:
        usuario = await sessao.get(Usuario, uid)
    return usuario if sessao_valida(usuario, versao) else None


async def usuario_atual(request: Request) -> Usuario:
    """Exige login (qualquer papel). Guarda o usuário em request.state.usuario."""
    lido = ler_cookie(request, request.app.state.config.segredo_sessao)
    usuario = await carregar_usuario(request.app, *lido) if lido else None
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar")
    request.state.usuario = usuario
    return usuario


async def exigir_admin(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
    if usuario.papel != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Somente administradores podem fazer isso")
    return usuario


async def registrar_auditoria(request: Request, usuario_id: int | None, acao: str, entidade: str | None = None,
                              entidade_id: int | None = None, detalhes: dict | None = None) -> None:
    """Grava na auditoria sem nunca derrubar a requisição (uma falha só vai para o log)."""
    try:
        async with request.app.state.fabrica_sessoes() as sessao:
            await repo_auditoria.registrar(sessao, usuario_id, acao, entidade, entidade_id, detalhes)
    except Exception:
        log.exception("Falha ao gravar auditoria (%s)", acao)


def admin_auditado(acao: str, entidade: str, parametro_id: str | None = None):
    """Dependência para rotas de alteração: exige admin e, se a rota terminar sem erro,
    grava na auditoria a ação, o id da entidade (do caminho) e o corpo JSON enviado.

        @router.patch("/{pulseira_id}", dependencies=[admin_auditado("pulseira.editar", "pulseira", "pulseira_id")])
    """
    async def dependencia(request: Request, usuario: Usuario = Depends(exigir_admin)) -> AsyncIterator[None]:
        corpo = await request.body()
        yield                                   # a rota roda aqui; exceções (4xx/5xx) passam direto
        try:
            detalhes = json.loads(corpo) if corpo else None
        except ValueError:
            detalhes = None
        if detalhes is not None and not isinstance(detalhes, dict):
            detalhes = {"corpo": detalhes}
        entidade_id = request.path_params.get(parametro_id) if parametro_id else None
        await registrar_auditoria(request, usuario.id, acao, entidade,
                                  int(entidade_id) if entidade_id is not None else None, detalhes)

    return Depends(dependencia)
