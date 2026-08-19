"""
Settlement request endpoints.
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

settlement_router = APIRouter()

@settlement_router.post("")
async def create_settlement(req: SettlementRequest, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Create settlement record"""
    if not await AccessControlService.can_access_feature(current_user.id, "SETTLEMENT", db):
        raise UnauthorizedFeature("Settlement")
    settlement = Settlement(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        case_reference=req.case_reference,
        status="Open",
        notes=req.notes,
    )
    db.add(settlement)
    await log_audit(
        db=db,
        user=current_user,
        action="SETTLEMENT_CREATE",
        settlement=settlement,
        reason=f"Settlement created for {req.case_reference}"
    )
    await db.commit()
    return ResponseFormatter.create_success(data={"id": settlement.id}, message="Settlement created")


@settlement_router.get("")
async def list_settlements(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """List settlements"""
    stmt = select(Settlement).where(Settlement.user_id == current_user.id).order_by(Settlement.created_at.desc())
    result = await db.execute(stmt)
    settlements = result.scalars().all()
    return ResponseFormatter.create_success(data=[{
        "id": s.id,
        "case_reference": s.case_reference,
        "status": s.status,
        "notes": s.notes,
        "documents_drive_folder": s.documents_drive_folder,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    } for s in settlements])


@settlement_router.get("/{settlement_id}")
async def get_settlement(settlement_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Get settlement details"""
    stmt = select(Settlement).where(Settlement.id == settlement_id)
    result = await db.execute(stmt)
    settlement = result.scalar_one_or_none()
    
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    
    if settlement.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)
    
    return ResponseFormatter.create_success(data={
        "id": settlement.id,
        "case_reference": settlement.case_reference,
        "status": settlement.status,
        "notes": settlement.notes,
        "documents_drive_folder": settlement.documents_drive_folder,
        "created_at": settlement.created_at.isoformat() if settlement.created_at else None,
        "updated_at": settlement.updated_at.isoformat() if settlement.updated_at else None,
    })


@settlement_router.put("/{settlement_id}")
async def update_settlement(settlement_id: str, req: SettlementUpdate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Update settlement"""
    stmt = select(Settlement).where(Settlement.id == settlement_id)
    result = await db.execute(stmt)
    settlement = result.scalar_one_or_none()
    
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    
    if settlement.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)
    
    if req.case_reference is not None:
        settlement.case_reference = req.case_reference
    if req.status is not None:
        settlement.status = req.status
    if req.notes is not None:
        settlement.notes = req.notes
    if req.documents_drive_folder is not None:
        settlement.documents_drive_folder = req.documents_drive_folder
    
    settlement.updated_at = datetime.now(timezone.utc)
    await log_audit(
        db=db,
        user=current_user,
        action="SETTLEMENT_UPDATE",
        settlement=settlement,
        reason="Settlement updated",
        new_data=req.model_dump(exclude_unset=True)
    )
    await db.commit()
    
    return ResponseFormatter.create_success(message="Settlement updated")


