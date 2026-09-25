"""create role_settings and business_check_requests tables

Last two tables with the same root cause as the previous several
fixes: never created by a real migration, only attempted via
best-effort CREATE TABLE IF NOT EXISTS statements in app/main.py's
startup block, which silently no-op after any earlier failure in that
same large multi-statement transaction.

role_settings: schema copied directly from app/main.py (search
"role_settings" there) — used to enable/disable the Financial and
Legal team roles (Admin dashboard's Role Management toggles).

business_check_requests: app/main.py actually contains TWO different,
mutually incompatible CREATE TABLE statements for this table (one
using VARCHAR ids, one using UUID; different column names for the
same data — e.g. report_text vs report_notes, reviewed_by vs
ops_reviewed_by). Neither matches what app/routes/business_check.py
actually reads and writes. The columns below are the real union of
every column referenced across that file's INSERT/UPDATE/SELECT
statements (including master_notes, which is used there but wasn't in
either of main.py's two conflicting definitions), with VARCHAR(36) ids
to match what the route code actually passes in (current_user.id and
a str(uuid.uuid4()), both plain strings, not the Postgres UUID type).

Revision ID: x5m6n7o8p9q0
Revises: w4l5m6n7o8p9
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'x5m6n7o8p9q0'
down_revision: Union[str, None] = 'w4l5m6n7o8p9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS role_settings (
            id SERIAL PRIMARY KEY,
            role_name VARCHAR(50) UNIQUE NOT NULL,
            is_enabled BOOLEAN DEFAULT true,
            updated_by VARCHAR(255),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO role_settings (role_name, is_enabled)
        VALUES ('FINANCIAL', true), ('LEGAL', true)
        ON CONFLICT (role_name) DO NOTHING
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS business_check_requests (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL,
            user_email VARCHAR(255),
            company_name VARCHAR(255) NOT NULL,
            gstin VARCHAR(50) NOT NULL,
            reason VARCHAR(255),
            additional_info TEXT,
            status VARCHAR(50) DEFAULT 'PENDING_OPERATION',
            report_text TEXT,
            report_notes TEXT,
            report_url VARCHAR(500),
            verdict VARCHAR(50),
            reviewed_by VARCHAR(255),
            reviewed_at TIMESTAMP,
            ops_reviewed_by VARCHAR(255),
            master_approved_by VARCHAR(255),
            master_approved_at TIMESTAMP,
            master_notes TEXT,
            is_new_company BOOLEAN DEFAULT false,
            saved_to_network BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_business_check_requests_user_id ON business_check_requests (user_id)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_business_check_requests_status ON business_check_requests (status)'))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS role_settings")
    op.execute("DROP TABLE IF EXISTS business_check_requests")
