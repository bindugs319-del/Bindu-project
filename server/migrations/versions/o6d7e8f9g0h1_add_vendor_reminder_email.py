"""add vendor_reminder_email to app_settings

Adds the default recipient email for automatic vendor-invoice payment
reminders (see the new /vendor-invoices/settings endpoint and the
vendor-invoice block in _daily_tasks_runner). Reuses the existing
single-row app_settings table rather than creating a new one, matching
how payment_window_days already works.

Revision ID: o6d7e8f9g0h1
Revises: n5c6d7e8f9g0
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'o6d7e8f9g0h1'
down_revision: Union[str, None] = 'n5c6d7e8f9g0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('app_settings', sa.Column('vendor_reminder_email', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('app_settings', 'vendor_reminder_email')
