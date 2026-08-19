"""add counterparty_phone to sales_invoices

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
Create Date: 2026-08-14 00:00:00.000000

Adds counterparty_phone so the Invoices page can show/collect a mobile
number, mirroring vendor_phone on purchase_orders. counterparty_email
already exists as a column on sales_invoices (added at some earlier
point but never mapped in the model) — this migration also does not
touch it, the model change alone is enough to start using it.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9d0e1f2a3b4'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sales_invoices', sa.Column('counterparty_phone', sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column('sales_invoices', 'counterparty_phone')
