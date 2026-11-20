"""Pesquisadores, atribuições pulseira ↔ pesquisador e atribuicao_id nas leituras

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Necessária para a EXCLUDE combinar igualdade de inteiro (=) com sobreposição de intervalo (&&).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "pesquisadores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),   # sempre em minúsculas
        sa.Column("data_nascimento", sa.Date),
        sa.Column("observacoes", sa.Text),
        sa.Column("ativo", sa.Boolean, server_default=sa.true(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("email = lower(email)", name="ck_pesquisadores_email_minusculo"),
    )

    # Quem está usando cada pulseira, por período. fim NULL = vínculo ativo.
    op.create_table(
        "atribuicoes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("pulseira_id", sa.Integer, sa.ForeignKey("pulseiras.id"), nullable=False),
        sa.Column("pesquisador_id", sa.Integer, sa.ForeignKey("pesquisadores.id"), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("fim", sa.DateTime(timezone=True)),
        sa.Column("criada_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("fim IS NULL OR fim > inicio", name="ck_atribuicoes_periodo"),
    )
    # Sem sobreposição de períodos: uma pessoa por pulseira e uma pulseira por pessoa,
    # também no histórico. tstzrange(inicio, NULL) = intervalo aberto (vínculo ativo).
    op.execute("""
        ALTER TABLE atribuicoes ADD CONSTRAINT ex_atribuicoes_pulseira
        EXCLUDE USING gist (pulseira_id WITH =, tstzrange(inicio, fim, '[)') WITH &&)
    """)
    op.execute("""
        ALTER TABLE atribuicoes ADD CONSTRAINT ex_atribuicoes_pesquisador
        EXCLUDE USING gist (pesquisador_id WITH =, tstzrange(inicio, fim, '[)') WITH &&)
    """)
    op.create_index("ix_atribuicoes_ativas", "atribuicoes", ["pulseira_id"],
                    postgresql_where=sa.text("fim IS NULL"))

    # A allowlist recarrega quando um vínculo muda ou o nome de um pesquisador muda.
    for tabela in ("atribuicoes", "pesquisadores"):
        op.execute(f"""
            CREATE TRIGGER {tabela}_notificar
            AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON {tabela}
            FOR EACH STATEMENT EXECUTE FUNCTION notificar_alteracao('atribuicoes_alteradas');
        """)

    op.add_column("leituras_bpm", sa.Column("atribuicao_id", sa.Integer, sa.ForeignKey("atribuicoes.id")))
    op.create_index("ix_leituras_atribuicao_ts", "leituras_bpm", ["atribuicao_id", "ts"])


def downgrade() -> None:
    op.drop_index("ix_leituras_atribuicao_ts", table_name="leituras_bpm")
    op.drop_column("leituras_bpm", "atribuicao_id")
    for tabela in ("atribuicoes", "pesquisadores"):
        op.execute(f"DROP TRIGGER IF EXISTS {tabela}_notificar ON {tabela}")
    op.drop_table("atribuicoes")
    op.drop_table("pesquisadores")
