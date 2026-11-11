"""
Head office / branch organisations.

Rules:
- A branch is its own company (own GSTIN, own login, sees only its own data).
- A branch links to a head office only if both GSTINs share the same PAN
  (GSTIN characters 3-12) and the head office approves it.
- A head office can have at most `branch_limit` approved branches; the limit
  is set by platform Super Admins (default 0 = must ask CreditDataWatch).
- A head office can VIEW an approved branch's account read-only via the
  X-Branch-View header (checked on every request in get_current_user, same
  read-only enforcement and audit trail as admin view access). No nesting:
  a branch can't have branches, a head office can't be a branch.
"""
import asyncio
import uuid
from datetime import datetime, date
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, User, SalesInvoice, PurchaseOrder, DefaulterCase
from app.models.organization import CompanyOrgSettings, CompanyBranchLink
from app.services import delegated_access_service as das

BRANCH_VIEW_HEADER = "X-Branch-View"
ORG_ADMIN_ROLES = {"COMPANY_ADMIN"}


class LinkStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REMOVED = "REMOVED"
    CANCELLED = "CANCELLED"


ACTIVE_LINK = (LinkStatus.PENDING, LinkStatus.APPROVED)


def _now() -> datetime:
    return datetime.utcnow()


def _err(code: str, msg: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "msg": msg})


def pan_of(gstin: Optional[str]) -> str:
    """PAN embedded in a GSTIN (characters 3-12)."""
    return (gstin or "").strip().upper()[2:12]


def is_org_admin(user) -> bool:
    return das.role_of(user) in ORG_ADMIN_ROLES


# ---------------------------------------------------------------- tables

_tables_ready = False
_tables_lock = asyncio.Lock()


async def ensure_tables(db: AsyncSession) -> None:
    """Create this feature's tables if missing (idempotent, own commit).
    Real migration: migrations/versions/z7o8p9q0r1s2_add_company_organisations.py"""
    global _tables_ready
    if _tables_ready:
        return
    async with _tables_lock:
        if _tables_ready:
            return
        tables = [CompanyOrgSettings.__table__, CompanyBranchLink.__table__]
        conn = await db.connection()
        await conn.run_sync(lambda c: CompanyOrgSettings.metadata.create_all(c, tables=tables, checkfirst=True))
        await db.commit()
        _tables_ready = True


# ---------------------------------------------------------------- lookups

async def get_settings(db: AsyncSession, company_id: str) -> Optional[CompanyOrgSettings]:
    return await db.get(CompanyOrgSettings, company_id) if company_id else None


async def _get_or_create_settings(db: AsyncSession, company_id: str) -> CompanyOrgSettings:
    row = await get_settings(db, company_id)
    if row is None:
        row = CompanyOrgSettings(company_id=company_id, is_headquarters=False, branch_limit=0)
        db.add(row)
        await db.flush()
    return row


async def active_link_for_branch(db: AsyncSession, branch_company_id: str) -> Optional[CompanyBranchLink]:
    return (await db.execute(
        select(CompanyBranchLink).where(
            CompanyBranchLink.branch_company_id == branch_company_id,
            CompanyBranchLink.status.in_(ACTIVE_LINK),
        )
    )).scalars().first()


async def approved_count(db: AsyncSession, hq_company_id: str) -> int:
    return (await db.execute(
        select(func.count(CompanyBranchLink.id)).where(
            CompanyBranchLink.hq_company_id == hq_company_id, CompanyBranchLink.status == LinkStatus.APPROVED,
        )
    )).scalar() or 0


async def branch_main_user(db: AsyncSession, company_id: str) -> Optional[User]:
    """The account whose data a head office sees when viewing this branch:
    the branch's company admin (first registered), else its first active user."""
    users = (await db.execute(
        select(User).where(User.company_id == company_id, User.is_active == True)  # noqa: E712
        .order_by(User.created_at.asc())
    )).scalars().all()
    for u in users:
        if das.role_of(u) == "COMPANY_ADMIN":
            return u
    return users[0] if users else None


