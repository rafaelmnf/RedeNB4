"""Usuários (login) e auditoria

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-26

Sem tabela de sessões: o cookie assinado leva (usuario_id, versao_sessao). Aumentar
versao_sessao (desativar, trocar senha, "sair de todos") invalida os cookies antigos.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("senha_hash", sa.Text, nullable=False),
        sa.Column("papel", sa.String(10), nullable=False),
        sa.Column("ativo", sa.Boolean, server_default=sa.true(), nullable=False),
        sa.Column("versao_sessao", sa.Integer, server_default="1", nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ultimo_login", sa.DateTime(timezone=True)),
        sa.CheckConstraint("email = lower(email)", name="ck_usuarios_email_minusculo"),
        sa.CheckConstraint("papel IN ('admin', 'leitor')", name="ck_usuarios_papel"),
    )
    op.create_table(
        "auditoria",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuarios.id")),
        sa.Column("acao", sa.Text, nullable=False),
        sa.Column("entidade", sa.Text),
        sa.Column("entidade_id", sa.Integer),
        sa.Column("detalhes", postgresql.JSONB),
    )
    op.create_index("ix_auditoria_ts", "auditoria", [sa.text("ts DESC")])
    op.create_index("ix_auditoria_usuario_ts", "auditoria", ["usuario_id", "ts"])


def downgrade() -> None:
    op.drop_table("auditoria")
    op.drop_table("usuarios")
