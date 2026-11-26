"""Usuários do site. Não são apagados: só desativados.

Proteções para ninguém ficar sem acesso: o último admin ativo não pode ser
desativado nem rebaixado, e ninguém desativa a si mesmo.
Aumentar versao_sessao derruba as sessões (cookies) existentes do usuário.
"""
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...dominio import senhas
from ..models import Usuario
from .erros import VIOLACAO_UNICA, sqlstate
from .pesquisadores import normalizar_email

PAPEIS = ("admin", "leitor")
_HASH_FALSO = senhas.gerar_hash("usuario-inexistente")   # para o login de e-mail desconhecido demorar igual


class UsuarioDuplicado(Exception):
    pass


class UsuarioNaoEncontrado(Exception):
    pass


class UltimoAdmin(Exception):
    """A operação deixaria o sistema sem nenhum admin ativo."""


class AutoDesativacao(Exception):
    pass


class SenhaFraca(Exception):
    pass


def _validar_senha(senha: str) -> None:
    if len(senha) < senhas.TAMANHO_MINIMO:
        raise SenhaFraca(f"A senha precisa ter pelo menos {senhas.TAMANHO_MINIMO} caracteres")


async def listar(sessao: AsyncSession) -> list[Usuario]:
    return list((await sessao.scalars(select(Usuario).order_by(Usuario.nome, Usuario.id))).all())


async def total(sessao: AsyncSession) -> int:
    return await sessao.scalar(select(func.count()).select_from(Usuario))


async def obter(sessao: AsyncSession, usuario_id: int) -> Usuario:
    u = await sessao.get(Usuario, usuario_id)
    if u is None:
        raise UsuarioNaoEncontrado(usuario_id)
    return u


async def por_email(sessao: AsyncSession, email: str) -> Usuario | None:
    return await sessao.scalar(select(Usuario).where(Usuario.email == normalizar_email(email)))


async def _admins_ativos(sessao: AsyncSession) -> int:
    return await sessao.scalar(
        select(func.count()).select_from(Usuario).where(Usuario.papel == "admin", Usuario.ativo.is_(True))
    )


async def _commit(sessao: AsyncSession, email: str) -> None:
    try:
        await sessao.commit()
    except IntegrityError as exc:
        await sessao.rollback()
        if sqlstate(exc) == VIOLACAO_UNICA:
            raise UsuarioDuplicado(email) from None
        raise


async def criar(sessao: AsyncSession, email: str, nome: str, senha: str, papel: str = "leitor") -> Usuario:
    if papel not in PAPEIS:
        raise ValueError(papel)
    _validar_senha(senha)
    email = normalizar_email(email)
    u = Usuario(email=email, nome=nome.strip(), senha_hash=senhas.gerar_hash(senha), papel=papel, ativo=True)
    sessao.add(u)
    await _commit(sessao, email)
    await sessao.refresh(u)
    return u


async def autenticar(sessao: AsyncSession, email: str, senha: str) -> Usuario | None:
    """Devolve o usuário se e-mail e senha conferem e ele está ativo."""
    u = await por_email(sessao, email)
    if u is None:
        senhas.conferir(_HASH_FALSO, senha)          # tempo parecido: não revela se o e-mail existe
        return None
    if not u.ativo or not senhas.conferir(u.senha_hash, senha):
        return None
    if senhas.precisa_rehash(u.senha_hash):
        u.senha_hash = senhas.gerar_hash(senha)
    u.ultimo_login = datetime.now(UTC)
    await sessao.commit()
    await sessao.refresh(u)
    return u


async def atualizar(sessao: AsyncSession, usuario_id: int, por: Usuario, nome: str | None = None,
                    papel: str | None = None, ativo: bool | None = None) -> Usuario:
    """Alterações feitas por um admin (`por`)."""
    u = await obter(sessao, usuario_id)
    if ativo is False and u.id == por.id:
        raise AutoDesativacao(usuario_id)
    perde_admin = u.papel == "admin" and u.ativo and (ativo is False or (papel is not None and papel != "admin"))
    if perde_admin and await _admins_ativos(sessao) <= 1:
        raise UltimoAdmin(usuario_id)
    if nome is not None:
        u.nome = nome.strip()
    if papel is not None:
        if papel not in PAPEIS:
            raise ValueError(papel)
        u.papel = papel
    if ativo is not None and ativo != u.ativo:
        u.ativo = ativo
        if not ativo:
            u.versao_sessao += 1             # derruba as sessões abertas
    await sessao.commit()
    await sessao.refresh(u)
    return u


async def definir_senha(sessao: AsyncSession, usuario_id: int, nova: str) -> Usuario:
    """Troca a senha e derruba as sessões existentes (o chamador emite um cookie novo,
    se for a própria pessoa trocando)."""
    _validar_senha(nova)
    u = await obter(sessao, usuario_id)
    u.senha_hash = senhas.gerar_hash(nova)
    u.versao_sessao += 1
    await sessao.commit()
    await sessao.refresh(u)
    return u


async def encerrar_sessoes(sessao: AsyncSession, usuario_id: int) -> Usuario:
    u = await obter(sessao, usuario_id)
    u.versao_sessao += 1
    await sessao.commit()
    await sessao.refresh(u)
    return u
