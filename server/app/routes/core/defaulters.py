"""
Defaulter case reporting endpoints.
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

defaulter_router = APIRouter()

def _validate_pan(pan: str) -> bool:
    """Validate PAN format: 5 letters, 4 digits, 1 letter"""
    return len(pan) == 10 and pan[:5].isalpha() and pan[5:9].isdigit() and pan[9].isalpha()


def _validate_gstin_pan(gstin: str, pan: str) -> bool:
    """Validate PAN format if provided. GSTIN and PAN are both optional."""
    if pan and not _validate_pan(pan):
        return False
    return True


def _apply_defaulter_updates(case: DefaulterCase, req: DefaulterCaseUpdate) -> None:
    """Apply field updates to defaulter case from request"""
    req_data = req.model_dump(exclude_unset=True)
    
    for field, value in req_data.items():
        if field in ("business_gstin", "pan"):
            value = value.upper().strip() if value else None
        setattr(case, field, value)


@defaulter_router.post("")
async def file_defaulter(req: DefaulterCaseRequest, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """File defaulter case - GSTIN or PAN required"""
    if not await AccessControlService.can_access_feature(current_user.id, REPORT_OVERDUE, db):
        raise UnauthorizedFeature(DEFAULTER_FEATURE_NAME)
    
    gstin = (req.business_gstin or "").strip().upper()
    pan = (req.pan or "").strip().upper()

    if pan and (len(pan) != 10 or not pan[:5].isalpha() or not pan[5:9].isdigit() or not pan[9].isalpha()):
        raise HTTPException(status_code=400, detail="Invalid PAN format")
    
    case = DefaulterCase(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        business_name=req.business_name,
        business_gstin=gstin if gstin else None,
        pan=pan if pan else None,
        invoice_number=req.invoice_number,
        amount=req.amount,
        due_date=req.due_date,
        approval_status="pending",
        notes=req.notes or "",
        documents_drive_folder=req.documents_drive_folder or "",
    )
    db.add(case)
    await log_audit(
        db=db,
        user=current_user,
        action="DEFAULTER_FILE",
        defaulter_case=case,
        reason=f"Defaulter case filed against {case.business_name}"
    )
    await db.commit()
    return ResponseFormatter.create_success(data={"id": case.id}, message="Defaulter case filed")


@defaulter_router.get("")
async def list_defaulters(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """List user's defaulter cases"""
    stmt = select(DefaulterCase).where(
        DefaulterCase.user_id == current_user.id
    ).order_by(DefaulterCase.created_at.desc())
    result = await db.execute(stmt)
    cases = result.scalars().all()
    
    data = [{
        "id": c.id,
        "business_name": c.business_name,
        "business_gstin": c.business_gstin,
        "pan": c.pan,
        "invoice_number": c.invoice_number,
        "amount": c.amount,
        "due_date": c.due_date.isoformat() if c.due_date else None,
        "approval_status": c.approval_status,
        "notes": c.notes,
        "documents_drive_folder": c.documents_drive_folder,
        "ledger_url": c.ledger_url,
        "ca_certificate_url": c.ca_certificate_url,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "verified_by": c.verified_by,
        "verification_date": c.verification_date.isoformat() if c.verification_date else None,
    } for c in cases]
    
    return ResponseFormatter.create_success(data=data)


@defaulter_router.get("/{case_id}")
async def get_defaulter(case_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Get single defaulter case details"""
    stmt = select(DefaulterCase).where(DefaulterCase.id == case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    
    if not case:
        raise HTTPException(status_code=404, detail="Defaulter case not found")
    
    if case.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)
    
    return ResponseFormatter.create_success(data={
        "id": case.id,
        "business_name": case.business_name,
        "business_gstin": case.business_gstin,
        "pan": case.pan,
        "invoice_number": case.invoice_number,
        "amount": case.amount,
        "due_date": case.due_date.isoformat() if case.due_date else None,
        "approval_status": case.approval_status,
        "notes": case.notes,
        "documents_drive_folder": case.documents_drive_folder,
        "ledger_url": case.ledger_url,
        "ca_certificate_url": case.ca_certificate_url,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        "verified_by": case.verified_by,
        "verification_date": case.verification_date.isoformat() if case.verification_date else None,
    })


@defaulter_router.put("/{case_id}")
async def update_defaulter(case_id: str, req: DefaulterCaseUpdate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Update defaulter case (only if pending)"""
    if not await AccessControlService.can_access_feature(current_user.id, REPORT_OVERDUE, db):
        raise UnauthorizedFeature(DEFAULTER_FEATURE_NAME)
    
    stmt = select(DefaulterCase).where(DefaulterCase.id == case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    
    if not case:
        raise HTTPException(status_code=404, detail=f"Defaulter case {NOT_FOUND_ERROR}")
    
    if case.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)
    
    if case.approval_status != "pending":
        raise HTTPException(status_code=400, detail=CANNOT_UPDATE_REVIEWED)
    
    # Validate GSTIN or PAN
    gstin = req.business_gstin.strip().upper() if req.business_gstin else case.business_gstin
    pan = req.pan.strip().upper() if req.pan else case.pan
    
    if not _validate_gstin_pan(gstin, pan):
        raise HTTPException(status_code=400, detail=INVALID_PAN_FORMAT)
    
    _apply_defaulter_updates(case, req)
    case.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await log_audit(
        db=db,
        user=current_user,
        action="DEFAULTER_UPDATE",
        defaulter_case=case,
        reason=f"Defaulter case updated",
        new_data=req.model_dump(exclude_unset=True)
    )
    await db.commit()
    
    return ResponseFormatter.create_success(message="Defaulter case updated")


@defaulter_router.delete("/{case_id}")
async def delete_defaulter(case_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Delete defaulter case (only if pending)"""
    if not await AccessControlService.can_access_feature(current_user.id, REPORT_OVERDUE, db):
        raise UnauthorizedFeature(DEFAULTER_FEATURE_NAME)
    
    stmt = select(DefaulterCase).where(DefaulterCase.id == case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    
    if not case:
        raise HTTPException(status_code=404, detail=f"Defaulter case {NOT_FOUND_ERROR}")
    
    if case.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)
    
    # Only allow deletion of pending cases
    if case.approval_status != "pending":
        raise HTTPException(status_code=400, detail="Cannot delete case that has been reviewed")
    
    await log_audit(
        db=db,
        user=current_user,
        action="DEFAULTER_DELETE",
        defaulter_case=case,
        reason=f"Defaulter case deleted"
    )
    await db.delete(case)
    await db.commit()
    
    return ResponseFormatter.create_success(message="Defaulter case deleted")


@defaulter_router.post("/{case_id}/upload-document")
async def upload_defaulter_document(
    case_id: str,
    req: DefaulterCaseUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Upload document links (Drive folder / ledger / CA certificate)"""
    stmt = select(DefaulterCase).where(DefaulterCase.id == case_id)
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    
    if not case:
        raise HTTPException(status_code=404, detail="Defaulter case not found")
    
    if case.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)
    
    if req.documents_drive_folder is not None:
        case.documents_drive_folder = req.documents_drive_folder
    if req.ledger_url is not None:
        case.ledger_url = req.ledger_url
    if req.ca_certificate_url is not None:
        case.ca_certificate_url = req.ca_certificate_url
    
    case.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await log_audit(
        db=db,
        user=current_user,
        action="DEFAULTER_DOC_UPLOAD",
        defaulter_case=case,
        reason="Uploaded defaulter documents",
        new_data=req.model_dump(exclude_unset=True)
    )
    await db.commit()
    
    return ResponseFormatter.create_success(message="Document links updated")


