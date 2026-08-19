"""add operations/master admin approval workflow columns to sales_invoices

Revision ID: b7c8d9e0f1a2
Revises: f7a8b9c0d1e2
Create Date: 2026-08-13 00:00:00.000000

Adds the same User -> Operations -> Master Admin approval workflow that
already exists on the Invoice (receivables) model to SalesInvoice, so
sales invoices submitted from the Invoices page can be routed through
Operations Team review and Master Admin final approval and show up on
their dashboards.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c8d9e0f1a2'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sales_invoices', sa.Column('workflow_status', sa.String(length=40), nullable=True, server_default='Draft'))
    op.add_column('sales_invoices', sa.Column('operations_reviewed_by', sa.String(length=36), nullable=True))
    op.add_column('sales_invoices', sa.Column('operations_reviewed_at', sa.DateTime(), nullable=True))
    op.add_column('sales_invoices', sa.Column('operations_notes', sa.Text(), nullable=True))
    op.add_column('sales_invoices', sa.Column('master_approved_by', sa.String(length=36), nullable=True))
    op.add_column('sales_invoices', sa.Column('master_approved_at', sa.DateTime(), nullable=True))
    op.add_column('sales_invoices', sa.Column('master_notes', sa.Text(), nullable=True))
    op.create_index('ix_sales_invoices_workflow_status', 'sales_invoices', ['workflow_status'])


def downgrade():
    op.drop_index('ix_sales_invoices_workflow_status', table_name='sales_invoices')
    op.drop_column('sales_invoices', 'master_notes')
    op.drop_column('sales_invoices', 'master_approved_at')
    op.drop_column('sales_invoices', 'master_approved_by')
    op.drop_column('sales_invoices', 'operations_notes')
    op.drop_column('sales_invoices', 'operations_reviewed_at')
    op.drop_column('sales_invoices', 'operations_reviewed_by')
    op.drop_column('sales_invoices', 'workflow_status')
