"""
Client-authorized read-only "view access" for Operation Admins / Super Admins.

Security model (see app/models/admin_access.py):
- The admin never receives the client's password or session. A delegated
  request is authenticated as the ADMIN (their own token) and carries the
  header X-Delegated-Grant: <grant_id>. resolve_delegation() re-checks the
  grant on EVERY request (owner, not revoked, not expired) and only then
  substitutes the client's User as current_user, so every existing
  client-facing endpoint serves the client's data unchanged.
- Delegated requests are read-only: enforced here AND in
  DelegatedReadOnlyMiddleware, independent of the frontend.
- Only an HMAC of the authorization code is stored. Codes are 160-bit,
  single-use (atomic conditional UPDATE), bound to the redeeming admin,
  and die if not redeemed within CODE_REDEEM_WINDOW.
"""
import asyncio
import hashlib
import hmac
import base64
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User
from app.models.admin_access import AdminAccessCode, AdminAccessGrant, DelegatedAccessAudit

logger = logging.getLogger(__name__)

DELEGATION_HEADER = "X-Delegated-Grant"

CODE_PREFIX = "CDW"
CODE_REDEEM_WINDOW = timedelta(minutes=30)
ALLOWED_DURATIONS_HOURS = (24, 72, 168)
DEFAULT_DURATION_HOURS = 24

# Per-admin brute-force guard (on top of the per-IP RateLimitMiddleware entry)
MAX_FAILED_REDEEMS = 10
FAILED_REDEEM_WINDOW = timedelta(minutes=15)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# GET endpoints that write to the database — never allowed under delegation.
BLOCKED_GET_PATHS = (
    "/api/v1/sales-invoices/next-number",
)
# The grant-management endpoints themselves are never usable "as the client".
BLOCKED_PATH_PREFIXES = (
    "/api/v1/access-grants",
    "/api/v1/admin/client-access",
    "/api/v1/organization",
    "/api/v1/admin/organizations",
)

CLIENT_ROLES = {"USER", "COMPANY_ADMIN"}
REDEEMER_ROLES = {"OPERATION", "OPERATIONS", "MASTER_ADMIN"}

RESOURCE_LABELS = {
    "invoices": "invoices",
    "sales-invoices": "invoices",
    "vendor-invoices": "vendor bills",
    "purchase-orders": "purchase orders",
    "pos": "purchase orders",
    "purchase-history": "purchase history",
    "defaulters": "defaulter reports",
    "settlements": "settlements",
    "credit-reports": "credit reports",
    "user": "profile",
    "account": "profile",
    "wallet": "wallet",
    "notifications": "notifications",
    "subscriptions": "membership",
    "appointments": "appointments",
    "credibility": "credibility index",
    "inv-credibility": "credibility index",
    "activity": "activity",
}


class Events:
    CODE_GENERATED = "CODE_GENERATED"
    CODE_CANCELLED = "CODE_CANCELLED"
    REDEEMED = "REDEEMED"
    REDEEM_FAILED = "REDEEM_FAILED"
    VIEWED = "VIEWED"
    WRITE_BLOCKED = "WRITE_BLOCKED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


def _now() -> datetime:
    # Naive UTC, matching the rest of the schema (datetime.utcnow defaults)
    return datetime.utcnow()


def role_of(user) -> str:
    role = getattr(user, "role", None)
    return str(getattr(role, "value", role) or "").upper()


def is_super_admin(user) -> bool:
    return role_of(user) == "MASTER_ADMIN" or getattr(user, "email", None) in settings.DEVELOPER_EMAILS


def can_redeem(user) -> bool:
    return role_of(user) in REDEEMER_ROLES or is_super_admin(user)


def is_client(user) -> bool:
    return role_of(user) in CLIENT_ROLES and not is_super_admin(user)


def team_label(role: Optional[str]) -> str:
    """Client-facing name for an admin role (individual names are not shown)."""
    return "Super Admin" if (role or "").upper() == "MASTER_ADMIN" else "Operation Team"


