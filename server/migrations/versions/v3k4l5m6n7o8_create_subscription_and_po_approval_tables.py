"""create subscription_requests and po_approval_requests tables

Both tables have a best-effort `CREATE TABLE IF NOT EXISTS` in
app/main.py's startup block, but — same root cause as the earlier
system_settings and user_activity_logs fixes — that block runs many
statements in one transaction with no per-statement recovery, so a
single earlier failure silently skips every statement after it on a
fresh Postgres database. Neither table was ever created by a real
migration either. Result: creating a subscription request (the
Membership Hub "Submit Payment Proof" flow) or a PO edit-approval
request both fail with `UndefinedTableError`.

Column definitions below are copied exactly from the CREATE TABLE
statements already written in app/main.py (search "Subscription
requests" / "PO approval requests" there), so this simply makes real
what the app already intended — not a schema change.

Revision ID: v3k4l5m6n7o8
Revises: u2j3k4l5m6n7
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'v3k4l5m6n7o8'
down_revision: Union[str, None] = 'u2j3k4l5m6n7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS subscription_requests (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(36),
            user_email VARCHAR(255),
            company_name VARCHAR(255),
            plan_name VARCHAR(100),
            amount DECIMAL(10,2) DEFAULT 0,
            payment_status VARCHAR(50) DEFAULT 'PENDING',
            workflow_status VARCHAR(50) DEFAULT 'PENDING',
            workflow_item_id VARCHAR(36),
            approved_at TIMESTAMP,
            rejected_at TIMESTAMP,
            rejection_reason TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS po_approval_requests (
            id VARCHAR(36) PRIMARY KEY,
            po_id VARCHAR(36) NOT NULL,
            po_number VARCHAR(100),
            requested_by_email VARCHAR(255),
            edit_data TEXT,
            evidence_url VARCHAR(500),
            evidence_filename VARCHAR(255),
            reason TEXT,
            workflow_status VARCHAR(50) DEFAULT 'PENDING_FINANCIAL',
            final_status VARCHAR(50) DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))

    # Read/write patterns in workflow_service.py join and filter on
    # these — without indexes it's a full table scan on every workflow
    # action as these tables grow.
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_subscription_requests_workflow_item_id ON subscription_requests (workflow_item_id)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_subscription_requests_user_email ON subscription_requests (user_email)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_po_approval_requests_po_id ON po_approval_requests (po_id)'))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS subscription_requests")
    op.execute("DROP TABLE IF EXISTS po_approval_requests")
