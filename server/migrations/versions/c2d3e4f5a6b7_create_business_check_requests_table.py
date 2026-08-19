"""create business_check_requests table properly

The business_check_requests table was never created by a real Alembic
migration — it only existed as TWO separate, mutually conflicting
`CREATE TABLE IF NOT EXISTS` attempts inline in main.py's startup code
(different column sets, different id/user_id types — VARCHAR(36) vs
native UUID). Both were bundled inside larger multi-statement DDL
transactions alongside other unrelated table creations.

That's a classic transactional-DDL trap: if ANY other statement later in
the same transaction failed, Postgres rolls back the ENTIRE transaction —
including the business_check_requests table that had already appeared to
succeed (its own "OK" log line had already printed by then, misleadingly
suggesting success). This is why business_check_requests could be
completely absent from a real database even though submitting a request
appeared to work and startup logs looked clean.

This migration creates the table for real, with the full column set the
running route code (app/routes/business_check.py) actually needs —
merging both of the previous conflicting inline attempts. Uses IF NOT
EXISTS defensively in case one of the inline attempts happened to
partially succeed on a given database.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'business_check_requests'"
    )).fetchone()

    if not exists:
        op.create_table(
            'business_check_requests',
            sa.Column('id', sa.String(length=36), primary_key=True,
                      server_default=sa.text('gen_random_uuid()::text')),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('user_email', sa.String(length=255), nullable=True),
            sa.Column('company_name', sa.String(length=255), nullable=False),
            sa.Column('gstin', sa.String(length=50), nullable=False),
            sa.Column('reason', sa.String(length=255), nullable=True),
            sa.Column('additional_info', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=50), server_default='PENDING_OPERATION'),
            sa.Column('report_text', sa.Text(), nullable=True),
            sa.Column('report_url', sa.String(length=500), nullable=True),
            sa.Column('report_notes', sa.Text(), nullable=True),
            sa.Column('verdict', sa.String(length=50), nullable=True),
            sa.Column('ops_reviewed_by', sa.String(length=255), nullable=True),
            sa.Column('reviewed_by', sa.String(length=255), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(), nullable=True),
            sa.Column('master_approved_by', sa.String(length=255), nullable=True),
            sa.Column('master_approved_at', sa.DateTime(), nullable=True),
            sa.Column('is_new_company', sa.Boolean(), server_default=sa.text('false')),
            sa.Column('saved_to_network', sa.Boolean(), server_default=sa.text('false')),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index(op.f('ix_business_check_requests_status'), 'business_check_requests', ['status'])
        op.create_index(op.f('ix_business_check_requests_user_id'), 'business_check_requests', ['user_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_business_check_requests_user_id'), table_name='business_check_requests')
    op.drop_index(op.f('ix_business_check_requests_status'), table_name='business_check_requests')
    op.drop_table('business_check_requests')