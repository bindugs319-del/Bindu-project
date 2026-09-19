"""create system_settings table

The admin settings pages (homepage alert message, Financial/Legal role
toggles, trust-ticker stats, business-impact stats) read and write a
`system_settings` key/value table. Earlier revisions never created it in
upgrade() (6f2cd4edd879 only mentions it inside downgrade()), and the
best-effort CREATE TABLE in app/main.py's startup block can be silently
skipped on Postgres if an earlier statement in the same startup
transaction fails. On a brand-new database the table therefore ended up
missing, causing `UndefinedTableError: relation "system_settings" does
not exist` and 503s on those pages.

This migration creates the table (and the default rows) idempotently:
every statement uses IF NOT EXISTS / ON CONFLICT DO NOTHING, so it is
safe to run on a database where the table already exists.

Revision ID: s0h1i2j3k4l5
Revises: r9g0h1i2j3k4
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 's0h1i2j3k4l5'
down_revision: Union[str, None] = 'r9g0h1i2j3k4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_ALERT_MESSAGE = (
    "Important Fraud Alert: We have received reports of unauthorized "
    "individuals impersonating CreditDataWatch. For your security, please "
    "strictly verify the Account Number and Account Holder's Name before "
    "processing any payments."
)

DEFAULT_TRUST_TICKER = (
    '[{"label": "Average Trust Score", "value": "98%"}, '
    '{"label": "Verified Companies", "value": "12,450"}, '
    '{"label": "Secure Transactions", "value": "4,56,780+"}]'
)

DEFAULT_BUSINESS_STATS = (
    '[{"label": "Defaulters by a Single Customer", "value": "668+"}, '
    '{"label": "MSMEs Connected", "value": "39+ Lakhs"}, '
    '{"label": "Settlements", "value": "59%"}, '
    '{"label": "Reported Defaulter Amount", "value": "4578+ Crores"}]'
)


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS system_settings (
            id VARCHAR(36) PRIMARY KEY,
            key VARCHAR(100) UNIQUE NOT NULL,
            value TEXT,
            description TEXT,
            updated_by VARCHAR(255),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """))

    # Default rows (same values app/main.py seeds on startup).
    conn.execute(sa.text("""
        INSERT INTO system_settings (id, key, value, description)
        VALUES
            (gen_random_uuid()::text, 'financial_role_enabled', 'false',
             'When enabled, Financial team members see their own dashboard and handle payment tasks'),
            (gen_random_uuid()::text, 'legal_role_enabled', 'false',
             'When enabled, Legal team members see their own dashboard and handle legal tasks')
        ON CONFLICT (key) DO NOTHING
    """))

    conn.execute(
        sa.text("""
            INSERT INTO system_settings (id, key, value, description)
            VALUES (gen_random_uuid()::text, 'alert_message', :msg,
                    'Homepage alert banner text, shown once per visitor session')
            ON CONFLICT (key) DO NOTHING
        """),
        {"msg": DEFAULT_ALERT_MESSAGE},
    )

    conn.execute(
        sa.text("""
            INSERT INTO system_settings (id, key, value, description)
            VALUES
                (gen_random_uuid()::text, 'trust_ticker_stats', :val,
                 'Homepage trust ticker stats (3 items, JSON)'),
                (gen_random_uuid()::text, 'business_impact_stats', :val2,
                 'Homepage business impact stats (4 items, JSON)')
            ON CONFLICT (key) DO NOTHING
        """),
        {"val": DEFAULT_TRUST_TICKER, "val2": DEFAULT_BUSINESS_STATS},
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS system_settings")
