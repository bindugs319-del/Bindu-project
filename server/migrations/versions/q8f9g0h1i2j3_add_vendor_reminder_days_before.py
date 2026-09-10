"""add vendor_reminder_days_before to app_settings

Makes the "starts N days before due date" threshold for automatic
vendor-invoice reminders configurable instead of hardcoded (see
_daily_tasks_runner in main.py). Reuses the same single-row app_settings
table as vendor_reminder_email — set together on the Vendor Bills page.

Revision ID: q8f9g0h1i2j3
Revises: p7e8f9g0h1i2
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'q8f9g0h1i2j3'
down_revision: Union[str, None] = 'p7e8f9g0h1i2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('app_settings', sa.Column('vendor_reminder_days_before', sa.Integer(), nullable=False, server_default='5'))


def downgrade() -> None:
    op.drop_column('app_settings', 'vendor_reminder_days_before')
