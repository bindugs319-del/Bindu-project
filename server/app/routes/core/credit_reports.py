"""
Credit report request endpoints.
"""
from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text
from datetime import datetime, timezone
from app.database import get_db, engine
from app.models import User, PurchaseOrder, DefaulterCase, CreditReport, Settlement, Company, BusinessRequest, CompanyCredibilityIndex
from app.schemas import (
    UpdateProfileRequest, UserProfileResponse, SubscriptionResponse, POApprovalRequest,
    GSTINCheckRequest, GSTINCheckResponse, BusinessRequestSchema, BusinessReportSubmit, BusinessRequestCreate,
    PurchaseOrderRequest, PurchaseOrderUpdate, GenericReasonRequest, ArchiveRequest, ReminderRequest,
    AdminSettingsRequest, OTPVerifyRequest, PhoneChangeRequest, EmailChangeRequest,
    DefaulterCaseRequest, DefaulterCaseUpdate, DefaulterVerifyRequest,
    CreditReportRequest, CreditReportResponse, CreditReportUpdate, CreditReportCompleteRequest,
    SettlementRequest, SettlementResponse, SettlementUpdate, ChatRequest
)
from app.services import UserService, OTPService, AccessControlService
from app.utils import ResponseFormatter, format_phone_e164
from app.dependencies import get_current_user, require_role, require_master_admin, is_developer
from app.exceptions import UnauthorizedFeature
import uuid
from app.utils.audit import log_audit

from .common import *  # noqa: F401,F403 (logger + shared constants)

credit_router = APIRouter()

@credit_router.post("")
async def request_credit_report(req: CreditReportRequest, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Request credit report"""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_REPORTS", db):
        raise UnauthorizedFeature("Credit Reports")
    report = CreditReport(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        entity_name=req.entity_name,
        entity_gstin=req.entity_gstin.upper() if req.entity_gstin else None,
        status="Requested",
    )
    db.add(report)
    await log_audit(
        db=db,
        user=current_user,
        action="CREDIT_REPORT_REQUEST",
        credit_report=report,
        reason=f"Credit report requested for {report.entity_name}"
    )
    await db.commit()
    return ResponseFormatter.create_success(data={"id": report.id}, message="Report requested")


@credit_router.get("")
async def list_credit_reports(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """List credit reports"""
    stmt = select(CreditReport).where(CreditReport.user_id == current_user.id).order_by(CreditReport.created_at.desc())
    result = await db.execute(stmt)
    reports = result.scalars().all()
    return ResponseFormatter.create_success(data=[{
        "id": r.id,
        "entity_name": r.entity_name,
        "entity_gstin": r.entity_gstin,
        "credit_score": r.credit_score,
        "status": r.status,
        "report_url": r.report_url,
        "last_updated": r.last_updated.isoformat() if r.last_updated else None,
        "requested_at": r.requested_at.isoformat() if r.requested_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in reports])


@credit_router.get("/{report_id}")
async def get_credit_report(report_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Get credit report details"""
    stmt = select(CreditReport).where(CreditReport.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Credit report not found")
    
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)
    
    return ResponseFormatter.create_success(data={
        "id": report.id,
        "entity_name": report.entity_name,
        "entity_gstin": report.entity_gstin,
        "credit_score": report.credit_score,
        "status": report.status,
        "report_url": report.report_url,
        "last_updated": report.last_updated.isoformat() if report.last_updated else None,
        "requested_at": report.requested_at.isoformat() if report.requested_at else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    })


@credit_router.put("/{report_id}")
async def update_credit_report(report_id: str, req: CreditReportUpdate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Update credit report (admin upload results)"""
    stmt = select(CreditReport).where(CreditReport.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Credit report not found")
    
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)
    
    if req.credit_score is not None:
        report.credit_score = req.credit_score
    if req.status is not None:
        report.status = req.status
    if req.report_url is not None:
        report.report_url = req.report_url
    if req.last_updated is not None:
        report.last_updated = req.last_updated
    
    report.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await log_audit(
        db=db,
        user=current_user,
        action="CREDIT_REPORT_UPDATE",
        credit_report=report,
        reason="Credit report updated",
        new_data=req.model_dump(exclude_unset=True)
    )
    await db.commit()
    
    return ResponseFormatter.create_success(message="Credit report updated")