def client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def resource_for_path(path: str) -> str:
    rest = path.split("/api/v1/", 1)[-1].strip("/")
    first = rest.split("/", 1)[0] if rest else ""
    return RESOURCE_LABELS.get(first, first.replace("-", " ") or "dashboard")


def is_write_blocked(method: str, path: str) -> bool:
    if method.upper() not in SAFE_METHODS:
        return True
    clean = path.rstrip("/")
    if clean in BLOCKED_GET_PATHS:
        return True
    return any(clean.startswith(p) for p in BLOCKED_PATH_PREFIXES)


# ---------------------------------------------------------------- codes

def generate_code() -> str:
    """160-bit random code, e.g. CDW-ABCD-EFGH-... (8 groups of 4, base32)."""
    body = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    return CODE_PREFIX + "-" + "-".join(body[i:i + 4] for i in range(0, len(body), 4))


_CODE_IN_TEXT = re.compile(r"CDW(?:[\s-]*[A-Z2-7]){32}")


def normalize_code(text: str) -> str:
    """Accept the bare code or the whole pasted message; ignore case/spacing/dashes."""
    upper = (text or "").upper()
    found = _CODE_IN_TEXT.search(upper)
    if found:
        upper = found.group(0)
    compact = re.sub(r"[^A-Z0-9]", "", upper)
    if not compact.startswith(CODE_PREFIX):
        compact = CODE_PREFIX + compact
    return compact


def hash_code(text: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), normalize_code(text).encode(), hashlib.sha256).hexdigest()


def authorization_message(code: str, company_name: str, duration_hours: int) -> str:
    span = f"{duration_hours // 24} day{'s' if duration_hours > 24 else ''}" if duration_hours >= 24 else f"{duration_hours} hours"
    return (
        f"I, {company_name}, authorize the CreditDataWatch team to VIEW my account (read-only) "
        f"for {span}.\nAuthorization code: {code}\n"
        f"This code works once and must be used within {int(CODE_REDEEM_WINDOW.total_seconds() // 60)} minutes."
    )


# ---------------------------------------------------------------- tables

_tables_ready = False
_tables_lock = asyncio.Lock()


async def ensure_tables(db: AsyncSession) -> None:
    """Create this feature's tables if missing (idempotent, own commit).

    Safety net for deployments that don't run Alembic; the real migration is
    migrations/versions/y6n7o8p9q0r1_add_admin_access_tables.py.
    """
    global _tables_ready
    if _tables_ready:
        return
    async with _tables_lock:
        if _tables_ready:
            return
        tables = [AdminAccessCode.__table__, AdminAccessGrant.__table__, DelegatedAccessAudit.__table__]
        conn = await db.connection()
        await conn.run_sync(lambda sync_conn: AdminAccessCode.metadata.create_all(sync_conn, tables=tables, checkfirst=True))
        await db.commit()
        _tables_ready = True


# ---------------------------------------------------------------- audit

