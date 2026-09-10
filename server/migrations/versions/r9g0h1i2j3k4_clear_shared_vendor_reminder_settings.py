"""clear leftover cross-tenant vendor reminder settings

Earlier versions of the vendor-invoice reminder feature stored the
reminder email/days-before on the single shared app_settings row
(id='default') — the same row payment_window_days legitimately uses as a
true global setting. That meant every company using this app shared one
reminder email, which is a real cross-tenant data leak: Company A's
vendor-bill reminders could be sent to Company B's saved address.

Settings are now scoped per company (see get_vendor_invoice_settings in
vendor_invoices.py — id = company_id, or 'user:{user_id}' as a fallback).
This migration only clears the two leftover fields on the 'default' row
itself — payment_window_days and the row itself are untouched — so stale
cross-tenant data can't linger or be mistaken for a real per-company
value. Anyone who had a reminder email configured before this fix will
need to re-enter it once, now correctly scoped to just their own company.

Revision ID: r9g0h1i2j3k4
Revises: q8f9g0h1i2j3
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'r9g0h1i2j3k4'
down_revision: Union[str, None] = 'q8f9g0h1i2j3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE app_settings
        SET vendor_reminder_email = NULL, vendor_reminder_days_before = 5
        WHERE id = 'default'
    """))


def downgrade() -> None:
    # Not reversible — the original (leaked) value is intentionally not
    # recoverable.
    pass