# ---------------------------------------------------------------- validation

async def find_head_office(db: AsyncSession, hq_gstin: str, branch_gstin: str) -> Company:
    """Validate a branch request target. Raises with a clear message."""
    hq_gstin = (hq_gstin or "").strip().upper()
    branch_gstin = (branch_gstin or "").strip().upper()
    if len(hq_gstin) != 15:
        raise _err("INVALID_HQ_GSTIN", "Enter the head office's 15-character GSTIN.")
    if hq_gstin == branch_gstin:
        raise _err("SAME_COMPANY", "A branch must have a different GSTIN from its head office.")
    hq = (await db.execute(select(Company).where(Company.gstin == hq_gstin))).scalars().first()
    if hq is None:
        raise _err("HQ_NOT_FOUND", "No company is registered with that head office GSTIN.")
    settings = await get_settings(db, hq.id)
    if not (settings and settings.is_headquarters):
        raise _err("NOT_HEAD_OFFICE", "That company is not registered as a head office yet. Ask them to set it up first.")
    if pan_of(hq_gstin) != pan_of(branch_gstin):
        raise _err("PAN_MISMATCH", "The branch and head office GSTINs must belong to the same PAN (same legal entity).")
    return hq


# ---------------------------------------------------------------- actions

async def mark_head_office(db: AsyncSession, company_id: str) -> CompanyOrgSettings:
    await ensure_tables(db)
    if await active_link_for_branch(db, company_id):
        raise _err("IS_BRANCH", "This company is a branch (or has a pending branch request), so it can't be a head office.")
    row = await _get_or_create_settings(db, company_id)
    row.is_headquarters = True
    await db.commit()
    return row


async def request_branch(db: AsyncSession, user: User, hq_gstin: str, branch_name: str) -> CompanyBranchLink:
    await ensure_tables(db)
    if not is_org_admin(user):
        raise _err("NOT_ALLOWED", "Only your company admin can request to join a head office.", status.HTTP_403_FORBIDDEN)
    branch_name = (branch_name or "").strip()
    if not 2 <= len(branch_name) <= 120:
        raise _err("INVALID_BRANCH_NAME", "Enter a branch name, e.g. the city or state.")
    branch_company = await db.get(Company, user.company_id) if user.company_id else None
    if branch_company is None:
        raise _err("NO_COMPANY", "Your account isn't linked to a company.")
    own = await get_settings(db, branch_company.id)
    if own and own.is_headquarters:
        raise _err("IS_HEAD_OFFICE", "A head office can't also be a branch.")
    if await active_link_for_branch(db, branch_company.id):
        raise _err("ALREADY_LINKED", "Your company already has a head office link or a pending request.")
    hq = await find_head_office(db, hq_gstin, branch_company.gstin)
    link = CompanyBranchLink(
        id=str(uuid.uuid4()), hq_company_id=hq.id, branch_company_id=branch_company.id,
        branch_name=branch_name, status=LinkStatus.PENDING, requested_by=user.id, requested_at=_now(),
    )
    db.add(link)
    await db.commit()
    return link


async def _hq_link(db: AsyncSession, user: User, link_id: str) -> CompanyBranchLink:
    if not is_org_admin(user):
        raise _err("NOT_ALLOWED", "Only your company admin can manage branches.", status.HTTP_403_FORBIDDEN)
    link = await db.get(CompanyBranchLink, link_id)
    if not link or link.hq_company_id != user.company_id:
        raise _err("NOT_FOUND", "Branch request not found.", status.HTTP_404_NOT_FOUND)
    return link


async def decide(db: AsyncSession, user: User, link_id: str, approve: bool) -> CompanyBranchLink:
    await ensure_tables(db)
    link = await _hq_link(db, user, link_id)
    if link.status != LinkStatus.PENDING:
        raise _err("NOT_PENDING", "This request has already been handled.")
    if approve:
        settings = await _get_or_create_settings(db, link.hq_company_id)
        used = await approved_count(db, link.hq_company_id)
        if used >= (settings.branch_limit or 0):
            raise _err(
                "BRANCH_LIMIT_REACHED",
                f"Your plan allows {settings.branch_limit or 0} branch(es) and all are in use. "
                "Contact CreditDataWatch to raise your branch limit.",
            )
    link.status = LinkStatus.APPROVED if approve else LinkStatus.REJECTED
    link.decided_by = user.id
    link.decided_at = _now()
    await db.commit()
    return link


