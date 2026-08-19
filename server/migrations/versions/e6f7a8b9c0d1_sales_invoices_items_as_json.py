"""sales_invoices: items as JSON blob, rename subtotal/total, drop item table

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-08-09 01:00:00.000000

Per the supervisor's spec sheet with example values:
- items are now a single JSON array column on sales_invoices, e.g.
  [{"desc": "...", "hsn": "...", "qty": ..., "rate": ..., "amount": ...}]
  instead of a separate sales_invoice_items table.
- bill_to / ship_to simplify to {"name": ..., "address": ...} — no
  application-level schema change needed here since they were already
  JSON columns, just a change in what shape the app writes into them.
- sub_total -> subtotal, total_amount -> total.

sales_invoices is still empty in every environment this has been tested
against, so this drops sales_invoice_items outright rather than
migrating its rows into the new JSON column. If this ever runs against
a database with real invoice data, back it up first — downgrade()
cannot recover the dropped table's data.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sales_invoices', sa.Column('items', sa.JSON(), nullable=True))
    op.alter_column('sales_invoices', 'sub_total', new_column_name='subtotal')
    op.alter_column('sales_invoices', 'total_amount', new_column_name='total')

    op.drop_index('ix_sales_invoice_items_id', table_name='sales_invoice_items')
    op.drop_index('ix_sales_invoice_items_invoice_id', table_name='sales_invoice_items')
    op.drop_table('sales_invoice_items')


def downgrade():
    op.create_table(
        'sales_invoice_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('invoice_id', sa.String(length=36), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('hsn_sac', sa.String(length=20), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('rate', sa.Float(), nullable=False),
        sa.Column('igst_percent', sa.Float(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['sales_invoices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sales_invoice_items_id', 'sales_invoice_items', ['id'], unique=False)
    op.create_index('ix_sales_invoice_items_invoice_id', 'sales_invoice_items', ['invoice_id'], unique=False)

    op.alter_column('sales_invoices', 'total', new_column_name='total_amount')
    op.alter_column('sales_invoices', 'subtotal', new_column_name='sub_total')
    op.drop_column('sales_invoices', 'items')
