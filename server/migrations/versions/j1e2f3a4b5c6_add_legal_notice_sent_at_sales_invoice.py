"""add legal_notice_sent_at to sales_invoices

Sales invoice reminders can now optionally attach a formal legal
notice PDF, mirroring purchase_orders.legal_notice_sent_at. This
timestamp records when that was last done for a given invoice.

Revision ID: j1e2f3a4b5c6
Revises: i8d9e0f1a2b3
Create Date: 2026-08-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j1e2f3a4b5c6'
down_revision: Union[str, None] = 'i8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'sales_invoices'"
    ))}
    if 'legal_notice_sent_at' not in existing_cols:
        op.add_column('sales_invoices', sa.Column('legal_notice_sent_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'sales_invoices'"
    ))}
    if 'legal_notice_sent_at' in existing_cols:
        op.drop_column('sales_invoices', 'legal_notice_sent_at')
