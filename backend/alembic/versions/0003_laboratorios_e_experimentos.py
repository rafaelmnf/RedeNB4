"""Laboratórios, experimentos e participantes

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21

O experimento não se liga à pulseira: o BPM de um experimento é obtido cruzando os
participantes, o período do experimento e as atribuições (quem usava qual pulseira).
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "laboratorios",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nome", sa.String(150), nullable=False, unique=True),
        sa.Column("descricao", sa.Text),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "experimentos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("laboratorio_id", sa.Integer, sa.ForeignKey("laboratorios.id"), nullable=False),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("descricao", sa.Text),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fim", sa.DateTime(timezone=True)),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("fim IS NULL OR fim > inicio", name="ck_experimentos_periodo"),
    )
    op.create_index("ix_experimentos_laboratorio", "experimentos", ["laboratorio_id", "inicio"])
    # Um pesquisador pode estar em vários experimentos ao mesmo tempo (sem EXCLUDE).
    op.create_table(
        "experimento_participantes",
        sa.Column("experimento_id", sa.Integer, sa.ForeignKey("experimentos.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("pesquisador_id", sa.Integer, sa.ForeignKey("pesquisadores.id"), primary_key=True),
    )
    op.create_index("ix_participantes_pesquisador", "experimento_participantes", ["pesquisador_id"])


def downgrade() -> None:
    op.drop_table("experimento_participantes")
    op.drop_table("experimentos")
    op.drop_table("laboratorios")
