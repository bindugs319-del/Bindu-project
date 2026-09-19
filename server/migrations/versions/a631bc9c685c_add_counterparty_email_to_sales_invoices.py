"""add counterparty_email to sales_invoices

Revision ID: a631bc9c685c
Revises: r9g0h1i2j3k4
Create Date: 2026-09-19 18:59:48.526818

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a631bc9c685c'
down_revision: Union[str, None] = 'r9g0h1i2j3k4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sales_invoices', sa.Column('counterparty_email', sa.String(length=255), nullable=True))

def downgrade() -> None:
    op.drop_column('sales_invoices', 'counterparty_email')