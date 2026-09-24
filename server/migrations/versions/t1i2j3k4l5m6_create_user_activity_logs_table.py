"""create user_activity_logs table

app/routes/activity.py logs a row here on nearly every authenticated
request (see main.py's activity-logging middleware / log_activity()),
and app/routes/admin.py reads it back for the admin activity feed —
but no migration ever created the table, so on a fresh database every
one of those inserts has been silently failing with
`UndefinedTableError: relation "user_activity_logs" does not exist`,
visible in Render's logs (same class of issue as the earlier missing
system_settings table).

Column set here matches exactly what the existing code reads/writes:
- activity.py's log_activity() INSERTs: user_id, user_email, user_role,
  action, page, entity_type, entity_id, details, ip_address.
- activity.py's /logs and /logs/summary endpoints ORDER BY / SELECT a
  `timestamp` column.
- admin.py's activity feed instead selects `al.id` and `al.created_at`
  for the same table.
Both `timestamp` and `created_at` are included (both DEFAULT NOW(),
populated automatically since neither is in the INSERT's column list)
so neither code path breaks — rather than picking one and silently
breaking the other, which is how this was written across two files.

Revision ID: t1i2j3k4l5m6
Revises: s0h1i2j3k4l5
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 't1i2j3k4l5m6'
down_revision: Union[str, None] = 's0h1i2j3k4l5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_activity_logs (
            id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
            user_id VARCHAR(36),
            user_email VARCHAR(255),
            user_role VARCHAR(100),
            action VARCHAR(255),
            page VARCHAR(255),
            entity_type VARCHAR(100),
            entity_id VARCHAR(255),
            details TEXT,
            ip_address VARCHAR(64),
            "timestamp" TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))

    # Read patterns in activity.py/admin.py filter and sort by these —
    # without indexes, the activity feed and per-user/action summaries
    # would do a full table scan on every request as this table grows.
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_user_activity_logs_timestamp ON user_activity_logs ("timestamp" DESC)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_user_activity_logs_created_at ON user_activity_logs (created_at DESC)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_user_activity_logs_user_id ON user_activity_logs (user_id)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_user_activity_logs_user_email ON user_activity_logs (user_email)'))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_activity_logs")
