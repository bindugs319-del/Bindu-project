"""
Client-authorized read-only admin view access — API endpoints.

Client side   (/api/v1/access-grants):        generate codes, list/revoke grants, see activity.
Admin side    (/api/v1/admin/client-access):  redeem codes, list own grants, banner info.
Super Admin   (/api/v1/admin/client-access):  all grants, revoke any, full audit log.

The read-only data views themselves are NOT here: they reuse every existing
client endpoint via the X-Delegated-Grant header (see get_current_user).
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.models.admin_access import AdminAccessCode, AdminAccessGrant, DelegatedAccessAudit
from app.services import delegated_access_service as das
from app.utils import ResponseFormatter

client_router = APIRouter(prefix="/access-grants", tags=["Admin View Access (Client)"])
admin_router = APIRouter(prefix="/admin/client-access", tags=["Admin View Access (Admin)"])

GRANT_NOT_FOUND = "Access grant not found."


class GenerateCodeRequest(BaseModel):
    duration_hours: int = Field(default=das.DEFAULT_DURATION_HOURS)


class RedeemCodeRequest(BaseModel):
    code: str = Field(..., min_length=10, max_length=2000)


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


def _req_id(request: Request) -> str:
    return getattr(getattr(request, "state", None), "request_id", "") or ""


def _require_client(user: User):
    if not das.is_client(user):
        raise das._forbidden("NOT_A_CLIENT_ACCOUNT", "Only client accounts can manage admin access.")


def _require_redeemer(user: User):
    if not das.can_redeem(user):
        raise das._forbidden("NOT_ALLOWED", "Only Operation Admins and Super Admins can use client access.")


def _require_super(user: User):
    if not das.is_super_admin(user):
        raise das._forbidden("SUPER_ADMIN_ONLY", "Super Admin access required.")


async def _last_viewed(db: AsyncSession, grant_ids):
    if not grant_ids:
        return {}
    rows = await db.execute(
        select(DelegatedAccessAudit.grant_id, func.max(DelegatedAccessAudit.created_at))
        .where(DelegatedAccessAudit.grant_id.in_(grant_ids), DelegatedAccessAudit.event == das.Events.VIEWED)
        .group_by(DelegatedAccessAudit.grant_id)
    )
    return dict(rows.all())


def _admin_grant_dict(grant, client, admin=None, last_viewed=None):
    data = {
        "id": grant.id,
        "status": das.grant_status(grant),
        "granted_at": _iso(grant.granted_at),
        "expires_at": _iso(grant.expires_at),
        "revoked_at": _iso(grant.revoked_at),
        "last_viewed_at": _iso(last_viewed),
        "client": {
            "id": client.id if client else grant.client_user_id,
            "company_name": (client.company_name if client else None) or "Client",
            "gstin": client.gstin if client else None,
            "email": client.email if client else None,
        },
    }
    if admin is not None:
        data["admin"] = {"id": admin.id, "name": admin.name, "email": admin.email, "role": das.role_of(admin)}
    return data


# ============================================================ CLIENT SIDE

@client_router.post("/codes")
async def generate_code(
    body: GenerateCodeRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    plaintext, row = await das.create_code(db, current_user, body.duration_hours, request)
    company = current_user.company_name or current_user.email
    return ResponseFormatter.create_success(
        data={
            "code_id": row.id,
            "code": plaintext,  # shown once; only the hash is stored
            "message": das.authorization_message(plaintext, company, row.duration_hours),
            "duration_hours": row.duration_hours,
            "redeem_by": _iso(row.redeem_by),
        },
        message="Authorization code generated",
        request_id=_req_id(request),
    )


@client_router.get("")
async def list_my_grants(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _require_client(current_user)
    await das.ensure_tables(db)
    admin_alias = aliased(User)
    rows = (await db.execute(
        select(AdminAccessGrant, admin_alias.role)
        .outerjoin(admin_alias, admin_alias.id == AdminAccessGrant.admin_id)
        .where(AdminAccessGrant.client_user_id == current_user.id)
        .order_by(AdminAccessGrant.granted_at.desc())
        .limit(50)
    )).all()
    grants = [g for g, _ in rows]
    await das.log_expired(db, grants)
    last = await _last_viewed(db, [g.id for g in grants])

    now = das._now()
    pending = (await db.execute(
        select(AdminAccessCode).where(
            AdminAccessCode.client_user_id == current_user.id,
            AdminAccessCode.redeemed_at.is_(None),
            AdminAccessCode.cancelled_at.is_(None),
            AdminAccessCode.redeem_by > now,
        ).order_by(AdminAccessCode.created_at.desc())
    )).scalars().all()

    return ResponseFormatter.create_success(
        data={
            "grants": [{
                "id": g.id,
                "used_by": das.team_label(str(getattr(role, "value", role)) if role else None),
                "status": das.grant_status(g, now),
                "granted_at": _iso(g.granted_at),
                "expires_at": _iso(g.expires_at),
                "revoked_at": _iso(g.revoked_at),
                "last_viewed_at": _iso(last.get(g.id)),
            } for g, role in rows],
            "pending_codes": [{
                "id": c.id,
                "duration_hours": c.duration_hours,
                "created_at": _iso(c.created_at),
                "redeem_by": _iso(c.redeem_by),
            } for c in pending],
        },
        request_id=_req_id(request),
    )


@client_router.post("/codes/{code_id}/cancel")
async def cancel_code(
    code_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _require_client(current_user)
    await das.ensure_tables(db)
    code = await db.get(AdminAccessCode, code_id)
    if not code or code.client_user_id != current_user.id:
        raise das._forbidden("NOT_FOUND", "Code not found.", 404)
    if code.redeemed_at is None and code.cancelled_at is None:
        code.cancelled_at = das._now()
        das.log_event(db, das.Events.CODE_CANCELLED, code_id=code.id, client_user_id=current_user.id, request=request)
        await db.commit()
    return ResponseFormatter.create_success(message="Code cancelled", request_id=_req_id(request))


@client_router.post("/{grant_id}/revoke")
async def client_revoke(
    grant_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _require_client(current_user)
    await das.ensure_tables(db)
    grant = await db.get(AdminAccessGrant, grant_id)
    if not grant or grant.client_user_id != current_user.id:
        raise das._forbidden("NOT_FOUND", GRANT_NOT_FOUND, 404)
    await das.revoke_grant(db, grant, current_user, "CLIENT", request)
    return ResponseFormatter.create_success(message="Access revoked", request_id=_req_id(request))


@client_router.get("/activity")
async def client_activity(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Simplified log for the client: 'Operation Team viewed your invoices on ...'."""
    _require_client(current_user)
    await das.ensure_tables(db)
    rows = (await db.execute(
        select(DelegatedAccessAudit)
        .where(
            DelegatedAccessAudit.client_user_id == current_user.id,
            DelegatedAccessAudit.event.in_([
                das.Events.REDEEMED, das.Events.VIEWED, das.Events.REVOKED, das.Events.EXPIRED,
            ]),
        )
        .order_by(DelegatedAccessAudit.created_at.desc())
        .limit(500)
    )).scalars().all()

    # Admin role per grant (for the team label), since VIEWED rows store it
    # but REVOKED/EXPIRED rows may not.
    grant_ids = {r.grant_id for r in rows if r.grant_id}
    roles = {}
    if grant_ids:
        role_rows = await db.execute(
            select(AdminAccessGrant.id, User.role)
            .join(User, User.id == AdminAccessGrant.admin_id)
            .where(AdminAccessGrant.id.in_(grant_ids))
        )
        roles = {gid: str(getattr(r, "value", r)) for gid, r in role_rows.all()}

    items, seen = [], set()
    for r in rows:
        team = das.team_label(r.admin_role or roles.get(r.grant_id))
        if r.event == das.Events.VIEWED:
            key = (r.grant_id, r.resource, r.created_at.strftime("%Y-%m-%d %H"))
            if key in seen:
                continue
            seen.add(key)
            text = f"{team} viewed your {r.resource or 'account'}"
        elif r.event == das.Events.REDEEMED:
            text = f"{team} started viewing your account (code redeemed)"
        elif r.event == das.Events.REVOKED:
            text = "View access was revoked" + (" by you" if "CLIENT" in (r.detail or "") else f" by {team}")
        else:
            text = f"{team}'s view access expired"
        items.append({"text": text, "at": _iso(r.created_at), "event": r.event})
        if len(items) >= 50:
            break
    return ResponseFormatter.create_success(data={"items": items}, request_id=_req_id(request))


