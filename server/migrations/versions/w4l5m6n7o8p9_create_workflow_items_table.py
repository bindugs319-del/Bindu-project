"""create workflow_items table

Same root cause as the previous few fixes: app/main.py has a
best-effort `CREATE TABLE IF NOT EXISTS workflow_items` in its startup
block, but that block runs many statements in one transaction with no
per-statement recovery, so an earlier failure silently skips every
statement after it on a fresh Postgres database — and no real
migration ever created this table either.

workflow_items is central: it's the shared approval-queue table behind
subscription requests, PO edit approvals, and other multi-step
approval flows (see app/services/workflow_service.py and
app/routes/workflow.py) — every one of those was failing at the
"create the workflow item" step with `UndefinedTableError`.

Column definitions copied exactly from the CREATE TABLE statement
already written in app/main.py (search "Workflow items" there) — this
makes real what the app already intended, not a schema change.

Revision ID: w4l5m6n7o8p9
Revises: v3k4l5m6n7o8
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'w4l5m6n7o8p9'
down_revision: Union[str, None] = 'v3k4l5m6n7o8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS workflow_items (
            id VARCHAR(36) PRIMARY KEY,
            type VARCHAR(50) NOT NULL,
            status VARCHAR(50) DEFAULT 'PENDING',
            title VARCHAR(255),
            description TEXT,
            entity_id VARCHAR(36),
            entity_type VARCHAR(50),
            submitted_by_email VARCHAR(255),
            submitted_by_name VARCHAR(255),
            assigned_to_role VARCHAR(50),
            current_handler_role VARCHAR(50),
            reviewed_by_email VARCHAR(255),
            review_notes TEXT,
            reviewed_at TIMESTAMP,
            approved_by_email VARCHAR(255),
            approval_notes TEXT,
            approved_at TIMESTAMP,
            rejected_by_email VARCHAR(255),
            rejection_notes TEXT,
            rejected_at TIMESTAMP,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """))

    # Every read pattern in workflow_service.py / workflow.py filters or
    # joins on these — without indexes, the approval queues (Master
    # Admin's pending list, per-role queues) would do a full table scan
    # on every load as this table grows.
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_workflow_items_status ON workflow_items (status)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_workflow_items_entity_id ON workflow_items (entity_id)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_workflow_items_current_handler_role ON workflow_items (current_handler_role)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_workflow_items_type ON workflow_items (type)'))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS workflow_items")
