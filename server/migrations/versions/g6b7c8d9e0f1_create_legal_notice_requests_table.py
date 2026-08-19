"""create legal_notice_requests table

Referenced extensively across routes/core.py (creation on legal support
submission), routes/workflow.py (Operations approve/reject, Master Admin
final approve/reject, and dashboard reads for both LEGAL and MASTER_ADMIN
roles), and services/workflow_service.py (kept in sync alongside the
corresponding workflow_items row) — but the table itself was never
actually created anywhere in this codebase, not even via the fragile
inline-SQL-in-main.py pattern other tables here used. Every legal notice
submitted crashed the whole request (before the earlier
legal_support_requested_by fix), and even after that fix, every
subsequent step in this workflow (Operations approve, Master Admin
approve/reject, and both dashboards' reads) was still broken because this
table simply didn't exist.

Revision ID: g6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-08-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g6b7c8d9e0f1'
down_revision: Union[str, None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'legal_notice_requests'"
    )).fetchone()

    if not exists:
        op.create_table(
            'legal_notice_requests',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('po_id', sa.String(length=36),
                      sa.ForeignKey('purchase_orders.id', ondelete='CASCADE'), nullable=False),
            sa.Column('po_number', sa.String(length=100), nullable=True),
            sa.Column('vendor', sa.String(length=255), nullable=True),
            sa.Column('vendor_email', sa.String(length=255), nullable=True),
            sa.Column('amount', sa.Float(), nullable=True),
            sa.Column('requested_by_email', sa.String(length=255), nullable=True),
            sa.Column('handler_role', sa.String(length=50), nullable=True),
            sa.Column('status', sa.String(length=50), server_default='PENDING'),
            sa.Column('ops_notes', sa.Text(), nullable=True),
            sa.Column('ops_processed_by', sa.String(length=255), nullable=True),
            sa.Column('ops_processed_at', sa.DateTime(), nullable=True),
            sa.Column('master_notes', sa.Text(), nullable=True),
            sa.Column('master_approved_by', sa.String(length=255), nullable=True),
            sa.Column('master_approved_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index(op.f('ix_legal_notice_requests_po_id'), 'legal_notice_requests', ['po_id'])
        op.create_index(op.f('ix_legal_notice_requests_status'), 'legal_notice_requests', ['status'])
        op.create_index(op.f('ix_legal_notice_requests_created_at'), 'legal_notice_requests', ['created_at'])


def downgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'legal_notice_requests'"
    )).fetchone()
    if exists:
        op.drop_index(op.f('ix_legal_notice_requests_created_at'), table_name='legal_notice_requests')
        op.drop_index(op.f('ix_legal_notice_requests_status'), table_name='legal_notice_requests')
        op.drop_index(op.f('ix_legal_notice_requests_po_id'), table_name='legal_notice_requests')
        op.drop_table('legal_notice_requests')
