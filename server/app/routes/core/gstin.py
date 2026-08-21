"""
GSTIN credibility check and report request endpoints.
"""
from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text
from datetime import datetime, timezone
from app.database import get_db, engine
from app.models import User, PurchaseOrder, DefaulterCase, CreditReport, Settlement, Company, BusinessRequest, CompanyCredibilityIndex
from app.models.credibility_index import GlobalCredibilityIndex, CredibilityStatus, AICreditRiskVerdict
from app.schemas import (
    UpdateProfileRequest, UserProfileResponse, SubscriptionResponse, POApprovalRequest,
    GSTINCheckRequest, GSTINCheckResponse, BusinessRequestSchema, BusinessReportSubmit, BusinessRequestCreate,
    PurchaseOrderRequest, PurchaseOrderUpdate, GenericReasonRequest, ArchiveRequest, ReminderRequest,
    AdminSettingsRequest, OTPVerifyRequest, PhoneChangeRequest, EmailChangeRequest,
    DefaulterCaseRequest, DefaulterCaseUpdate, DefaulterVerifyRequest,
    CreditReportRequest, CreditReportResponse, CreditReportUpdate, CreditReportCompleteRequest,
    SettlementRequest, SettlementResponse, SettlementUpdate, ChatRequest
)
from app.utils import ResponseFormatter, format_phone_e164
from app.dependencies import get_current_user, require_role, require_master_admin, is_developer
from app.models import UserRole
import uuid
from app.utils.audit import log_audit

from .common import *  # noqa: F401,F403 (logger + shared constants)

gstin_router = APIRouter()

@gstin_router.post("/check", response_model=dict)
async def check_gstin_credibility(
    req: GSTINCheckRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Basic GSTIN credibility check"""
    # 1. Try to find company and its credibility index
    stmt = select(Company).where(Company.gstin == req.gstin)
    res = await db.execute(stmt)
    company = res.scalars().first()
    
    if not company:
        # If company not found, return default "Active" but low score or just "New"
        return ResponseFormatter.create_success(data={
            "status": "Active (New)",
            "credibility_score": 50,
            "risk_level": "Medium"
        })
        
    idx_stmt = select(CompanyCredibilityIndex).where(CompanyCredibilityIndex.company_id == company.id)
    idx_res = await db.execute(idx_stmt)
    idx = idx_res.scalars().first()
    
    if not idx:
        await log_audit(db, current_user, "GSTIN_CHECK", reason=f"GSTIN check for {req.gstin} (No index found)")
        return ResponseFormatter.create_success(data={
            "status": "Active",
            "credibility_score": 60,
            "risk_level": "Medium"
        })
        
    await log_audit(
        db=db,
        user=current_user,
        action="GSTIN_CHECK",
        reason=f"GSTIN check for {req.gstin} (Score: {idx.score})"
    )
    return ResponseFormatter.create_success(data={
        "status": "Defaulter" if idx.risk_level == "Critical" else "Active",
        "credibility_score": idx.score,
        "risk_level": idx.risk_level
    })


@gstin_router.post("/request-report", response_model=dict)
async def request_full_report(
    req: BusinessRequestCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Request a full business analysis report"""
    business_req = BusinessRequest(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        company_name=req.company_name,
        gstin=req.gstin,
        status="PENDING"
    )
    db.add(business_req)
    
    # Integration with NEW WORKFLOW SYSTEM
    try:
        from app.services.workflow_service import WorkflowService
        await WorkflowService.process_gstin_report_workflow(
            db=db,
            user_email=current_user.email,
            gstin=req.gstin
        )
    except Exception as workflow_err:
        logger.error(f"Failed to trigger GSTIN workflow: {workflow_err}")

    await log_audit(
        db=db, 
        user=current_user, 
        action="GSTIN_REPORT_REQUESTED", 
        entity_obj=business_req,
        reason=f"Report requested for {req.company_name} ({req.gstin})"
    )
    await db.commit()
    
    return ResponseFormatter.create_success(
        data={"request_id": business_req.id},
        message="Full report request submitted and assigned to LEGAL team"
    )


@gstin_router.get("/requests", response_model=dict)
async def list_report_requests(
    current_user: Annotated[User, Depends(require_role([UserRole.LEGAL, UserRole.MASTER_ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List report requests for LEGAL team"""
    stmt = select(BusinessRequest).order_by(BusinessRequest.created_at.desc())
    res = await db.execute(stmt)
    requests = res.scalars().all()
    
    return ResponseFormatter.create_success(data=[BusinessRequestSchema.model_validate(r).__dict__ for r in requests])


@gstin_router.post("/report", response_model=dict)
async def submit_legal_report(
    req: BusinessReportSubmit,
    current_user: Annotated[User, Depends(require_role([UserRole.LEGAL, UserRole.MASTER_ADMIN]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Submit analysis report (LEGAL only)"""
    stmt = select(BusinessRequest).where(BusinessRequest.id == req.request_id)
    res = await db.execute(stmt)
    business_req = res.scalars().first()
    
    if not business_req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    business_req.risk_score = req.risk_score
    business_req.recommendation = req.recommendation
    business_req.legal_notes = req.legal_notes
    business_req.analyzed_by = current_user.id
    business_req.status = "COMPLETED"
    business_req.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # Also update the company's credibility
    comp_stmt = select(Company).where(Company.gstin == business_req.gstin)
    comp_res = await db.execute(comp_stmt)
    company = comp_res.scalars().first()
    
    if not company:
        company = Company(
            id=str(uuid.uuid4()),
            company_name=business_req.company_name,
            gstin=business_req.gstin,
            domain_name=f"{business_req.company_name.lower().replace(' ', '')}.com",
            is_verified=True
        )
        db.add(company)
        await db.flush()

        # Auto-add to Global Credibility Index
        gci_entry = GlobalCredibilityIndex(
            id=str(uuid.uuid4()),
            company_id=company.id,
            company_name=company.company_name,
            company_registration_no=None,
            partner_trust_score=0.0,
            ai_credit_risk_verdict=AICreditRiskVerdict.NOT_RATED,
            credibility_status=CredibilityStatus.STANDARD,
            approved_by_master_admin_id=None,
            credibility_review_id=None,
        )
        db.add(gci_entry)
        
    idx_stmt = select(CompanyCredibilityIndex).where(CompanyCredibilityIndex.company_id == company.id)
    idx_res = await db.execute(idx_stmt)
    idx = idx_res.scalars().first()
    
    if not idx:
        idx = CompanyCredibilityIndex(
            id=str(uuid.uuid4()),
            company_id=company.id
        )
        db.add(idx)
        
    idx.score = req.risk_score
    # Simple mapping from score to risk level
    if req.risk_score >= 80:
        idx.risk_level = "Low"
        idx.grade = "A"
    elif req.risk_score >= 50:
        idx.risk_level = "Medium"
        idx.grade = "B"
    else:
        idx.risk_level = "High"
        idx.grade = "C"
    idx.last_calculated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    await log_audit(
        db=db,
        user=current_user,
        action="GSTIN_REPORT_SUBMITTED",
        entity_obj=business_req,
        reason=f"Risk Score: {req.risk_score}, Rec: {req.recommendation}"
    )
    
    # Audit log for company index update
    await log_audit(
        db=db,
        user=current_user,
        action="COMPANY_INDEX_UPDATED",
        entity_obj=idx,
        reason=f"Index updated for {company.company_name} after legal report submission. New Score: {req.risk_score}"
    )
    await db.commit()
    
    return ResponseFormatter.create_success(message="Analysis report submitted successfully")


