"""
Head office / branch organisations — API endpoints.

Company side (/api/v1/organization):  status, become a head office, request
to join a head office, approve/reject/remove branches, combined totals,
banner info for viewing a branch.
Super Admin (/api/v1/admin/organizations): list head offices, set branch limits.

Viewing a branch's data reuses every existing endpoint via the
X-Branch-View header (see get_current_user / organization_service).
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.services import organization_service as org
from app.utils import ResponseFormatter

router = APIRouter(prefix="/organization", tags=["Organisation (head office / branches)"])
admin_router = APIRouter(prefix="/admin/organizations", tags=["Organisation (Super Admin)"])

CurrentUser = Annotated[User, Depends(get_current_user)]
Db = Annotated[AsyncSession, Depends(get_db)]


class BranchRequestBody(BaseModel):
    hq_gstin: str = Field(..., min_length=15, max_length=15)
    branch_name: str = Field(..., min_length=2, max_length=120)


class BranchLimitBody(BaseModel):
    branch_limit: int = Field(..., ge=0, le=500)


def _rid(request: Request) -> str:
    return getattr(getattr(request, "state", None), "request_id", "") or ""


def _require_admin(user: User):
    if not org.is_org_admin(user):
        raise org._err("NOT_ALLOWED", "Only your company admin can change organisation settings.", 403)


@router.get("")
async def my_organisation(request: Request, current_user: CurrentUser, db: Db):
    return ResponseFormatter.create_success(data=await org.org_status(db, current_user), request_id=_rid(request))


@router.post("/head-office")
async def become_head_office(request: Request, current_user: CurrentUser, db: Db):
    _require_admin(current_user)
    await org.mark_head_office(db, current_user.company_id)
    return ResponseFormatter.create_success(
        data=await org.org_status(db, current_user),
        message="Your company is now a head office. Contact CreditDataWatch to set how many branches you can add.",
        request_id=_rid(request),
    )


@router.post("/branch-request")
async def request_to_join(body: BranchRequestBody, request: Request, current_user: CurrentUser, db: Db):
    await org.request_branch(db, current_user, body.hq_gstin, body.branch_name)
    return ResponseFormatter.create_success(
        data=await org.org_status(db, current_user),
        message="Request sent. The head office must approve it.",
        request_id=_rid(request),
    )


@router.post("/branch-request/cancel")
async def cancel_my_request(request: Request, current_user: CurrentUser, db: Db):
    await org.cancel_request(db, current_user)
    return ResponseFormatter.create_success(data=await org.org_status(db, current_user), request_id=_rid(request))


@router.post("/branches/{link_id}/approve")
async def approve_branch(link_id: str, request: Request, current_user: CurrentUser, db: Db):
    await org.decide(db, current_user, link_id, approve=True)
    return ResponseFormatter.create_success(message="Branch approved", request_id=_rid(request))


@router.post("/branches/{link_id}/reject")
async def reject_branch(link_id: str, request: Request, current_user: CurrentUser, db: Db):
    await org.decide(db, current_user, link_id, approve=False)
    return ResponseFormatter.create_success(message="Request rejected", request_id=_rid(request))


@router.post("/branches/{link_id}/remove")
async def remove_branch(link_id: str, request: Request, current_user: CurrentUser, db: Db):
    await org.remove_branch(db, current_user, link_id)
    return ResponseFormatter.create_success(message="Branch removed", request_id=_rid(request))


@router.get("/summary")
async def head_office_summary(request: Request, current_user: CurrentUser, db: Db):
    return ResponseFormatter.create_success(data=await org.summary(db, current_user), request_id=_rid(request))


@router.get("/branches/{branch_company_id}/session")
async def branch_view_session(branch_company_id: str, request: Request, current_user: CurrentUser, db: Db):
    return ResponseFormatter.create_success(
        data=await org.branch_session(db, current_user, branch_company_id), request_id=_rid(request),
    )


# ------------------------------------------------------------ Super Admin

@admin_router.get("")
async def list_organisations(
    request: Request, current_user: CurrentUser, db: Db,
    q: Annotated[Optional[str], Query(max_length=100)] = None,
):
    items = await org.list_organisations(db, current_user, q)
    return ResponseFormatter.create_success(data={"items": items}, request_id=_rid(request))


@admin_router.put("/{company_id}/branch-limit")
async def set_limit(company_id: str, body: BranchLimitBody, request: Request, current_user: CurrentUser, db: Db):
    row = await org.set_branch_limit(db, current_user, company_id, body.branch_limit)
    return ResponseFormatter.create_success(
        data={"company_id": company_id, "branch_limit": row.branch_limit},
        message="Branch limit updated", request_id=_rid(request),
    )
