"""add head office / branch organisation tables

company_org_settings:  per company — is it a head office, and how many
                       branches it may have (set by platform Super Admins).
company_branch_links:  a branch company's link to its head office
                       (PENDING until the head office approves).

New tables only; `companies` is not altered. Uses IF NOT EXISTS because
the app also creates these on first use
(app/services/organization_service.ensure_tables).

Revision ID: z7o8p9q0r1s2
Revises: y6n7o8p9q0r1
Create Date: 2026-11-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'z7o8p9q0r1s2'
down_revision: Union[str, None] = 'y6n7o8p9q0r1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS company_org_settings (
            company_id VARCHAR(36) PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
            is_headquarters BOOLEAN NOT NULL DEFAULT false,
            branch_limit INTEGER NOT NULL DEFAULT 0,
            limit_set_by VARCHAR(36),
            limit_set_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_company_org_settings_is_headquarters ON company_org_settings (is_headquarters)"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS company_branch_links (
            id VARCHAR(36) PRIMARY KEY,
            hq_company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            branch_company_id VARCHAR(36) NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            branch_name VARCHAR(120) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
            requested_by VARCHAR(36),
            requested_at TIMESTAMP NOT NULL DEFAULT NOW(),
            decided_by VARCHAR(36),
            decided_at TIMESTAMP
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_company_branch_links_hq_company_id ON company_branch_links (hq_company_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_company_branch_links_branch_company_id ON company_branch_links (branch_company_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_company_branch_links_status ON company_branch_links (status)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_branch_link_hq_status ON company_branch_links (hq_company_id, status)"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS company_branch_links")
    op.execute("DROP TABLE IF EXISTS company_org_settings")