async def remove_branch(db: AsyncSession, user: User, link_id: str) -> CompanyBranchLink:
    await ensure_tables(db)
    link = await _hq_link(db, user, link_id)
    if link.status != LinkStatus.APPROVED:
        raise _err("NOT_APPROVED", "Only approved branches can be removed.")
    link.status = LinkStatus.REMOVED
    link.decided_by = user.id
    link.decided_at = _now()
    await db.commit()
    return link


async def cancel_request(db: AsyncSession, user: User) -> None:
    await ensure_tables(db)
    if not is_org_admin(user):
        raise _err("NOT_ALLOWED", "Only your company admin can cancel this request.", status.HTTP_403_FORBIDDEN)
    link = await active_link_for_branch(db, user.company_id)
    if not link or link.status != LinkStatus.PENDING:
        raise _err("NOT_PENDING", "There is no pending request to cancel.")
    link.status = LinkStatus.CANCELLED
    link.decided_by = user.id
    link.decided_at = _now()
    await db.commit()


async def set_branch_limit(db: AsyncSession, admin: User, company_id: str, limit: int) -> CompanyOrgSettings:
    await ensure_tables(db)
    if not das.is_super_admin(admin):
        raise _err("SUPER_ADMIN_ONLY", "Super Admin access required.", status.HTTP_403_FORBIDDEN)
    if not 0 <= limit <= 500:
        raise _err("INVALID_LIMIT", "Branch limit must be between 0 and 500.")
    if await db.get(Company, company_id) is None:
        raise _err("NOT_FOUND", "Company not found.", status.HTTP_404_NOT_FOUND)
    row = await _get_or_create_settings(db, company_id)
    row.branch_limit = limit
    row.limit_set_by = admin.id
    row.limit_set_at = _now()
    await db.commit()
    return row


# ---------------------------------------------------------------- reads

def _link_dict(link: CompanyBranchLink, company: Optional[Company]) -> dict:
    return {
        "id": link.id,
        "status": link.status,
        "branch_name": link.branch_name,
        "requested_at": link.requested_at.isoformat() + "Z" if link.requested_at else None,
        "decided_at": link.decided_at.isoformat() + "Z" if link.decided_at else None,
        "company": {
            "id": company.id if company else link.branch_company_id,
            "name": company.company_name if company else None,
            "gstin": company.gstin if company else None,
        },
    }


async def org_status(db: AsyncSession, user: User) -> dict:
    """What the Account page shows: independent / head office / branch."""
    await ensure_tables(db)
    company = await db.get(Company, user.company_id) if user.company_id else None
    if company is None:
        return {"type": "NONE", "can_manage": False}
    settings = await get_settings(db, company.id)
    data = {"company": {"id": company.id, "name": company.company_name, "gstin": company.gstin},
            "can_manage": is_org_admin(user)}
    if settings and settings.is_headquarters:
        links = (await db.execute(
            select(CompanyBranchLink, Company)
            .join(Company, Company.id == CompanyBranchLink.branch_company_id)
            .where(CompanyBranchLink.hq_company_id == company.id, CompanyBranchLink.status.in_(ACTIVE_LINK))
            .order_by(CompanyBranchLink.requested_at.asc())
        )).all()
        data.update({
            "type": "HEAD_OFFICE",
            "branch_limit": settings.branch_limit or 0,
            "approved_count": sum(1 for lk, _ in links if lk.status == LinkStatus.APPROVED),
            "branches": [_link_dict(lk, c) for lk, c in links],
        })
        return data
    link = await active_link_for_branch(db, company.id)
    if link:
        hq = await db.get(Company, link.hq_company_id)
        data.update({
            "type": "BRANCH",
            "link_status": link.status,
            "branch_name": link.branch_name,
            "head_office": {"name": hq.company_name if hq else None, "gstin": hq.gstin if hq else None},
        })
        return data
    data["type"] = "INDEPENDENT"
    return data


