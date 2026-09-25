"""widen app_settings.id column

app_settings.id was VARCHAR(36), sized for a plain UUID. But
app/routes/vendor_invoices.py's vendor-reminder settings endpoint uses
`current_user.company_id` when set, and otherwise falls back to
`f"user:{current_user.id}"` — a 41-character string ("user:" + a
36-char UUID) — for users with no company (e.g. the seeded MASTER_ADMIN
account, which app/scripts/seed_admin.py never assigns a company_id).

That 41-character value silently failed to insert into a 36-character
column with a genuine Postgres "value too long" error, which the app's
generic error-handler middleware then reported to the user as
"Database service is unavailable" — a misleading message for what was
actually a column-width bug, not an outage.

Revision ID: u2j3k4l5m6n7
Revises: t1i2j3k4l5m6
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'u2j3k4l5m6n7'
down_revision: Union[str, None] = 't1i2j3k4l5m6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'app_settings', 'id',
        existing_type=sa.String(length=36),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Not reversible if any row's id is already longer than 36 chars
    # (exactly the case this migration exists to allow) — this would
    # fail loudly rather than silently truncating real data, which is
    # the right behavior for a downgrade nobody should actually need.
    op.alter_column(
        'app_settings', 'id',
        existing_type=sa.String(length=64),
        type_=sa.String(length=36),
        existing_nullable=False,
    )
