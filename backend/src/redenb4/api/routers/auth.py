"""Login, logout, usuário atual e troca da própria senha.

A sessão é um cookie assinado sem expiração (ver api/sessao.py). Depois de 5 senhas
erradas seguidas para o mesmo e-mail, o login fica bloqueado por 1 minuto.
"""
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Usuario
from ...db.repos import usuarios as repo
from ...db.repos.pesquisadores import normalizar_email
from ...dominio import senhas
from ..deps import obter_sessao, registrar_auditoria, usuario_atual
from ..schemas import LoginEntrada, TrocaSenha, UsuarioSaida
from ..sessao import apagar_cookie, emitir_cookie

router = APIRouter(prefix="/api/auth", tags=["login"])

MAX_FALHAS = 5
BLOQUEIO_S = 60
_falhas: dict[str, tuple[int, float]] = {}       # e-mail -> (falhas seguidas, bloqueado até)


def _bloqueado(email: str) -> float:
    falhas, ate = _falhas.get(email, (0, 0.0))
    return max(0.0, ate - time.monotonic()) if falhas >= MAX_FALHAS else 0.0


def _registrar_falha(email: str) -> None:
    falhas, _ = _falhas.get(email, (0, 0.0))
    falhas += 1
    _falhas[email] = (falhas, time.monotonic() + BLOQUEIO_S if falhas >= MAX_FALHAS else 0.0)


@router.post("/login", response_model=UsuarioSaida)
async def login(dados: LoginEntrada, request: Request, response: Response,
                sessao: AsyncSession = Depends(obter_sessao)):
    email = normalizar_email(dados.email)
    espera = _bloqueado(email)
    if espera:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Muitas tentativas. Tente de novo em {int(espera) + 1} s.")
    if _falhas.get(email, (0, 0.0))[0] >= MAX_FALHAS:
        _falhas.pop(email, None)                 # o bloqueio passou: zera a contagem
    usuario = await repo.autenticar(sessao, email, dados.senha)
    if usuario is None:
        _registrar_falha(email)
        await registrar_auditoria(request, None, "login.falhou", "usuario", None, {"email": email})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos")
    _falhas.pop(email, None)
    emitir_cookie(response, usuario, request.app.state.config.segredo_sessao)
    await registrar_auditoria(request, usuario.id, "login", "usuario", usuario.id)
    return usuario


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response):
    """Sai só deste navegador (apaga o cookie)."""
    usuario = getattr(request.state, "usuario", None)
    try:
        usuario = await usuario_atual(request)
    except HTTPException:
        pass
    apagar_cookie(response)
    if usuario is not None:
        await registrar_auditoria(request, usuario.id, "logout", "usuario", usuario.id)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/eu", response_model=UsuarioSaida)
async def eu(usuario: Usuario = Depends(usuario_atual)):
    return usuario


@router.post("/senha", status_code=status.HTTP_204_NO_CONTENT)
async def trocar_senha(dados: TrocaSenha, request: Request, response: Response,
                       usuario: Usuario = Depends(usuario_atual), sessao: AsyncSession = Depends(obter_sessao)):
    """Troca a própria senha. Este navegador continua logado; os outros saem."""
    if not senhas.conferir(usuario.senha_hash, dados.senha_atual):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha atual incorreta")
    try:
        atualizado = await repo.definir_senha(sessao, usuario.id, dados.nova_senha)
    except repo.SenhaFraca as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    emitir_cookie(response, atualizado, request.app.state.config.segredo_sessao)
    await registrar_auditoria(request, usuario.id, "usuario.trocar_senha", "usuario", usuario.id)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
