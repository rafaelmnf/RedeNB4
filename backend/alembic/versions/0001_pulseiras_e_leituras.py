"""APs, pulseiras, leituras de BPM e NOTIFY da allowlist

Revision ID: 0001
Revises:
Create Date: 2026-11-15
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("identificador", sa.String(100), nullable=False, unique=True),
        sa.Column("zona", sa.String(100)),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "pulseiras",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("mac", postgresql.MACADDR, nullable=False, unique=True),
        sa.Column("apelido", sa.String(100)),
        sa.Column("ativa", sa.Boolean, server_default=sa.true(), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("removida_em", sa.DateTime(timezone=True)),
    )
    # Série temporal: PK (id, ts) para permitir hypertable do TimescaleDB no futuro.
    op.create_table(
        "leituras_bpm",
        sa.Column("id", sa.BigInteger, sa.Identity(always=False), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pulseira_id", sa.Integer, sa.ForeignKey("pulseiras.id"), nullable=False),
        sa.Column("bpm", sa.SmallInteger, nullable=False),
        sa.Column("rssi", sa.REAL),
        sa.Column("ap_id", sa.Integer, sa.ForeignKey("aps.id")),
        sa.PrimaryKeyConstraint("id", "ts"),
    )
    op.create_index("ix_leituras_pulseira_ts", "leituras_bpm", ["pulseira_id", "ts"])

    # Avisa a ingestão (LISTEN) sempre que a tabela muda, inclusive por edição manual no psql.
    op.execute("""
        CREATE FUNCTION notificar_alteracao() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_notify(TG_ARGV[0], TG_OP);
            RETURN NULL;
        END $$;
    """)
    op.execute("""
        CREATE TRIGGER pulseiras_notificar
        AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON pulseiras
        FOR EACH STATEMENT EXECUTE FUNCTION notificar_alteracao('pulseiras_alteradas');
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS pulseiras_notificar ON pulseiras")
    op.execute("DROP FUNCTION IF EXISTS notificar_alteracao()")
    op.drop_table("leituras_bpm")
    op.drop_table("pulseiras")
    op.drop_table("aps")