async def summary(db: AsyncSession, user: User) -> dict:
    """Head office: combined totals for itself + every approved branch."""
    await ensure_tables(db)
    settings = await get_settings(db, user.company_id) if user.company_id else None
    if not (settings and settings.is_headquarters):
        raise _err("NOT_HEAD_OFFICE", "Only a head office can see branch totals.", status.HTTP_403_FORBIDDEN)

    hq = await db.get(Company, user.company_id)
    links = (await db.execute(
        select(CompanyBranchLink).where(
            CompanyBranchLink.hq_company_id == hq.id, CompanyBranchLink.status == LinkStatus.APPROVED,
        ).order_by(CompanyBranchLink.branch_name.asc())
    )).scalars().all()
    units = [(hq.id, "Head office", None)] + [(lk.branch_company_id, lk.branch_name, lk.id) for lk in links]
    company_ids = [cid for cid, _, _ in units]
    today = date.today()

    unpaid = and_(
        SalesInvoice.archived.isnot(True),
        SalesInvoice.payment_completed_at.is_(None),
        SalesInvoice.status.notin_(("Paid", "Cancelled")),
    )
    inv_rows = (await db.execute(
        select(
            SalesInvoice.company_id,
            func.count(SalesInvoice.id).filter(SalesInvoice.archived.isnot(True)),
            func.coalesce(func.sum(SalesInvoice.total * SalesInvoice.exchange_rate).filter(unpaid), 0.0),
            func.count(SalesInvoice.id).filter(and_(unpaid, SalesInvoice.payment_due_date < today)),
        ).where(SalesInvoice.company_id.in_(company_ids)).group_by(SalesInvoice.company_id)
    )).all()
    po_rows = (await db.execute(
        select(PurchaseOrder.company_id, func.count(PurchaseOrder.id))
        .where(PurchaseOrder.company_id.in_(company_ids), PurchaseOrder.archived.isnot(True))
        .group_by(PurchaseOrder.company_id)
    )).all()
    def_rows = (await db.execute(
        select(User.company_id, func.count(DefaulterCase.id))
        .join(User, User.id == DefaulterCase.user_id)
        .where(User.company_id.in_(company_ids))
        .group_by(User.company_id)
    )).all()

    inv = {cid: (n, float(out or 0), od) for cid, n, out, od in inv_rows}
    pos = dict(po_rows)
    defs = dict(def_rows)
    companies = {c.id: c for c in (await db.execute(select(Company).where(Company.id.in_(company_ids)))).scalars().all()}

    rows = []
    for cid, label, link_id in units:
        n, out, od = inv.get(cid, (0, 0.0, 0))
        c = companies.get(cid)
        rows.append({
            "company_id": cid, "link_id": link_id, "label": label, "is_head_office": link_id is None,
            "company_name": c.company_name if c else None, "gstin": c.gstin if c else None,
            "invoices": n, "outstanding": round(out, 2), "overdue_invoices": od,
            "purchase_orders": pos.get(cid, 0), "defaulter_cases": defs.get(cid, 0),
        })
    totals = {k: sum(r[k] for r in rows) for k in ("invoices", "outstanding", "overdue_invoices", "purchase_orders", "defaulter_cases")}
    totals["outstanding"] = round(totals["outstanding"], 2)
    return {"rows": rows, "totals": totals, "branch_limit": settings.branch_limit or 0, "approved_count": len(links)}


async def branch_session(db: AsyncSession, user: User, branch_company_id: str) -> dict:
    """Banner info for a head office viewing a branch (or 404 if not allowed)."""
    await ensure_tables(db)
    link = await _approved_link(db, user, branch_company_id)
    if link is None:
        raise _err("NOT_FOUND", "Branch not found.", status.HTTP_404_NOT_FOUND)
    company = await db.get(Company, branch_company_id)
    return {"status": "ACTIVE", "branch_name": link.branch_name,
            "company_name": company.company_name if company else None}


