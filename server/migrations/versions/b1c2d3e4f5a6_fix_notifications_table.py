"""fix notifications table: add user_email, title, action_url, workflow_item_id

The `notifications` table has no CREATE TABLE migration of its own — it was
originally created by Base.metadata.create_all() at app startup, straight
from the (incomplete) Notification ORM model. That model was missing
user_email, title, action_url, and workflow_item_id, even though
NotificationService.send() has always tried to INSERT into those columns.
Every notification send has therefore been silently failing (caught by a
bare except in NotificationService.send()) with an "column does not exist"
error, on any database whose notifications table predates this migration.

This migration adds the missing columns so the app's notification system
actually works. It also merges the two previously-independent migration
heads back into one.

Revision ID: b1c2d3e4f5a6
Revises: f5g6h7i8j9k0, a3b4c5d6e7f8
Create Date: 2026-08-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = ('f5g6h7i8j9k0', 'a3b4c5d6e7f8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'notifications'"
    ))}

    if 'user_email' not in existing_cols:
        op.add_column('notifications', sa.Column('user_email', sa.String(length=255), nullable=True))
        op.create_index(op.f('ix_notifications_user_email'), 'notifications', ['user_email'], unique=False)
    if 'title' not in existing_cols:
        op.add_column('notifications', sa.Column('title', sa.String(length=255), nullable=True))
    if 'action_url' not in existing_cols:
        op.add_column('notifications', sa.Column('action_url', sa.String(length=500), nullable=True))
    if 'workflow_item_id' not in existing_cols:
        op.add_column('notifications', sa.Column('workflow_item_id', sa.String(length=36), nullable=True))
        op.create_index(op.f('ix_notifications_workflow_item_id'), 'notifications', ['workflow_item_id'], unique=False)

    # Backfill user_email for any pre-existing rows from their user_id, so
    # old notifications remain queryable (get_for_user filters on user_email).
    if 'user_email' not in existing_cols:
        conn.execute(sa.text("""
            UPDATE notifications n
            SET user_email = u.email
            FROM users u
            WHERE n.user_id = u.id AND n.user_email IS NULL
        """))


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {row[0] for row in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'notifications'"
    ))}
    if 'workflow_item_id' in existing_cols:
        op.drop_index(op.f('ix_notifications_workflow_item_id'), table_name='notifications')
        op.drop_column('notifications', 'workflow_item_id')
    if 'action_url' in existing_cols:
        op.drop_column('notifications', 'action_url')
    if 'title' in existing_cols:
        op.drop_column('notifications', 'title')
    if 'user_email' in existing_cols:
        op.drop_index(op.f('ix_notifications_user_email'), table_name='notifications')
        op.drop_column('notifications', 'user_email')
