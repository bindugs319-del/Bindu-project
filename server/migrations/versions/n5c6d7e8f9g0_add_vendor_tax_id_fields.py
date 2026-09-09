"""add generic vendor_tax_id / vendor_tax_id_type fields

Step 1 of the vendor-invoice tax-ID redesign (see conversation notes).
Roughly half of real vendor invoices are foreign (VAT/FEIN/Chamber of
Commerce numbers, not GSTIN/PAN), so vendor_gstin/vendor_pan are being
replaced with a generic (value, type) pair. This migration only ADDS the
new columns and backfills them from the old ones — it deliberately does
NOT drop vendor_gstin/vendor_pan yet, so the backend can dual-write to
both during rollout and nothing breaks mid-deploy. A follow-up migration
drops the old columns once the new ones are confirmed working in
production.

Revision ID: n5c6d7e8f9g0
Revises: m4b5c6d7e8f9
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'n5c6d7e8f9g0'
down_revision: Union[str, None] = 'm4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vendor_invoices', sa.Column('vendor_tax_id', sa.String(length=30), nullable=True))
    op.add_column('vendor_invoices', sa.Column('vendor_tax_id_type', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_vendor_invoices_vendor_tax_id'), 'vendor_invoices', ['vendor_tax_id'])

    # Backfill from the existing columns so current records keep working
    # unchanged: any row with a GSTIN becomes type='GSTIN', any row with
    # only a PAN becomes type='PAN'. GSTIN takes priority since a row
    # could in theory have stray data in both.
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE vendor_invoices
        SET vendor_tax_id = vendor_gstin, vendor_tax_id_type = 'GSTIN'
        WHERE vendor_gstin IS NOT NULL AND vendor_gstin != ''
    """))
    conn.execute(sa.text("""
        UPDATE vendor_invoices
        SET vendor_tax_id = vendor_pan, vendor_tax_id_type = 'PAN'
        WHERE vendor_tax_id IS NULL AND vendor_pan IS NOT NULL AND vendor_pan != ''
    """))


def downgrade() -> None:
    op.drop_index(op.f('ix_vendor_invoices_vendor_tax_id'), table_name='vendor_invoices')
    op.drop_column('vendor_invoices', 'vendor_tax_id_type')
    op.drop_column('vendor_invoices', 'vendor_tax_id')
