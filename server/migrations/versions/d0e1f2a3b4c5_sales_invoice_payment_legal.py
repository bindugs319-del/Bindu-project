"""add payment and legal-support tracking to sales_invoices

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-14 01:00:00.000000

Mirrors the equivalent purchase_orders columns so the Invoices page can
offer Mark Paid, Send Reminder, and Send to Legal Support actions the
same way the Purchase Orders page does.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sales_invoices', sa.Column('payment_completed_at', sa.DateTime(), nullable=True))
    op.add_column('sales_invoices', sa.Column('payment_receipt_url', sa.String(length=500), nullable=True))
    op.add_column('sales_invoices', sa.Column('payment_receipt_filename', sa.String(length=255), nullable=True))
    op.add_column('sales_invoices', sa.Column('legal_support_status', sa.String(length=50), nullable=True))
    op.add_column('sales_invoices', sa.Column('legal_support_requested_at', sa.DateTime(), nullable=True))
    op.add_column('sales_invoices', sa.Column('legal_support_reason', sa.Text(), nullable=True))
    op.add_column('sales_invoices', sa.Column('legal_support_evidence_url', sa.String(length=500), nullable=True))
    op.add_column('sales_invoices', sa.Column('legal_support_evidence_filename', sa.String(length=255), nullable=True))
    op.add_column('sales_invoices', sa.Column('legal_support_requested_by', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('sales_invoices', 'legal_support_requested_by')
    op.drop_column('sales_invoices', 'legal_support_evidence_filename')
    op.drop_column('sales_invoices', 'legal_support_evidence_url')
    op.drop_column('sales_invoices', 'legal_support_reason')
    op.drop_column('sales_invoices', 'legal_support_requested_at')
    op.drop_column('sales_invoices', 'legal_support_status')
    op.drop_column('sales_invoices', 'payment_receipt_filename')
    op.drop_column('sales_invoices', 'payment_receipt_url')
    op.drop_column('sales_invoices', 'payment_completed_at')