async def _approved_link(db: AsyncSession, user: User, branch_company_id: str) -> Optional[CompanyBranchLink]:
    if not user.company_id or not is_org_admin(user):
        return None
    return (await db.execute(
        select(CompanyBranchLink).where(
            CompanyBranchLink.hq_company_id == user.company_id,
            CompanyBranchLink.branch_company_id == branch_company_id,
            CompanyBranchLink.status == LinkStatus.APPROVED,
        )
    )).scalars().first()


# ---------------------------------------------------------------- read-only branch view

async def resolve_branch_view(request: Request, db: AsyncSession, user: User, branch_company_id: str) -> User:
    """Called from get_current_user when X-Branch-View is present. Returns the
    branch's main user (read-only) or raises 403. Runs on every request, so
    removing the branch ends access on the next request."""
    await ensure_tables(db)
    link = await _approved_link(db, user, branch_company_id)
    if link is None:
        raise das._forbidden("DELEGATION_ENDED", "You can no longer view this branch.")

    path = str(request.url.path)
    if das.is_write_blocked(request.method, path):
        das.log_event(db, das.Events.WRITE_BLOCKED, admin_id=user.id, admin_role="HEAD_OFFICE", request=request,
                      resource=das.resource_for_path(path), detail=f"branch_company_id={branch_company_id}")
        await db.commit()
        raise das._forbidden("DELEGATION_READ_ONLY", "Read-only view: changes are not allowed while viewing a branch.")

    branch_user = await branch_main_user(db, branch_company_id)
    if branch_user is None:
        raise das._forbidden("DELEGATION_ENDED", "This branch has no active account.")

    das.log_event(db, "BRANCH_VIEWED", admin_id=user.id, admin_role="HEAD_OFFICE", client_user_id=branch_user.id,
                  request=request, resource=das.resource_for_path(path), detail=f"branch_company_id={branch_company_id}")
    await db.commit()
    request.state.delegation = {"kind": "branch", "hq_user_id": user.id, "branch_company_id": branch_company_id,
                                "client_user_id": branch_user.id}
    return branch_user


async def list_organisations(db: AsyncSession, admin: User, q: Optional[str] = None) -> list:
    """Super Admin: head offices (or any company matching q) with limits and usage."""
    await ensure_tables(db)
    if not das.is_super_admin(admin):
        raise _err("SUPER_ADMIN_ONLY", "Super Admin access required.", status.HTTP_403_FORBIDDEN)
    stmt = select(Company, CompanyOrgSettings).outerjoin(CompanyOrgSettings, CompanyOrgSettings.company_id == Company.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Company.gstin.ilike(like), Company.company_name.ilike(like)))
    else:
        stmt = stmt.where(CompanyOrgSettings.is_headquarters == True)  # noqa: E712
    rows = (await db.execute(stmt.order_by(Company.company_name.asc()).limit(100))).all()
    ids = [c.id for c, _ in rows]
    counts = {}
    if ids:
        for hq_id, st, n in (await db.execute(
            select(CompanyBranchLink.hq_company_id, CompanyBranchLink.status, func.count(CompanyBranchLink.id))
            .where(CompanyBranchLink.hq_company_id.in_(ids), CompanyBranchLink.status.in_(ACTIVE_LINK))
            .group_by(CompanyBranchLink.hq_company_id, CompanyBranchLink.status)
        )).all():
            counts.setdefault(hq_id, {})[st] = n
    return [{
        "company_id": c.id, "company_name": c.company_name, "gstin": c.gstin,
        "is_headquarters": bool(s and s.is_headquarters), "branch_limit": (s.branch_limit if s else 0) or 0,
        "approved_count": counts.get(c.id, {}).get(LinkStatus.APPROVED, 0),
        "pending_count": counts.get(c.id, {}).get(LinkStatus.PENDING, 0),
    } for c, s in rows]
