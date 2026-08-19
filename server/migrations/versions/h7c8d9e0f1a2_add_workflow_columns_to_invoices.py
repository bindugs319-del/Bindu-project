"""add approval workflow columns to invoices table

The Invoice model (app/models/__init__.py) has 8 "approval workflow
(User -> Operations -> Master Admin)" columns — workflow_status,
company_id, operations_reviewed_by, operations_reviewed_at,
operations_notes, master_approved_by, master_approved_at, master_notes —
that were never actually added to the `invoices` table by any migration.
A near-identical set of columns *was* added to the sales_invoices table
(migration b7c8d9e0f1a2), which is presumably where this got confused —
sales_invoices and invoices are two separate tables/models in this app.

Since select(Invoice) is a full ORM query touching every mapped column,
any read of the invoices table (GET /invoices, GET /invoices/reminders/due,
etc.) failed with "column ... does not exist" the moment these columns
were added to the model without a matching migration.

Revision ID: h7c8d9e0f1a2
Revises: g6b7c8d9e0f1
Create Date: 2026-08-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h7c8d9e0f1a2'
down_revision: Union[str, None] = 'g6b7c8d9e0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'invoices'"
    ))}

    if 'workflow_status' not in existing_cols:
        op.add_column('invoices', sa.Column('workflow_status', sa.String(length=40), nullable=True, server_default='Draft'))
    if 'company_id' not in existing_cols:
        op.add_column('invoices', sa.Column('company_id', sa.String(length=36),
                      sa.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True))
        op.create_index(op.f('ix_invoices_company_id'), 'invoices', ['company_id'])
    if 'operations_reviewed_by' not in existing_cols:
        op.add_column('invoices', sa.Column('operations_reviewed_by', sa.String(length=36), nullable=True))
    if 'operations_reviewed_at' not in existing_cols:
        op.add_column('invoices', sa.Column('operations_reviewed_at', sa.DateTime(), nullable=True))
    if 'operations_notes' not in existing_cols:
        op.add_column('invoices', sa.Column('operations_notes', sa.Text(), nullable=True))
    if 'master_approved_by' not in existing_cols:
        op.add_column('invoices', sa.Column('master_approved_by', sa.String(length=36), nullable=True))
    if 'master_approved_at' not in existing_cols:
        op.add_column('invoices', sa.Column('master_approved_at', sa.DateTime(), nullable=True))
    if 'master_notes' not in existing_cols:
        op.add_column('invoices', sa.Column('master_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'invoices'"
    ))}
    for col in ['master_notes', 'master_approved_at', 'master_approved_by', 'operations_notes',
                'operations_reviewed_at', 'operations_reviewed_by']:
        if col in existing_cols:
            op.drop_column('invoices', col)
    if 'company_id' in existing_cols:
        op.drop_index(op.f('ix_invoices_company_id'), table_name='invoices')
        op.drop_column('invoices', 'company_id')
    if 'workflow_status' in existing_cols:
        op.drop_column('invoices', 'workflow_status')