"""Limites globais e alertas

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22

A linha única de `limites` é criada pela aplicação na subida, com os valores do .env.
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TIPOS = ("bpm_alto", "bpm_baixo", "sem_sinal", "fora_do_braco")


def upgrade() -> None:
    op.create_table(
        "limites",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("bpm_min", sa.SmallInteger, nullable=False),
        sa.Column("bpm_max", sa.SmallInteger, nullable=False),
        sa.Column("duracao_s", sa.Integer, nullable=False),
        sa.Column("sem_sinal_s", sa.Integer, nullable=False),
        sa.Column("fora_do_braco_s", sa.Integer, nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_limites_linha_unica"),
        sa.CheckConstraint("bpm_min > 0 AND bpm_min < bpm_max", name="ck_limites_faixa"),
        sa.CheckConstraint("duracao_s > 0 AND sem_sinal_s > 0 AND fora_do_braco_s > 0", name="ck_limites_tempos"),
    )
    op.create_table(
        "alertas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("pulseira_id", sa.Integer, sa.ForeignKey("pulseiras.id"), nullable=False),
        sa.Column("pesquisador_id", sa.Integer, sa.ForeignKey("pesquisadores.id"), nullable=False),
        sa.Column("atribuicao_id", sa.Integer, sa.ForeignKey("atribuicoes.id"), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fim", sa.DateTime(timezone=True)),
        sa.Column("valor", sa.SmallInteger),       # pico (alto) ou vale (baixo)
        sa.Column("limite", sa.SmallInteger),      # limite vigente quando começou
        sa.Column("reconhecido_em", sa.DateTime(timezone=True)),
        sa.Column("reconhecido_por", sa.Text),     # preenchido a partir da etapa de login
        sa.CheckConstraint(f"tipo IN {TIPOS}", name="ck_alertas_tipo"),
        sa.CheckConstraint("fim IS NULL OR fim >= inicio", name="ck_alertas_periodo"),
    )
    # No máximo um alerta aberto de cada tipo por vínculo.
    op.create_index("ux_alertas_abertos", "alertas", ["atribuicao_id", "tipo"], unique=True,
                    postgresql_where=sa.text("fim IS NULL"))
    op.create_index("ix_alertas_pesquisador_inicio", "alertas", ["pesquisador_id", "inicio"])
    op.create_index("ix_alertas_pulseira_inicio", "alertas", ["pulseira_id", "inicio"])


def downgrade() -> None:
    op.drop_table("alertas")
    op.drop_table("limites")
