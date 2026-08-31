"""set null on delete for advisory user_id fks

Same root cause as k2f3a4b5c6d7 (notifications), but for the other
"who did this" user references that had no ON DELETE behavior at all:
users.created_by, subscriptions.verified_by/processed_by/approved_by,
purchase_orders.approved_by, business_requests.analyzed_by, and
support_requests.resolved_by. Any of these blocks a user delete (and
therefore a company delete, which cascades into deleting its users)
the moment that user has ever verified/processed/approved/analyzed/
resolved something — which is routine for MASTER_ADMIN/FINANCIAL/
OPERATION/LEGAL staff.

Unlike notifications.user_id (CASCADE — a notification has no meaning
without its owner), these columns just record who performed an action
on a record that should keep existing on its own — a subscription,
PO, business check, or support ticket shouldn't disappear just
because the staff member who approved/resolved it was later removed.
So these get SET NULL instead: the record survives, the "who" is
simply cleared.

Revision ID: l3a4b5c6d7e8
Revises: k2f3a4b5c6d7
Create Date: 2026-08-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l3a4b5c6d7e8'
down_revision: Union[str, None] = 'k2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column) pairs to fix, each referencing users.id
TARGETS = [
    ("users", "created_by"),
    ("subscriptions", "verified_by"),
    ("subscriptions", "processed_by"),
    ("subscriptions", "approved_by"),
    ("purchase_orders", "approved_by"),
    ("business_requests", "analyzed_by"),
    ("support_requests", "resolved_by"),
]


def _find_fk_name(conn, table, column):
    return conn.execute(sa.text("""
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = :table
          AND tc.constraint_type = 'FOREIGN KEY'
          AND kcu.column_name = :column
    """), {"table": table, "column": column}).scalar()


def upgrade() -> None:
    conn = op.get_bind()
    for table, column in TARGETS:
        fk_name = _find_fk_name(conn, table, column)
        if not fk_name:
            continue
        op.drop_constraint(fk_name, table, type_='foreignkey')
        op.create_foreign_key(fk_name, table, 'users', [column], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    conn = op.get_bind()
    for table, column in TARGETS:
        fk_name = _find_fk_name(conn, table, column)
        if not fk_name:
            continue
        op.drop_constraint(fk_name, table, type_='foreignkey')
        op.create_foreign_key(fk_name, table, 'users', [column], ['id'])
