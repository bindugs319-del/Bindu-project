"""Checks which FK tables still have rows referencing the test user IDs
— a read-only diagnostic companion to the delete_*_test_users.py scripts,
useful for confirming a cleanup run actually worked (or scoping out what
it'll touch beforehand). See _test_user_utils.py for the shared user-ID
list and FK-table list (previously duplicated here too)."""
import asyncio
from _test_user_utils import TEST_USER_IDS, FK_TABLES, AsyncSessionLocal, text


async def check_references():
    db = AsyncSessionLocal()
    for table, column in FK_TABLES:
        for user_id in TEST_USER_IDS:
            try:
                result = await db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {column} = :user_id"), {"user_id": user_id})
                count = result.scalar()
                if count > 0:
                    print(f"[FOUND] Table {table}, column {column} has {count} references to user {user_id}")
            except Exception as e:
                pass
    await db.close()


asyncio.run(check_references())
