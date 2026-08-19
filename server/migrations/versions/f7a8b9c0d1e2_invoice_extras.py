"""add bank details, round-off, reverse charge, eway bill, discount, exchange rate

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-08-09 02:00:00.000000

Adds:
- business_profiles: bank_account_name, bank_account_number, bank_ifsc,
  bank_name, bank_upi_id (source of the snapshot below)
- sales_invoices: discount_amount, round_off, exchange_rate,
  reverse_charge, eway_bill_number, and the same 5 bank_* fields as a
  per-invoice snapshot

status/document_url already existed on sales_invoices — no migration
needed for the status workflow or file-attachment features, just
application-level changes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('business_profiles', sa.Column('bank_account_name', sa.String(length=255), nullable=True))
    op.add_column('business_profiles', sa.Column('bank_account_number', sa.String(length=50), nullable=True))
    op.add_column('business_profiles', sa.Column('bank_ifsc', sa.String(length=20), nullable=True))
    op.add_column('business_profiles', sa.Column('bank_name', sa.String(length=255), nullable=True))
    op.add_column('business_profiles', sa.Column('bank_upi_id', sa.String(length=100), nullable=True))

    op.add_column('sales_invoices', sa.Column('discount_amount', sa.Float(), nullable=False, server_default='0'))
    op.add_column('sales_invoices', sa.Column('round_off', sa.Float(), nullable=False, server_default='0'))
    op.add_column('sales_invoices', sa.Column('exchange_rate', sa.Float(), nullable=False, server_default='1'))
    op.add_column('sales_invoices', sa.Column('reverse_charge', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('sales_invoices', sa.Column('eway_bill_number', sa.String(length=50), nullable=True))
    op.add_column('sales_invoices', sa.Column('bank_account_name', sa.String(length=255), nullable=True))
    op.add_column('sales_invoices', sa.Column('bank_account_number', sa.String(length=50), nullable=True))
    op.add_column('sales_invoices', sa.Column('bank_ifsc', sa.String(length=20), nullable=True))
    op.add_column('sales_invoices', sa.Column('bank_name', sa.String(length=255), nullable=True))
    op.add_column('sales_invoices', sa.Column('bank_upi_id', sa.String(length=100), nullable=True))


def downgrade():
    op.drop_column('sales_invoices', 'bank_upi_id')
    op.drop_column('sales_invoices', 'bank_name')
    op.drop_column('sales_invoices', 'bank_ifsc')
    op.drop_column('sales_invoices', 'bank_account_number')
    op.drop_column('sales_invoices', 'bank_account_name')
    op.drop_column('sales_invoices', 'eway_bill_number')
    op.drop_column('sales_invoices', 'reverse_charge')
    op.drop_column('sales_invoices', 'exchange_rate')
    op.drop_column('sales_invoices', 'round_off')
    op.drop_column('sales_invoices', 'discount_amount')

    op.drop_column('business_profiles', 'bank_upi_id')
    op.drop_column('business_profiles', 'bank_name')
    op.drop_column('business_profiles', 'bank_ifsc')
    op.drop_column('business_profiles', 'bank_account_number')
    op.drop_column('business_profiles', 'bank_account_name')
