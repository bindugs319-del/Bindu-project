"""extend scheduled_reminders to support sales invoices

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-14 02:00:00.000000

scheduled_reminders was purchase-order-only (purchase_order_id NOT
NULL). This makes that column nullable and adds a nullable
sales_invoice_id, so a reminder row can belong to either a PO or a
sales invoice (exactly one of the two should be set).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('scheduled_reminders', 'purchase_order_id', nullable=True)
    op.add_column('scheduled_reminders', sa.Column('sales_invoice_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(
        'fk_scheduled_reminders_sales_invoice_id',
        'scheduled_reminders', 'sales_invoices',
        ['sales_invoice_id'], ['id'], ondelete='CASCADE',
    )
    op.create_index('ix_scheduled_reminders_sales_invoice_id', 'scheduled_reminders', ['sales_invoice_id'])


def downgrade():
    op.drop_index('ix_scheduled_reminders_sales_invoice_id', table_name='scheduled_reminders')
    op.drop_constraint('fk_scheduled_reminders_sales_invoice_id', 'scheduled_reminders', type_='foreignkey')
    op.drop_column('scheduled_reminders', 'sales_invoice_id')
    op.alter_column('scheduled_reminders', 'purchase_order_id', nullable=False)