# ============================================================ ADMIN SIDE

@admin_router.post("/redeem")
async def redeem(
    body: RedeemCodeRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    grant = await das.redeem_code(db, current_user, body.code, request)
    client = await db.get(User, grant.client_user_id)
    return ResponseFormatter.create_success(
        data=_admin_grant_dict(grant, client),
        message=f"Access granted to {(client.company_name if client else None) or 'client'} (read-only)",
        request_id=_req_id(request),
    )


async def _grants_with_clients(db: AsyncSession, *conditions, with_admin: bool = False):
    client_alias = aliased(User)
    admin_alias = aliased(User)
    stmt = select(AdminAccessGrant, client_alias, admin_alias).outerjoin(client_alias, client_alias.id == AdminAccessGrant.client_user_id) \
        .outerjoin(admin_alias, admin_alias.id == AdminAccessGrant.admin_id).where(*conditions) \
        .order_by(AdminAccessGrant.expires_at.asc())
    rows = (await db.execute(stmt)).all()
    await das.log_expired(db, [g for g, _, _ in rows])
    last = await _last_viewed(db, [g.id for g, _, _ in rows])
    return [_admin_grant_dict(g, c, a if with_admin else None, last.get(g.id)) for g, c, a in rows]


def _active_conditions():
    now = das._now()
    return (AdminAccessGrant.revoked_at.is_(None), AdminAccessGrant.expires_at > now)


@admin_router.get("/mine")
async def my_clients(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Clients who have authorized THIS admin (active grants only)."""
    _require_redeemer(current_user)
    await das.ensure_tables(db)
    items = await _grants_with_clients(db, AdminAccessGrant.admin_id == current_user.id, *_active_conditions())
    return ResponseFormatter.create_success(data={"grants": items}, request_id=_req_id(request))


@admin_router.get("/grants/{grant_id}")
async def grant_session(
    grant_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Banner/session info for a grant the caller owns (status, company, expiry)."""
    _require_redeemer(current_user)
    await das.ensure_tables(db)
    grant = await db.get(AdminAccessGrant, grant_id)
    if not grant or grant.admin_id != current_user.id:
        raise das._forbidden("NOT_FOUND", GRANT_NOT_FOUND, 404)
    await das.log_expired(db, [grant])
    client = await db.get(User, grant.client_user_id)
    return ResponseFormatter.create_success(data=_admin_grant_dict(grant, client), request_id=_req_id(request))


@admin_router.post("/grants/{grant_id}/revoke")
async def admin_revoke(
    grant_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Super Admin can revoke any grant; other admins only their own."""
    _require_redeemer(current_user)
    await das.ensure_tables(db)
    grant = await db.get(AdminAccessGrant, grant_id)
    is_super = das.is_super_admin(current_user)
    if not grant or (grant.admin_id != current_user.id and not is_super):
        raise das._forbidden("NOT_FOUND", GRANT_NOT_FOUND, 404)
    await das.revoke_grant(db, grant, current_user, "MASTER_ADMIN" if is_super else "ADMIN", request)
    return ResponseFormatter.create_success(message="Access revoked", request_id=_req_id(request))


@admin_router.get("/all")
async def all_grants(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Super Admin: every active grant across all admins."""
    _require_super(current_user)
    await das.ensure_tables(db)
    items = await _grants_with_clients(db, *_active_conditions(), with_admin=True)
    return ResponseFormatter.create_success(data={"grants": items}, request_id=_req_id(request))


@admin_router.get("/audit")
async def audit_log(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    grant_id: Optional[str] = None,
    client_user_id: Optional[str] = None,
    admin_id: Optional[str] = None,
    event: Optional[str] = None,
):
    """Super Admin: full delegated-access audit log."""
    _require_super(current_user)
    await das.ensure_tables(db)
    client_alias = aliased(User)
    admin_alias = aliased(User)
    stmt = select(DelegatedAccessAudit, client_alias.company_name, admin_alias.email) \
        .outerjoin(client_alias, client_alias.id == DelegatedAccessAudit.client_user_id) \
        .outerjoin(admin_alias, admin_alias.id == DelegatedAccessAudit.admin_id)
    if grant_id:
        stmt = stmt.where(DelegatedAccessAudit.grant_id == grant_id)
    if client_user_id:
        stmt = stmt.where(DelegatedAccessAudit.client_user_id == client_user_id)
    if admin_id:
        stmt = stmt.where(DelegatedAccessAudit.admin_id == admin_id)
    if event:
        stmt = stmt.where(DelegatedAccessAudit.event == event.upper())
    rows = (await db.execute(stmt.order_by(DelegatedAccessAudit.created_at.desc()).limit(limit))).all()
    return ResponseFormatter.create_success(
        data={"items": [{
            "id": r.id,
            "event": r.event,
            "at": _iso(r.created_at),
            "admin_id": r.admin_id,
            "admin_email": admin_email,
            "admin_role": r.admin_role,
            "client_user_id": r.client_user_id,
            "client_company": company,
            "grant_id": r.grant_id,
            "method": r.method,
            "path": r.path,
            "resource": r.resource,
            "ip": r.ip,
            "detail": r.detail,
        } for r, company, admin_email in rows]},
        request_id=_req_id(request),
    )
