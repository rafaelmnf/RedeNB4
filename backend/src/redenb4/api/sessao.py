"""Cookie de sessão assinado (sem tabela de sessões e sem expiração por tempo).

O cookie leva {"uid": id, "v": versao_sessao}, assinado com SEGREDO_SESSAO. Ele vale
até o usuário clicar em "Sair" nesse navegador, ou até a versao_sessao do usuário mudar
(desativado, senha trocada, "sair de todos os dispositivos"). Trocar o SEGREDO_SESSAO
desloga todo mundo.
"""
from fastapi import Request, Response
from itsdangerous import BadSignature, URLSafeSerializer

from ..db.models import Usuario

NOME_COOKIE = "redenb4_sessao"
DEZ_ANOS_S = 10 * 365 * 24 * 3600
SEGREDOS_PADRAO = {"", "dev-inseguro-troque", "troque-este-segredo"}


def _serializador(segredo: str) -> URLSafeSerializer:
    return URLSafeSerializer(segredo, salt="redenb4-sessao")


def emitir_cookie(resp: Response, usuario: Usuario, segredo: str) -> None:
    token = _serializador(segredo).dumps({"uid": usuario.id, "v": usuario.versao_sessao})
    resp.set_cookie(NOME_COOKIE, token, max_age=DEZ_ANOS_S, httponly=True, samesite="lax", path="/")


def apagar_cookie(resp: Response) -> None:
    resp.delete_cookie(NOME_COOKIE, path="/", httponly=True, samesite="lax")


def ler_token(token: str | None, segredo: str) -> tuple[int, int] | None:
    if not token:
        return None
    try:
        dados = _serializador(segredo).loads(token)
        return int(dados["uid"]), int(dados["v"])
    except (BadSignature, KeyError, TypeError, ValueError):
        return None


def ler_cookie(request: Request, segredo: str) -> tuple[int, int] | None:
    return ler_token(request.cookies.get(NOME_COOKIE), segredo)


def sessao_valida(usuario: Usuario | None, versao: int) -> bool:
    return usuario is not None and usuario.ativo and usuario.versao_sessao == versao
