"""Registro de auditoria: quem fez o quê e quando. Nunca é apagado."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import RegistroAuditoria, Usuario

CAMPOS_SENSIVEIS = {"senha", "senha_atual", "nova_senha", "senha_hash"}


def _limpar(detalhes):
    """Tira senhas dos detalhes antes de gravar."""
    if isinstance(detalhes, dict):
        return {k: ("***" if k in CAMPOS_SENSIVEIS else _limpar(v)) for k, v in detalhes.items()}
    if isinstance(detalhes, list):
        return [_limpar(v) for v in detalhes]
    return detalhes


async def registrar(sessao: AsyncSession, usuario_id: int | None, acao: str, entidade: str | None = None,
                    entidade_id: int | None = None, detalhes: dict | None = None) -> None:
    sessao.add(RegistroAuditoria(usuario_id=usuario_id, acao=acao, entidade=entidade, entidade_id=entidade_id,
                                 detalhes=_limpar(detalhes) if detalhes else None))
    await sessao.commit()


async def listar(sessao: AsyncSession, usuario_id: int | None = None, acao: str | None = None,
                 de: datetime | None = None, ate: datetime | None = None,
                 limite: int = 500) -> list[tuple[RegistroAuditoria, str | None, str | None]]:
    """Registros mais recentes primeiro, com nome e e-mail de quem fez."""
    q = (select(RegistroAuditoria, Usuario.nome, Usuario.email)
         .outerjoin(Usuario, Usuario.id == RegistroAuditoria.usuario_id)
         .order_by(RegistroAuditoria.ts.desc(), RegistroAuditoria.id.desc()).limit(limite))
    if usuario_id is not None:
        q = q.where(RegistroAuditoria.usuario_id == usuario_id)
    if acao:
        q = q.where(RegistroAuditoria.acao.startswith(acao))
    if de is not None:
        q = q.where(RegistroAuditoria.ts >= de)
    if ate is not None:
        q = q.where(RegistroAuditoria.ts < ate)
    return [tuple(linha) for linha in (await sessao.execute(q)).all()]


async def acoes(sessao: AsyncSession) -> list[str]:
    """Ações já registradas (para o filtro da tela)."""
    r = await sessao.scalars(select(RegistroAuditoria.acao).distinct().order_by(RegistroAuditoria.acao))
    return list(r.all())
