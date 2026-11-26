"""Índice BRIN em leituras_bpm.ts, para a limpeza das leituras antigas

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-22

As leituras entram em ordem de tempo, então um BRIN (poucos KB) basta para achar as
antigas sem varrer a tabela inteira.
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX ix_leituras_ts_brin ON leituras_bpm USING brin (ts)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_leituras_ts_brin")