def log_event(
    db: AsyncSession,
    event: str,
    *,
    grant: Optional[AdminAccessGrant] = None,
    code_id: Optional[str] = None,
    admin: Optional[User] = None,
    admin_id: Optional[str] = None,
    admin_role: Optional[str] = None,
    client_user_id: Optional[str] = None,
    request: Optional[Request] = None,
    resource: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """Queue an audit row on the session (caller commits)."""
    db.add(DelegatedAccessAudit(
        id=str(uuid.uuid4()),
        event=event,
        grant_id=grant.id if grant else None,
        code_id=code_id or (grant.code_id if grant else None),
        admin_id=(admin.id if admin else None) or admin_id or (grant.admin_id if grant else None),
        admin_role=(role_of(admin) if admin else None) or admin_role,
        client_user_id=client_user_id or (grant.client_user_id if grant else None),
        method=request.method if request else None,
        path=str(request.url.path)[:500] if request else None,
        resource=resource,
        ip=client_ip(request),
        detail=detail,
        created_at=_now(),
    ))


def grant_status(grant: AdminAccessGrant, now: Optional[datetime] = None) -> str:
    now = now or _now()
    if grant.revoked_at:
        return "REVOKED"
    if grant.expires_at <= now:
        return "EXPIRED"
    return "ACTIVE"


async def log_expired(db: AsyncSession, grants) -> None:
    """Record the EXPIRED event once per grant (lazily, when next seen)."""
    now = _now()
    changed = False
    for g in grants:
        if not g.revoked_at and g.expires_at <= now and not g.expiry_logged:
            g.expiry_logged = True
            log_event(db, Events.EXPIRED, grant=g, detail=f"expired at {g.expires_at.isoformat()}Z")
            changed = True
    if changed:
        await db.commit()


# ---------------------------------------------------------------- flows

def _forbidden(code: str, msg: str, status_code: int = status.HTTP_403_FORBIDDEN) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "msg": msg})


async def create_code(db: AsyncSession, client: User, duration_hours: int, request: Optional[Request] = None):
    await ensure_tables(db)
    if not is_client(client):
        raise _forbidden("NOT_A_CLIENT_ACCOUNT", "Only client accounts can grant admin access.")
    if duration_hours not in ALLOWED_DURATIONS_HOURS:
        raise _forbidden("INVALID_DURATION", "Duration must be 24, 72 or 168 hours.", status.HTTP_400_BAD_REQUEST)

    plaintext = generate_code()
    now = _now()
    row = AdminAccessCode(
        id=str(uuid.uuid4()),
        client_user_id=client.id,
        company_id=client.company_id,
        code_hash=hash_code(plaintext),
        duration_hours=duration_hours,
        created_at=now,
        redeem_by=now + CODE_REDEEM_WINDOW,
    )
    db.add(row)
    log_event(db, Events.CODE_GENERATED, code_id=row.id, client_user_id=client.id, request=request,
              detail=f"duration={duration_hours}h")
    await db.commit()
    return plaintext, row


async def redeem_code(db: AsyncSession, admin: User, code_text: str, request: Optional[Request] = None) -> AdminAccessGrant:
    await ensure_tables(db)
    if not can_redeem(admin):
        raise _forbidden("NOT_ALLOWED", "Only Operation Admins and Super Admins can redeem authorization codes.")

    now = _now()
    failures = (await db.execute(
        select(func.count(DelegatedAccessAudit.id)).where(
            DelegatedAccessAudit.event == Events.REDEEM_FAILED,
            DelegatedAccessAudit.admin_id == admin.id,
            DelegatedAccessAudit.created_at > now - FAILED_REDEEM_WINDOW,
        )
    )).scalar() or 0
    if failures >= MAX_FAILED_REDEEMS:
        raise _forbidden("TOO_MANY_ATTEMPTS", "Too many failed attempts. Try again in 15 minutes.",
                         status.HTTP_429_TOO_MANY_REQUESTS)

    code_hash = hash_code(code_text)
    # Atomic single-use: only one UPDATE can flip redeemed_at from NULL.
    result = await db.execute(
        update(AdminAccessCode)
        .where(
            AdminAccessCode.code_hash == code_hash,
            AdminAccessCode.redeemed_at.is_(None),
            AdminAccessCode.cancelled_at.is_(None),
            AdminAccessCode.redeem_by > now,
        )
        .values(redeemed_at=now, redeemed_by_admin_id=admin.id)
        .returning(AdminAccessCode.id, AdminAccessCode.client_user_id, AdminAccessCode.company_id,
                   AdminAccessCode.duration_hours)
    )
    claimed = result.first()
    if not claimed:
        # Nothing was updated, so there is nothing to roll back (a rollback
        # here would also expire `admin` and break attribute access below).
        log_event(db, Events.REDEEM_FAILED, admin=admin, request=request)
        await db.commit()
        raise _forbidden("INVALID_CODE", "This code is invalid, expired, cancelled or already used.",
                         status.HTTP_400_BAD_REQUEST)

    code_id, client_user_id, company_id, duration_hours = claimed
    grant = AdminAccessGrant(
        id=str(uuid.uuid4()),
        code_id=code_id,
        admin_id=admin.id,
        client_user_id=client_user_id,
        company_id=company_id,
        granted_at=now,
        expires_at=now + timedelta(hours=duration_hours),
    )
    db.add(grant)
    log_event(db, Events.REDEEMED, grant=grant, admin=admin, request=request,
              detail=f"expires_at={grant.expires_at.isoformat()}Z")
    await db.commit()

    client = await db.get(User, client_user_id)
    if client and client.email:
        try:
            from app.services.notification_service import NotificationService
            await NotificationService.send(
                db,
                to_email=client.email,
                title="Admin view access granted",
                message=(
                    f"Your authorization code was used by the {team_label(role_of(admin))}. "
                    f"They can view your account (read-only) until "
                    f"{grant.expires_at.strftime('%d %b %Y, %H:%M')} UTC. "
                    f"You can revoke this anytime in Account > Grant Admin Access."
                ),
                ntype="SECURITY",
                action_url=f"{settings.FRONTEND_URL}/account",
            )
        except Exception as e:  # notification must never undo the grant
            logger.warning(f"[ADMIN ACCESS] Redeem notification failed: {e}")
    return grant


