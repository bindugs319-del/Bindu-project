"""Deletes test users one-by-one, with per-row error handling so one
failed FK delete doesn't abort the whole run for that user. See
_test_user_utils.py for the shared user-ID list, FK-table list, and
"list remaining users" step (previously duplicated across this file and
its two siblings, delete_test_users_safe.py and delete_all_test_users.py)."""
import asyncio
from _test_user_utils import TEST_USER_IDS, FK_TABLES, AsyncSessionLocal, text, list_remaining_users


async def delete_single_user(user_id):
    """Delete a single user and all their related records"""
    db = None
    try:
        db = AsyncSessionLocal()
        # Delete related records from all FK tables
        for table, column in FK_TABLES:
            try:
                await db.execute(text(f"DELETE FROM {table} WHERE {column} = :user_id"), {"user_id": user_id})
            except Exception as e:
                # Rollback just this failed statement's transaction
                await db.rollback()

        # Now delete the user
        await db.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
        await db.commit()
        print(f"[OK] Deleted user {user_id}")
        return True
    except Exception as e:
        print(f"[ERROR] Deleting {user_id}: {str(e)[:100]}")
        try:
            await db.rollback()
        except:
            pass
        return False
    finally:
        if db:
            await db.close()


async def delete_test_users():
    for user_id in TEST_USER_IDS:
        await delete_single_user(user_id)
    await list_remaining_users()


asyncio.run(delete_test_users())
