"""add legal_support_requested_by column to purchase_orders

routes/core.py's send_to_legal_support() writes to
purchase_orders.legal_support_requested_by, but this column was only ever
defined on the SalesInvoice model (the code was evidently copy-pasted from
the invoice version) — it was never added to the PurchaseOrder model or
the database. Every legal support request submitted from a PO crashed
immediately on this UPDATE with "column ... does not exist", before ever
reaching the workflow-creation or notification code that follows it.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'purchase_orders'"
    ))}
    if 'legal_support_requested_by' not in existing_cols:
        op.add_column('purchase_orders', sa.Column('legal_support_requested_by', sa.String(length=255), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'purchase_orders'"
    ))}
    if 'legal_support_requested_by' in existing_cols:
        op.drop_column('purchase_orders', 'legal_support_requested_by')
