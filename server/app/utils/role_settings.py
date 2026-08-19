from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def get_role_setting(db: AsyncSession, role_name: str) -> bool:
    """Check if a role is enabled in role_settings table"""
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
            result = await db.execute(
                text("SELECT is_enabled FROM role_settings WHERE role_name = :role_name"),
                {"role_name": role_name}
            )
            row = result.fetchone()
            if row:
                return row[0]
            # Fallback to system_settings if not found
            key = f"{role_name.lower()}_role_enabled"
            result_fallback = await db.execute(
                text("SELECT value FROM system_settings WHERE key = :key"),
                {"key": key}
            )
            row_fallback = result_fallback.fetchone()
            return row_fallback[0] == 'true' if row_fallback else True  # Default to True
    except Exception as e:
        print(f"[SETTINGS] Error checking {role_name}: {e}")
        return True  # Default to True if error; savepoint above is already rolled back


async def is_financial_enabled(db: AsyncSession) -> bool:
    return await get_role_setting(db, 'FINANCIAL')


async def is_legal_enabled(db: AsyncSession) -> bool:
    return await get_role_setting(db, 'LEGAL')
