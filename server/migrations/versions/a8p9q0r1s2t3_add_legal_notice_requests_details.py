"""add details column to legal_notice_requests

The LegalNoticeRequest model has a `details` JSON column, but no
migration ever created it, so a database built from migrations (e.g. a
fresh Render Postgres) would fail on any legal-notice query.

Revision ID: a8p9q0r1s2t3
Revises: z7o8p9q0r1s2
Create Date: 2026-11-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a8p9q0r1s2t3'
down_revision: Union[str, None] = 'z7o8p9q0r1s2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE legal_notice_requests ADD COLUMN IF NOT EXISTS details JSON")


def downgrade() -> None:
    op.execute("ALTER TABLE legal_notice_requests DROP COLUMN IF EXISTS details")
