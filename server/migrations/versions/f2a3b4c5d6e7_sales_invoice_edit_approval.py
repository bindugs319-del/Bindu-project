"""add PO-style edit-approval columns to sales_invoices

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-14 03:00:00.000000

Adds approval_status and pending_changes to sales_invoices, mirroring
purchase_orders' edit-approval mechanism: editing an existing invoice
now stores the changes here instead of applying them immediately, and
a Master Admin approves or rejects them via new endpoints. This
replaces the earlier Operations-Team-then-Master-Admin "submit for
approval" workflow for invoices, which is no longer used.

The master_approved_by / master_approved_at / master_notes columns
added in an earlier migration are reused here for the approval
decision (who approved/rejected, when, with what notes), so nothing
new is needed for that part.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sales_invoices', sa.Column('approval_status', sa.String(length=50), nullable=True))
    op.add_column('sales_invoices', sa.Column('pending_changes', sa.JSON(), nullable=True))
    op.create_index('ix_sales_invoices_approval_status', 'sales_invoices', ['approval_status'])


def downgrade():
    op.drop_index('ix_sales_invoices_approval_status', table_name='sales_invoices')
    op.drop_column('sales_invoices', 'pending_changes')
    op.drop_column('sales_invoices', 'approval_status')