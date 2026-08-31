"""fix notifications user_id fk to cascade on delete

Deleting a company cascades (via ORM relationships) into deleting its
users, but notifications.user_id had a plain FK with no ON DELETE
behavior — so Postgres blocked the delete with a
ForeignKeyViolationError ("update or delete on table users violates
foreign key constraint notifications_user_id_fkey") the moment a
to-be-deleted user had any notifications, which is effectively always.

This mirrors related_po_id on the same table and every other
user_id FK added since (see USER_ID_FK/ONDELETE_CASCADE usage in
app/models/__init__.py): ON DELETE CASCADE, so a user's notifications
are cleaned up automatically along with the user.

Revision ID: k2f3a4b5c6d7
Revises: j1e2f3a4b5c6
Create Date: 2026-08-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k2f3a4b5c6d7'
down_revision: Union[str, None] = 'j1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # Find the actual constraint name rather than assuming the default
    # Postgres-generated name, in case it was ever created differently.
    fk_name = conn.execute(sa.text("""
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = 'notifications'
          AND tc.constraint_type = 'FOREIGN KEY'
          AND kcu.column_name = 'user_id'
    """)).scalar()

    if fk_name:
        op.drop_constraint(fk_name, 'notifications', type_='foreignkey')

    op.create_foreign_key(
        'notifications_user_id_fkey',
        'notifications', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('notifications_user_id_fkey', 'notifications', type_='foreignkey')
    op.create_foreign_key(
        'notifications_user_id_fkey',
        'notifications', 'users',
        ['user_id'], ['id'],
    )
