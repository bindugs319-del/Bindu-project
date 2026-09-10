"""Deletes test users in one pass — all FK tables first (warning, not
failing, on any single table error), then the users themselves. The
simplest/original of the three variants. See _test_user_utils.py for the
shared user-ID list, FK-table list, and "list remaining users" step
(previously duplicated across this file and its two siblings,
delete_test_users.py and delete_test_users_safe.py)."""
import asyncio
from _test_user_utils import TEST_USER_IDS, FK_TABLES, AsyncSessionLocal, text, list_remaining_users


async def delete_all_test_users():
    db = AsyncSessionLocal()
    try:
        # Delete from all FK tables
        for table, column in FK_TABLES:
            try:
                await db.execute(text(f"DELETE FROM {table} WHERE {column} = ANY(:user_ids)"), {"user_ids": TEST_USER_IDS})
            except Exception as e:
                print(f"Warning: Could not delete from {table}.{column}: {str(e)[:80]}")

        # Delete the users
        await db.execute(text("DELETE FROM users WHERE id = ANY(:user_ids)"), {"user_ids": TEST_USER_IDS})
        await db.commit()
        print("Successfully deleted all test users!")
    except Exception as e:
        print(f"Error: {str(e)}")
        await db.rollback()
    finally:
        await db.close()


async def main():
    await delete_all_test_users()
    await list_remaining_users()


asyncio.run(main())
