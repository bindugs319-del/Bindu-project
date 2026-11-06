"""add admin view-access tables (client-authorized read-only access)

admin_access_codes:     one-time authorization codes a client generates
                        (only an HMAC of the code is stored).
admin_access_grants:    redeemed codes -> admin_id + client + expiry,
                        checked on every delegated request.
delegated_access_audit: generation / redemption / views / blocked writes /
                        revocation / expiry, with admin, client, time, IP.

Uses CREATE TABLE IF NOT EXISTS because the app also creates these tables
on first use (app/services/delegated_access_service.ensure_tables) for
deployments that don't run Alembic.

Revision ID: y6n7o8p9q0r1
Revises: x5m6n7o8p9q0
Create Date: 2026-11-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'y6n7o8p9q0r1'
down_revision: Union[str, None] = 'x5m6n7o8p9q0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS admin_access_codes (
            id VARCHAR(36) PRIMARY KEY,
            client_user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            company_id VARCHAR(36),
            code_hash VARCHAR(64) NOT NULL UNIQUE,
            duration_hours INTEGER NOT NULL DEFAULT 24,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            redeem_by TIMESTAMP NOT NULL,
            redeemed_at TIMESTAMP,
            redeemed_by_admin_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
            cancelled_at TIMESTAMP
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_access_codes_client_user_id ON admin_access_codes (client_user_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_access_codes_company_id ON admin_access_codes (company_id)"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS admin_access_grants (
            id VARCHAR(36) PRIMARY KEY,
            code_id VARCHAR(36) REFERENCES admin_access_codes(id) ON DELETE SET NULL,
            admin_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            client_user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            company_id VARCHAR(36),
            granted_at TIMESTAMP NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP NOT NULL,
            revoked_at TIMESTAMP,
            revoked_by_id VARCHAR(36),
            revoked_by_role VARCHAR(30),
            expiry_logged BOOLEAN NOT NULL DEFAULT false
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_access_grants_admin_id ON admin_access_grants (admin_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_access_grants_client_user_id ON admin_access_grants (client_user_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_access_grants_company_id ON admin_access_grants (company_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_access_grants_expires_at ON admin_access_grants (expires_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_admin_access_grant_admin_active ON admin_access_grants (admin_id, revoked_at, expires_at)"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS delegated_access_audit (
            id VARCHAR(36) PRIMARY KEY,
            event VARCHAR(30) NOT NULL,
            grant_id VARCHAR(36),
            code_id VARCHAR(36),
            admin_id VARCHAR(36),
            admin_role VARCHAR(30),
            client_user_id VARCHAR(36),
            method VARCHAR(10),
            path VARCHAR(500),
            resource VARCHAR(100),
            ip VARCHAR(64),
            detail TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_delegated_access_audit_event ON delegated_access_audit (event)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_delegated_access_audit_grant_id ON delegated_access_audit (grant_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_delegated_access_audit_admin_id ON delegated_access_audit (admin_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_delegated_access_audit_client_user_id ON delegated_access_audit (client_user_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_delegated_access_audit_created_at ON delegated_access_audit (created_at)"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS delegated_access_audit")
    op.execute("DROP TABLE IF EXISTS admin_access_grants")
    op.execute("DROP TABLE IF EXISTS admin_access_codes")
