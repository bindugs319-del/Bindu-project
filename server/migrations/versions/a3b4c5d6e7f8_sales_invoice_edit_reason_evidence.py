"""add edit-approval reason/evidence fields to sales_invoices

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-14 04:00:00.000000

Supports the two-stage (Operations Truth Check -> Master Admin final
approval) edit-approval flow, mirroring purchase_orders' EditPOModal +
WorkflowService.start_po_approval exactly. approval_status and
pending_changes already exist from the previous migration; this adds
the reason/evidence fields that go with them.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sales_invoices', sa.Column('pending_change_reason', sa.Text(), nullable=True))
    op.add_column('sales_invoices', sa.Column('pending_change_evidence_url', sa.String(length=500), nullable=True))
    op.add_column('sales_invoices', sa.Column('pending_change_evidence_filename', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('sales_invoices', 'pending_change_evidence_filename')
    op.drop_column('sales_invoices', 'pending_change_evidence_url')
    op.drop_column('sales_invoices', 'pending_change_reason')
