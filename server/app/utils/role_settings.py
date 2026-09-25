from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def get_role_setting(db: AsyncSession, role_name: str) -> bool:
    """Check if a role is enabled.

    system_settings is checked FIRST, not role_settings — system_settings
    is what the Admin dashboard's role toggle (see
    app/routes/admin.py's /settings/roles/{role_key}/toggle) actually
    writes to and what its UI reads back to show as on/off, so it's the
    real source of truth an admin sees. role_settings is used only as a
    fallback for a role that's never been touched. This previously
    checked role_settings first, which — combined with that table
    having been created with default is_enabled=true rows for FINANCIAL
    and LEGAL — silently ignored whatever an admin had actually set in
    system_settings, routing new requests to the wrong (and, if that
    role is disabled, effectively unreachable) approval queue.
    """
    # Run the lookup inside a SAVEPOINT (nested transaction). If the query
    # fails, only the savepoint is rolled back — the outer transaction (which
    # may already hold other uncommitted work, e.g. a payment status update
    # done earlier in the same request) is left intact. Without this, a
    # failure here would poison the *whole* transaction, and the very next
    # statement on this session (e.g. INSERT INTO subscription_requests)
    # would fail with "current transaction is aborted, commands ignored
    # until end of transaction block" — masking the real error.
    try:
        async with db.begin_nested():
            key = f"{role_name.lower()}_role_enabled"
            result = await db.execute(
                text("SELECT value FROM system_settings WHERE key = :key"),
                {"key": key}
            )
            row = result.fetchone()
            if row is not None:
                return str(row[0]).lower() == 'true'

            # Fallback to role_settings only if system_settings has no
            # row at all for this role yet.
            result_fallback = await db.execute(
                text("SELECT is_enabled FROM role_settings WHERE role_name = :role_name"),
                {"role_name": role_name}
            )
            row_fallback = result_fallback.fetchone()
            if row_fallback is not None:
                return row_fallback[0]

            return False  # Neither table has a row — default to disabled, not enabled.
    except Exception as e:
        print(f"[SETTINGS] Error checking {role_name}: {e}")
        return False  # Default to disabled on error, matching the no-row case above.


async def is_financial_enabled(db: AsyncSession) -> bool:
    return await get_role_setting(db, 'FINANCIAL')


async def is_legal_enabled(db: AsyncSession) -> bool:
    return await get_role_setting(db, 'LEGAL')