async def revoke_grant(db: AsyncSession, grant: AdminAccessGrant, actor: User, actor_kind: str,
                       request: Optional[Request] = None) -> AdminAccessGrant:
    if grant.revoked_at is None:
        grant.revoked_at = _now()
        grant.revoked_by_id = actor.id
        grant.revoked_by_role = actor_kind
        log_event(db, Events.REVOKED, grant=grant, admin=actor if actor_kind != "CLIENT" else None,
                  request=request, detail=f"revoked_by={actor_kind}")
        await db.commit()
    return grant


async def resolve_delegation(request: Request, db: AsyncSession, admin: User, grant_id: str) -> User:
    """Called from get_current_user when X-Delegated-Grant is present.

    Returns the CLIENT user for this request, or raises 403. Runs on every
    delegated request, so revocation/expiry take effect immediately.
    """
    await ensure_tables(db)
    if not can_redeem(admin):
        raise _forbidden("DELEGATION_NOT_ALLOWED", "Your role cannot use delegated view access.")

    grant = (await db.execute(
        select(AdminAccessGrant).where(AdminAccessGrant.id == grant_id, AdminAccessGrant.admin_id == admin.id)
    )).scalars().first()
    if not grant:
        raise _forbidden("DELEGATION_ENDED", "This view access is not valid for your account.")

    if grant.revoked_at:
        raise _forbidden("DELEGATION_ENDED", "The client revoked this view access.")
    if grant.expires_at <= _now():
        await log_expired(db, [grant])
        raise _forbidden("DELEGATION_ENDED", "This view access has expired.")

    path = str(request.url.path)
    if is_write_blocked(request.method, path):
        log_event(db, Events.WRITE_BLOCKED, grant=grant, admin=admin, request=request,
                  resource=resource_for_path(path))
        await db.commit()
        raise _forbidden("DELEGATION_READ_ONLY", "Read-only view: changes are not allowed while viewing a client account.")

    client = (await db.execute(
        select(User).where(User.id == grant.client_user_id, User.is_active == True)  # noqa: E712
    )).scalars().first()
    if not client:
        raise _forbidden("DELEGATION_ENDED", "The client account is no longer active.")

    log_event(db, Events.VIEWED, grant=grant, admin=admin, request=request, resource=resource_for_path(path))
    await db.commit()

    request.state.delegation = {
        "grant_id": grant.id,
        "admin_id": admin.id,
        "client_user_id": client.id,
        "expires_at": grant.expires_at,
    }
    return client
