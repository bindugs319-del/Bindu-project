"""add master_notes column to business_check_requests

Missed in the initial table-creation migration (c2d3e4f5a6b7) — the
master-approve endpoint in routes/business_check.py writes to a
master_notes column that wasn't included in that migration's column list.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'business_check_requests'"
    ))}
    if 'master_notes' not in existing_cols:
        op.add_column('business_check_requests', sa.Column('master_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'business_check_requests'"
    ))}
    if 'master_notes' in existing_cols:
        op.drop_column('business_check_requests', 'master_notes')