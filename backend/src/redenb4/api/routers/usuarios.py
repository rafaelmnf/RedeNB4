"""Gestão de usuários (só admin). Usuários não são apagados, só desativados."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Usuario
from ...db.repos import usuarios as repo
from ..deps import exigir_admin, obter_sessao, registrar_auditoria
from ..schemas import SenhaNova, UsuarioAtualizar, UsuarioCriar, UsuarioSaida

router = APIRouter(prefix="/api/usuarios", tags=["usuários"], dependencies=[Depends(exigir_admin)])


def _erro(exc: Exception, usuario_id: int | None = None) -> HTTPException:
    if isinstance(exc, repo.UsuarioNaoEncontrado):
        return HTTPException(status.HTTP_404_NOT_FOUND, f"Usuário {usuario_id} não encontrado")
    if isinstance(exc, repo.UsuarioDuplicado):
        return HTTPException(status.HTTP_409_CONFLICT, f"Já existe um usuário com o e-mail {exc}")
    if isinstance(exc, repo.UltimoAdmin):
        return HTTPException(status.HTTP_409_CONFLICT,
                             "Este é o último administrador ativo. Promova outra pessoa a admin antes.")
    if isinstance(exc, repo.AutoDesativacao):
        return HTTPException(status.HTTP_409_CONFLICT, "Você não pode desativar o seu próprio usuário")
    if isinstance(exc, repo.SenhaFraca):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    raise exc


ERROS = (repo.UsuarioNaoEncontrado, repo.UsuarioDuplicado, repo.UltimoAdmin, repo.AutoDesativacao, repo.SenhaFraca)


@router.get("", response_model=list[UsuarioSaida])
async def listar(sessao: AsyncSession = Depends(obter_sessao)):
    return await repo.listar(sessao)


@router.post("", response_model=UsuarioSaida, status_code=status.HTTP_201_CREATED)
async def criar(dados: UsuarioCriar, request: Request, admin: Usuario = Depends(exigir_admin),
                sessao: AsyncSession = Depends(obter_sessao)):
    try:
        u = await repo.criar(sessao, dados.email, dados.nome, dados.senha, dados.papel)
    except ERROS as exc:
        raise _erro(exc) from None
    await registrar_auditoria(request, admin.id, "usuario.criar", "usuario", u.id,
                              {"email": u.email, "nome": u.nome, "papel": u.papel})
    return u


@router.patch("/{usuario_id}", response_model=UsuarioSaida)
async def atualizar(usuario_id: int, dados: UsuarioAtualizar, request: Request,
                    admin: Usuario = Depends(exigir_admin), sessao: AsyncSession = Depends(obter_sessao)):
    campos = {k: v for k, v in dados.model_dump(exclude_unset=True).items() if v is not None}
    try:
        u = await repo.atualizar(sessao, usuario_id, admin, **campos)
    except ERROS as exc:
        raise _erro(exc, usuario_id) from None
    await registrar_auditoria(request, admin.id, "usuario.editar", "usuario", usuario_id, campos)
    return u


@router.post("/{usuario_id}/senha", status_code=status.HTTP_204_NO_CONTENT)
async def redefinir_senha(usuario_id: int, dados: SenhaNova, request: Request,
                          admin: Usuario = Depends(exigir_admin), sessao: AsyncSession = Depends(obter_sessao)):
    """O admin define uma senha nova para alguém. As sessões dessa pessoa caem."""
    try:
        await repo.definir_senha(sessao, usuario_id, dados.senha)
    except ERROS as exc:
        raise _erro(exc, usuario_id) from None
    await registrar_auditoria(request, admin.id, "usuario.redefinir_senha", "usuario", usuario_id)


@router.post("/{usuario_id}/encerrar-sessoes", status_code=status.HTTP_204_NO_CONTENT)
async def encerrar_sessoes(usuario_id: int, request: Request, admin: Usuario = Depends(exigir_admin),
                           sessao: AsyncSession = Depends(obter_sessao)):
    """Desloga a pessoa de todos os navegadores (ela entra de novo com a mesma senha)."""
    try:
        await repo.encerrar_sessoes(sessao, usuario_id)
    except ERROS as exc:
        raise _erro(exc, usuario_id) from None
    await registrar_auditoria(request, admin.id, "usuario.encerrar_sessoes", "usuario", usuario_id)
