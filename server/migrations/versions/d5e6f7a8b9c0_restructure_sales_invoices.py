"""restructure sales_invoices to match supervisor spec sheet

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-09 00:00:00.000000

sales_invoices is empty in every environment this has been tested
against, so this migration restructures it directly (add/rename/drop/
retype columns) rather than doing a data migration. If this ever runs
against a database that already has invoice rows, back them up first —
downgrade() cannot recover dropped/renamed data.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    # --- New columns: issuing company's own details (snapshot) ---
    op.add_column('sales_invoices', sa.Column('company_name', sa.String(length=255), nullable=True))
    op.add_column('sales_invoices', sa.Column('company_address', sa.Text(), nullable=True))
    op.add_column('sales_invoices', sa.Column('company_gstin', sa.String(length=15), nullable=True))
    op.add_column('sales_invoices', sa.Column('company_pan', sa.String(length=10), nullable=True))
    op.add_column('sales_invoices', sa.Column('cin', sa.String(length=30), nullable=True))

    # --- New columns: document details ---
    op.add_column('sales_invoices', sa.Column('payment_terms', sa.String(length=100), nullable=True))
    op.add_column('sales_invoices', sa.Column('expected_delivery_date', sa.Date(), nullable=True))
    op.add_column('sales_invoices', sa.Column('currency', sa.String(length=3), nullable=False, server_default='INR'))
    op.add_column('sales_invoices', sa.Column('tax_breakdown', sa.JSON(), nullable=True))
    op.add_column('sales_invoices', sa.Column('bill_to', sa.JSON(), nullable=True))
    op.add_column('sales_invoices', sa.Column('ship_to', sa.JSON(), nullable=True))

    # --- Rename customer_* -> counterparty_* ---
    op.alter_column('sales_invoices', 'customer_name', new_column_name='counterparty_name')
    op.alter_column('sales_invoices', 'customer_gstin', new_column_name='counterparty_gstin')
    op.alter_column('sales_invoices', 'customer_pan', new_column_name='counterparty_pan')

    # --- Rename is_sez_supply -> is_sez_export ---
    op.alter_column('sales_invoices', 'is_sez_supply', new_column_name='is_sez_export')

    # --- Drop columns superseded by bill_to / ship_to JSON ---
    op.drop_column('sales_invoices', 'customer_address')
    op.drop_column('sales_invoices', 'ship_to_name')
    op.drop_column('sales_invoices', 'ship_to_address')

    # --- Change timestamp columns to plain dates (no time component) ---
    op.alter_column(
        'sales_invoices', 'invoice_date',
        existing_type=sa.DateTime(), type_=sa.Date(),
        postgresql_using='invoice_date::date',
    )
    op.alter_column(
        'sales_invoices', 'payment_due_date',
        existing_type=sa.DateTime(), type_=sa.Date(),
        postgresql_using='payment_due_date::date',
    )
    op.alter_column(
        'sales_invoices', 'po_date',
        existing_type=sa.DateTime(), type_=sa.Date(),
        postgresql_using='po_date::date',
    )
    op.alter_column(
        'sales_invoices', 'lut_filing_date',
        existing_type=sa.DateTime(), type_=sa.Date(),
        postgresql_using='lut_filing_date::date',
    )


def downgrade():
    op.alter_column(
        'sales_invoices', 'lut_filing_date',
        existing_type=sa.Date(), type_=sa.DateTime(),
        postgresql_using='lut_filing_date::timestamp',
    )
    op.alter_column(
        'sales_invoices', 'po_date',
        existing_type=sa.Date(), type_=sa.DateTime(),
        postgresql_using='po_date::timestamp',
    )
    op.alter_column(
        'sales_invoices', 'payment_due_date',
        existing_type=sa.Date(), type_=sa.DateTime(),
        postgresql_using='payment_due_date::timestamp',
    )
    op.alter_column(
        'sales_invoices', 'invoice_date',
        existing_type=sa.Date(), type_=sa.DateTime(),
        postgresql_using='invoice_date::timestamp',
    )

    op.add_column('sales_invoices', sa.Column('ship_to_address', sa.Text(), nullable=True))
    op.add_column('sales_invoices', sa.Column('ship_to_name', sa.String(length=255), nullable=True))
    op.add_column('sales_invoices', sa.Column('customer_address', sa.Text(), nullable=True))

    op.alter_column('sales_invoices', 'is_sez_export', new_column_name='is_sez_supply')

    op.alter_column('sales_invoices', 'counterparty_pan', new_column_name='customer_pan')
    op.alter_column('sales_invoices', 'counterparty_gstin', new_column_name='customer_gstin')
    op.alter_column('sales_invoices', 'counterparty_name', new_column_name='customer_name')

    op.drop_column('sales_invoices', 'ship_to')
    op.drop_column('sales_invoices', 'bill_to')
    op.drop_column('sales_invoices', 'tax_breakdown')
    op.drop_column('sales_invoices', 'currency')
    op.drop_column('sales_invoices', 'expected_delivery_date')
    op.drop_column('sales_invoices', 'payment_terms')

    op.drop_column('sales_invoices', 'cin')
    op.drop_column('sales_invoices', 'company_pan')
    op.drop_column('sales_invoices', 'company_gstin')
    op.drop_column('sales_invoices', 'company_address')
    op.drop_column('sales_invoices', 'company_name')
