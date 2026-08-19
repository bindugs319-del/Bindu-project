"""add company details and invoice/po numbering to business_profiles

Revision ID: c4d5e6f7a8b9
Revises: a2b3c4d5e6f7
Create Date: 2026-08-08 00:00:00.000000

Adds the fields needed to (1) auto-fill "your company" details on new
invoices from a saved profile, and (2) auto-generate the next invoice
number / PO number.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d5e6f7a8b9'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('business_profiles', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('business_profiles', sa.Column('pan', sa.String(length=10), nullable=True))
    op.add_column('business_profiles', sa.Column('cin', sa.String(length=30), nullable=True))
    op.add_column('business_profiles', sa.Column('msme_no', sa.String(length=50), nullable=True))
    op.add_column(
        'business_profiles',
        sa.Column('next_invoice_seq', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column(
        'business_profiles',
        sa.Column('next_po_seq', sa.Integer(), nullable=False, server_default='1'),
    )


def downgrade():
    op.drop_column('business_profiles', 'next_po_seq')
    op.drop_column('business_profiles', 'next_invoice_seq')
    op.drop_column('business_profiles', 'msme_no')
    op.drop_column('business_profiles', 'cin')
    op.drop_column('business_profiles', 'pan')
    op.drop_column('business_profiles', 'address')
