"""add exchange_rate to vendor_invoices

Vendor invoices track their own currency but had no way to convert to
INR, so any dashboard/list total summed a $8,364.00 USD bill and a
₹1,93,732.90 INR bill as if they were the same currency — off by roughly
80x for the USD one. Mirrors SalesInvoice.exchange_rate exactly (see
models.py): total * exchange_rate gives the INR-equivalent, manually
entered per invoice (defaults to 1.0, i.e. already-INR invoices are
unaffected), same as sales invoices already work.

Revision ID: p7e8f9g0h1i2
Revises: o6d7e8f9g0h1
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'p7e8f9g0h1i2'
down_revision: Union[str, None] = 'o6d7e8f9g0h1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vendor_invoices', sa.Column('exchange_rate', sa.Float(), nullable=False, server_default='1.0'))


def downgrade() -> None:
    op.drop_column('vendor_invoices', 'exchange_rate')
