"""create company_rating_requests table

Backs the new "Request Company Rating" action on the Credibility Index
pages — a lightweight way for a user to ask CreditDataWatch to add/rate a
company not yet in the Network Trust Intelligence registry
(GlobalCredibilityIndex). Distinct from CredibilityReview, which is a
heavier multi-stage approval chain tied to an existing Company Safety
Check request.

Created via a proper migration from the start (unlike several earlier
tables in this app that only existed as inline CREATE TABLE IF NOT EXISTS
statements bundled into larger startup transactions — which turned out to
silently roll back entirely if any other statement in the same
transaction failed later, even though each one appeared to succeed at
the time).

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-08-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'company_rating_requests'"
    )).fetchone()

    if not exists:
        op.create_table(
            'company_rating_requests',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('requested_by_user_id', sa.String(length=36),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('requested_by_email', sa.String(length=255), nullable=True),
            sa.Column('company_name', sa.String(length=255), nullable=False),
            sa.Column('status', sa.String(length=50), server_default='PENDING'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
        )
        op.create_index(op.f('ix_company_rating_requests_requested_by_user_id'),
                        'company_rating_requests', ['requested_by_user_id'])
        op.create_index(op.f('ix_company_rating_requests_company_name'),
                        'company_rating_requests', ['company_name'])
        op.create_index(op.f('ix_company_rating_requests_status'),
                        'company_rating_requests', ['status'])
        op.create_index(op.f('ix_company_rating_requests_created_at'),
                        'company_rating_requests', ['created_at'])


def downgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'company_rating_requests'"
    )).fetchone()
    if exists:
        op.drop_index(op.f('ix_company_rating_requests_created_at'), table_name='company_rating_requests')
        op.drop_index(op.f('ix_company_rating_requests_status'), table_name='company_rating_requests')
        op.drop_index(op.f('ix_company_rating_requests_company_name'), table_name='company_rating_requests')
        op.drop_index(op.f('ix_company_rating_requests_requested_by_user_id'), table_name='company_rating_requests')
        op.drop_table('company_rating_requests')
