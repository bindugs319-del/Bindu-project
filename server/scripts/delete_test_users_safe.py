"""Deletes test users using a single ANY() query per FK table (rather
than per-row queries) — the "safe" variant in that each table's delete
is one all-or-nothing statement instead of many small ones. See
_test_user_utils.py for the shared user-ID list, FK-table list, and
"list remaining users" step (previously duplicated across this file and
its two siblings, delete_test_users.py and delete_all_test_users.py)."""
import asyncio
from _test_user_utils import TEST_USER_IDS, FK_TABLES, AsyncSessionLocal, text, list_remaining_users


async def delete_from_table(table, column):
    db = AsyncSessionLocal()
    try:
        await db.execute(text(f"DELETE FROM {table} WHERE {column} = ANY(:user_ids)"), {"user_ids": TEST_USER_IDS})
        await db.commit()
        print(f"OK: Deleted from {table}.{column}")
    except Exception as e:
        print(f"SKIP: Could not delete from {table}.{column}: {str(e)[:100]}")
        await db.rollback()
    finally:
        await db.close()


async def delete_users():
    db = AsyncSessionLocal()
    try:
        await db.execute(text("DELETE FROM users WHERE id = ANY(:user_ids)"), {"user_ids": TEST_USER_IDS})
        await db.commit()
        print("OK: Deleted all test users!")
    except Exception as e:
        print(f"ERROR: Could not delete users: {str(e)[:100]}")
        await db.rollback()
    finally:
        await db.close()


async def main():
    for table, column in FK_TABLES:
        await delete_from_table(table, column)
    await delete_users()
    await list_remaining_users()


asyncio.run(main())
