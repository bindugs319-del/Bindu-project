"""add operations proposal columns to company_rating_requests

Changes the "Request Company Rating" flow from a direct
user-request -> Master-Admin-fulfills flow into a proper
Operations-proposes -> Master-Admin-approves chain, matching the pattern
already used for PO approvals, subscriptions, and legal notices elsewhere
in this app.

Revision ID: i8d9e0f1a2b3
Revises: h7c8d9e0f1a2
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i8d9e0f1a2b3'
down_revision: Union[str, None] = 'h7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'company_rating_requests'"
    ))}

    if 'proposed_partner_trust_score' not in existing_cols:
        op.add_column('company_rating_requests', sa.Column('proposed_partner_trust_score', sa.Float(), nullable=True))
    if 'proposed_ai_credit_risk_verdict' not in existing_cols:
        op.add_column('company_rating_requests', sa.Column('proposed_ai_credit_risk_verdict', sa.String(length=50), nullable=True))
    if 'proposed_credibility_status' not in existing_cols:
        op.add_column('company_rating_requests', sa.Column('proposed_credibility_status', sa.String(length=50), nullable=True))
    if 'operations_reviewed_by' not in existing_cols:
        op.add_column('company_rating_requests', sa.Column('operations_reviewed_by', sa.String(length=36), nullable=True))
    if 'operations_reviewed_at' not in existing_cols:
        op.add_column('company_rating_requests', sa.Column('operations_reviewed_at', sa.DateTime(), nullable=True))
    if 'operations_notes' not in existing_cols:
        op.add_column('company_rating_requests', sa.Column('operations_notes', sa.Text(), nullable=True))
    if 'master_approved_by' not in existing_cols:
        op.add_column('company_rating_requests', sa.Column('master_approved_by', sa.String(length=36), nullable=True))
    if 'master_notes' not in existing_cols:
        op.add_column('company_rating_requests', sa.Column('master_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'company_rating_requests'"
    ))}
    for col in ['master_notes', 'master_approved_by', 'operations_notes', 'operations_reviewed_at',
                'operations_reviewed_by', 'proposed_credibility_status', 'proposed_ai_credit_risk_verdict',
                'proposed_partner_trust_score']:
        if col in existing_cols:
            op.drop_column('company_rating_requests', col)
