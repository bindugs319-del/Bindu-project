import uuid 
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.services.email_service import EmailService

# Keeps a strong reference to background email tasks so they aren't
# garbage-collected mid-run — see app/main.py's spawn_background_task
# for the full explanation of why this is needed.
_background_tasks: set = set()


class NotificationService:

    @staticmethod
    async def send(
        db: AsyncSession,
        to_email: str,
        title: str,
        message: str,
        ntype: str = "INFO",
        action_url: str = None,
        workflow_id: str = None,
        related_po_id: str = None,
        send_email: bool = True
    ):
        """Send notification IMMEDIATELY - no queue, no delay"""
        try:
            # 1. Save in-app notification to DB RIGHT NOW
            user_result = await db.execute(
                text("SELECT id FROM users WHERE email = :e"), {"e": to_email}
            )
            user_row = user_result.fetchone()
            
            if not user_row:
                print(f"[NOTIFY] Warning: No user found for email {to_email}, skipping notification")
                return
            
            notif_id = str(uuid.uuid4())
            await db.execute(text("""
                INSERT INTO notifications 
                (id, user_id, user_email, title, message, type, 
                 action_url, workflow_item_id, related_po_id, is_read, created_at) 
                VALUES (:id, :uid, :email, :title, :msg, :type, 
                 :url, :wid, :po_id, false, NOW())
            """), {
                "id": notif_id,
                "uid": str(user_row[0]),
                "email": to_email,
                "title": title,
                "msg": message,
                "type": ntype,
                "url": action_url or "http://localhost:3001/dashboard",
                "wid": workflow_id,
                "po_id": related_po_id
            })
            await db.commit()
            print(f"[NOTIFY] Saved in-app notification: {to_email} — {title}")
            
            # 2. Send email IMMEDIATELY in background (don't await - non-blocking)
            if send_email:
                task = asyncio.create_task(
                    NotificationService._send_email_background(to_email, title, message, action_url)
                )
                _background_tasks.add(task)  # keep a strong reference alive
                # Add a callback to log any exceptions from the task, and to
                # release our reference once the task is actually done.
                def log_task_result(task):
                    try:
                        task.result()
                    except Exception as e:
                        print(f"[NOTIFY] Background email task failed: {e}")
                        import traceback
                        traceback.print_exc()
                    finally:
                        _background_tasks.discard(task)
                task.add_done_callback(log_task_result)
                print(f"[NOTIFY] Created background email task for {to_email}")
                
        except Exception as e:
            print(f"[NOTIFY] Error: {e}")
            import traceback
            traceback.print_exc()
            # Without a rollback here, a failed statement above (e.g. a bad
            # column) leaves this session's transaction aborted, silently
            # breaking any later commit on the same session/request (like
            # the route's own db.commit() for its main action). See the
            # same note in send_to_role below.
            try:
                await db.rollback()
            except Exception as rollback_err:
                print(f"[NOTIFY] Rollback after error also failed: {rollback_err}")

    @staticmethod
    async def _send_email_background(to_email: str, title: str, message: str, action_url: str = None):
        """Send email in background - won't block the main request"""
        try:
            from app.services.email_service import send_email
            body = f"""{title}

{message}

{f'View in app: {action_url}' if action_url else 'Login: http://localhost:3001/auth/login'}

---
CreditDataWatch Notification
"""
            await send_email(
                to_email=to_email,
                subject=f"[CreditDataWatch] {title}",
                body=body
            )
            print(f"[NOTIFY] Email sent to {to_email}")
        except Exception as e:
            print(f"[NOTIFY] Email failed (notification already saved): {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    async def send_to_role(
        db: AsyncSession,
        role: str,
        title: str,
        message: str,
        ntype: str = "INFO",
        action_url: str = None,
        workflow_id: str = None,
        related_po_id: str = None
    ):
        try:
            # The `role` column is a native Postgres ENUM type whose only
            # valid values are: USER, COMPANY_ADMIN, FINANCIAL, OPERATION,
            # LEGAL, MASTER_ADMIN — there is no "OPERATIONS" (plural) or
            # "FINANCE" member. Postgres validates every literal in an
            # `IN (...)` list against the enum, so including even one
            # invalid alias (e.g. querying role IN ('OPERATIONS',
            # 'OPERATION')) fails the ENTIRE query with "invalid input
            # value for enum userrole" — even though 'OPERATION' alongside
            # it is valid. This was silently breaking every notification
            # sent to Operations or Financial (caught by the except below).
            # Fix: normalize to the single canonical value instead of
            # querying multiple aliases.
            CANONICAL_ROLE = {
                'OPERATIONS': 'OPERATION',
                'FINANCE': 'FINANCIAL',
            }
            canonical_role = CANONICAL_ROLE.get(role, role)
            roles_to_check = [canonical_role]

            # Handle both SQLite and PostgreSQL
            # For SQLite, use IN clause with positional params or string format with proper escaping
            placeholders = ', '.join([f':role{i}' for i in range(len(roles_to_check))])
            params = {f'role{i}': r for i, r in enumerate(roles_to_check)}
            
            users = await db.execute(
                text(f"SELECT email FROM users WHERE role IN ({placeholders}) AND is_active = true"),
                params
            )
            emails = [row[0] for row in users.fetchall()]
            print(f"[NOTIFY] Sending to {len(emails)} {role} users ({emails})")
            for email in emails:
                await NotificationService.send(
                    db, email, title, message, ntype, action_url, workflow_id, related_po_id
                )
        except Exception as e:
            print(f"[NOTIFY] Role notify failed: {e}")
            import traceback
            traceback.print_exc()
            # IMPORTANT: without rolling back here, a failure in the queries
            # above (e.g. a bad column in the INSERT) leaves the DB
            # transaction aborted. Every statement run afterwards on this
            # same session - e.g. an audit_logs insert during the route's
            # final db.commit() - then fails with "current transaction is
            # aborted, commands ignored until end of transaction block",
            # which hides the real error above.
            try:
                await db.rollback()
            except Exception as rollback_err:
                print(f"[NOTIFY] Rollback after error also failed: {rollback_err}")

    @staticmethod
    async def notify_po_approval_submitted(db: AsyncSession, po_number: str):
        """Notify MASTER_ADMIN + OPERATIONS that a PO has evidence/edits
        awaiting their approval — this was previously called from
        submit_po_for_approval but never existed, so every PO submission
        silently failed to notify anyone (caught by that call site's own
        try/except). This is why the "PO Approvals" queue could show
        pending items with zero notification ever having fired."""
        for role in ("MASTER_ADMIN", "OPERATIONS"):
            await NotificationService.send_to_role(
                db, role,
                title="PO Approval Needed",
                message=f"PO {po_number} has evidence/edits awaiting your approval.",
                ntype="PO",
                action_url="/dashboard/admin",
            )

    @staticmethod
    async def notify_subscription_activated(db: AsyncSession, to_email: str, plan_name: str):
        """Confirm to the user that their subscription/plan was activated
        after a verified payment. Was previously called but never defined,
        so this silently never fired (caught by that call site's own
        try/except)."""
        await NotificationService.send(
            db, to_email,
            title="Subscription Activated",
            message=f"Your {plan_name} plan is now active.",
            ntype="SUBSCRIPTION",
            action_url="/membership",
        )

    @staticmethod
    async def get_for_user(db: AsyncSession, email: str):
        try:
            result = await db.execute(text("""
                SELECT id, title, message, type, is_read, action_url, created_at
                FROM notifications WHERE user_email = :e
                ORDER BY created_at DESC LIMIT 50
            """), {"e": email})
            rows = result.mappings().all()
            return [dict(r) for r in rows]
        except Exception:
            return []

    @staticmethod
    async def get_unread_count(db: AsyncSession, email: str):
        try:
            result = await db.execute(
                text("SELECT COUNT(*) FROM notifications WHERE user_email = :e AND is_read = false"),
                {"e": email}
            )
            return result.scalar() or 0
        except Exception:
            return 0

    @staticmethod
    async def mark_read(db: AsyncSession, notif_id: str, email: str):
        try:
            await db.execute(
                text("UPDATE notifications SET is_read = true WHERE id = :id AND user_email = :e"),
                {"id": notif_id, "e": email}
            )
            await db.commit()
        except Exception as e:
            print(f"[NOTIFY] Mark read failed: {e}")

    @staticmethod
    async def mark_all_read(db: AsyncSession, email: str):
        try:
            await db.execute(
                text("UPDATE notifications SET is_read = true WHERE user_email = :e"),
                {"e": email}
            )
            await db.commit()
        except Exception as e:
            print(f"[NOTIFY] Mark all read failed: {e}")

    @staticmethod
    async def notify_po_created_for_vendor(
        db: AsyncSession,
        vendor_company_id: str,
        po_number: str,
        buyer_company_name: str,
        vendor_name: str,
        amount: float,
        due_date: str,
        order_date: str,
        gstin: str,
        buyer_credibility: dict = None
    ):
        from app.models import User
        from sqlalchemy import select
        
        try:
            admin_stmt = select(User).where(
                (User.company_id == vendor_company_id) &
                (User.is_active == True) &
                (User.role.in_(["MASTER_ADMIN", "COMPANY_ADMIN"]))
            )
            admin_res = await db.execute(admin_stmt)
            admins = admin_res.scalars().all()
            
            for admin in admins:
                await db.execute(text("""
                    INSERT INTO notifications (id, user_id, user_email, title, message, type, action_url, is_read, created_at)
                    VALUES (:id, :uid, :email, :title, :message, 'PO_CREATED', :url, false, NOW())
                """), {
                    "id": str(uuid.uuid4()),
                    "uid": admin.id,
                    "email": admin.email,
                    "title": f"New PO {po_number} from {buyer_company_name}",
                    "message": f"PO {po_number} from {buyer_company_name} to {vendor_name} - Amount: ₹{amount}, Due Date: {due_date}",
                    "url": "/dashboard/user"
                })
            
            await db.commit()
            print(f"[NOTIFY] PO {po_number} vendor notifications sent")
            
            email_svc = EmailService()
            subj = f"New PO {po_number} from {buyer_company_name}"
            body_lines = [
                f"PO Number: {po_number}",
                f"Vendor: {vendor_name}",
                f"Buyer Company: {buyer_company_name}",
                f"GSTIN: {gstin}",
                f"Amount: ₹{amount}",
                f"Order Date: {order_date}",
                f"Due Date: {due_date}"
            ]
            if buyer_credibility:
                body_lines.append(f"Buyer Credibility Index: {buyer_credibility.get('score')} (Grade {buyer_credibility.get('grade')}, Risk {buyer_credibility.get('risk_level')})")
            
            body = "\n".join(body_lines)
            
            for admin in admins:
                if admin.email:
                    await email_svc.send_email(admin.email, subj, body)
            
        except Exception as e:
            print(f"[NOTIFY] PO vendor notification failed: {e}")