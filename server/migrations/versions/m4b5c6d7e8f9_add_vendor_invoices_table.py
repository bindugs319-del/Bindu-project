"""add vendor_invoices table

The VendorInvoice model (app/models/__init__.py) was added to the codebase
without a matching Alembic migration, so `vendor_invoices` was never
created in any database that only ran `alembic upgrade head` — it only
existed on databases where it had been created by hand. This migration
brings it in line with the model.

Revision ID: m4b5c6d7e8f9
Revises: l3a4b5c6d7e8
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'm4b5c6d7e8f9'
down_revision: Union[str, None] = 'l3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'vendor_invoices',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('vendor_name', sa.String(length=255), nullable=False),
        sa.Column('vendor_gstin', sa.String(length=15), nullable=True),
        sa.Column('vendor_pan', sa.String(length=10), nullable=True),
        sa.Column('vendor_email', sa.String(length=255), nullable=True),
        sa.Column('vendor_phone', sa.String(length=20), nullable=True),
        sa.Column('vendor_address', sa.Text(), nullable=True),
        sa.Column('invoice_number', sa.String(length=100), nullable=False),
        sa.Column('invoice_date', sa.Date(), nullable=False),
        sa.Column('payment_due_date', sa.Date(), nullable=False),
        sa.Column('payment_terms', sa.String(length=100), nullable=True),
        sa.Column('place_of_supply', sa.String(length=100), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('items', sa.JSON(), nullable=True),
        sa.Column('subtotal', sa.Float(), nullable=False, server_default='0'),
        sa.Column('tax_breakdown', sa.JSON(), nullable=True),
        sa.Column('tax_amount', sa.Float(), nullable=False, server_default='0'),
        sa.Column('total', sa.Float(), nullable=False, server_default='0'),
        sa.Column('balance_due', sa.Float(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=True, server_default='Unpaid'),
        sa.Column('archived', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('payment_completed_at', sa.DateTime(), nullable=True),
        sa.Column('payment_receipt_url', sa.String(length=500), nullable=True),
        sa.Column('payment_receipt_filename', sa.String(length=255), nullable=True),
        sa.Column('document_url', sa.String(length=500), nullable=True),
        sa.Column('document_filename', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_vendor_invoices_id'), 'vendor_invoices', ['id'])
    op.create_index(op.f('ix_vendor_invoices_company_id'), 'vendor_invoices', ['company_id'])
    op.create_index(op.f('ix_vendor_invoices_user_id'), 'vendor_invoices', ['user_id'])
    op.create_index(op.f('ix_vendor_invoices_vendor_name'), 'vendor_invoices', ['vendor_name'])
    op.create_index(op.f('ix_vendor_invoices_vendor_gstin'), 'vendor_invoices', ['vendor_gstin'])
    op.create_index(op.f('ix_vendor_invoices_invoice_number'), 'vendor_invoices', ['invoice_number'])
    op.create_index(op.f('ix_vendor_invoices_invoice_date'), 'vendor_invoices', ['invoice_date'])
    op.create_index(op.f('ix_vendor_invoices_payment_due_date'), 'vendor_invoices', ['payment_due_date'])
    op.create_index(op.f('ix_vendor_invoices_status'), 'vendor_invoices', ['status'])
    op.create_index(op.f('ix_vendor_invoices_archived'), 'vendor_invoices', ['archived'])
    op.create_index(op.f('ix_vendor_invoices_payment_completed_at'), 'vendor_invoices', ['payment_completed_at'])
    op.create_index(op.f('ix_vendor_invoices_created_at'), 'vendor_invoices', ['created_at'])
    op.create_index('idx_vendor_invoice_company_status', 'vendor_invoices', ['company_id', 'status'])
    op.create_index('idx_vendor_invoice_number', 'vendor_invoices', ['invoice_number'])
    op.create_index('idx_vendor_invoice_due_date', 'vendor_invoices', ['payment_due_date'])


def downgrade() -> None:
    op.drop_index('idx_vendor_invoice_due_date', table_name='vendor_invoices')
    op.drop_index('idx_vendor_invoice_number', table_name='vendor_invoices')
    op.drop_index('idx_vendor_invoice_company_status', table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_created_at'), table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_payment_completed_at'), table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_archived'), table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_status'), table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_payment_due_date'), table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_invoice_date'), table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_invoice_number'), table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_vendor_gstin'), table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_vendor_name'), table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_user_id'), table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_company_id'), table_name='vendor_invoices')
    op.drop_index(op.f('ix_vendor_invoices_id'), table_name='vendor_invoices')
    op.drop_table('vendor_invoices')
