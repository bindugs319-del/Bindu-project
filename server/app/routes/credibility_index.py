"""
New API endpoints for Global Credibility Index Auto-Addition Feature
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
import uuid

from app.database import get_db
from app.dependencies import get_current_user, require_role, require_master_admin
from app.models import (
    User,
    UserRole,
    BusinessRequest,
    CredibilityReview,
    CredibilityReviewStage,
    GlobalCredibilityIndex,
    CredibilityReviewStatus,
    CredibilityReviewStage as ReviewStageEnum,
    ReviewDecision,
    Notification,
    Company,
    CompanyRatingRequest,
    AICreditRiskVerdict,
    CredibilityStatus
)
from app.schemas import credibility_index as cred_schemas
from app.services.notification_service import NotificationService
from app.utils.role_settings import is_legal_enabled, is_financial_enabled

router = APIRouter(prefix="/api/v1/credibility-index", tags=["Credibility Index"])


@router.post("/initiate")
async def initiate_credibility_review(
    payload: cred_schemas.CredibilityReviewInitiate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate credibility review when user submits safety request"""
    # Check if business request exists
    result = await db.execute(select(BusinessRequest).where(BusinessRequest.id == payload.business_request_id))
    business_request = result.scalar_one_or_none()
    if not business_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business request not found"
        )

    # Check if review already exists
    existing_result = await db.execute(
        select(CredibilityReview).where(CredibilityReview.business_request_id == payload.business_request_id)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credibility review already exists for this request"
        )

    # Check role settings
    financial_enabled = await is_financial_enabled(db)
    legal_enabled = await is_legal_enabled(db)

    # Determine initial status
    if not financial_enabled:
        # Skip Financial, go to Legal if enabled, else skip to Operations
        if not legal_enabled:
            initial_status = CredibilityReviewStatus.PENDING_OPERATIONS
            await NotificationService.send_to_role(
                db=db,
                role="OPERATIONS",
                title="New Credibility Review",
                message=f"Company {business_request.company_name} is pending your review in the credibility index process (Financial & Legal roles disabled).",
                action_url="/dashboard/admin"
            )
        else:
            initial_status = CredibilityReviewStatus.PENDING_LEGAL
            await NotificationService.send_to_role(
                db=db,
                role="LEGAL",
                title="New Credibility Review",
                message=f"Company {business_request.company_name} is pending your review in the credibility index process (Financial role disabled).",
                action_url="/dashboard/legal"
            )
    else:
        initial_status = CredibilityReviewStatus.PENDING_FINANCIAL
        await NotificationService.send_to_role(
            db=db,
            role="FINANCIAL",
            title="New Credibility Review",
            message=f"Company {business_request.company_name} is pending your review in the credibility index process.",
            action_url="/dashboard/financial"
        )

    # Create review
    review = CredibilityReview(
        id=str(uuid.uuid4()),
        business_request_id=payload.business_request_id,
        company_name=business_request.company_name,
        company_registration_no=payload.company_registration_no or None,
        submitted_by_user_id=current_user.id,
        status=initial_status
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    return {"message": "Credibility review initiated successfully", "review_id": review.id}


@router.get("/pending/financial", response_model=list[cred_schemas.CredibilityReviewOut])
async def get_pending_financial_reviews(
    current_user: User = Depends(require_role([UserRole.FINANCIAL])),
    db: AsyncSession = Depends(get_db)
):
    """Get all reviews pending financial team review"""
    result = await db.execute(
        select(CredibilityReview)
        .where(CredibilityReview.status == CredibilityReviewStatus.PENDING_FINANCIAL)
        .order_by(CredibilityReview.created_at.desc())
    )
    reviews = result.scalars().all()
    return reviews


@router.post("/review/financial/{review_id}")
async def submit_financial_review(
    review_id: str,
    payload: cred_schemas.FinancialReviewSubmit,
    current_user: User = Depends(require_role([UserRole.FINANCIAL])),
    db: AsyncSession = Depends(get_db)
):
    """Financial team submits review"""
    # Get review
    result = await db.execute(select(CredibilityReview).where(CredibilityReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    # Create stage entry
    stage = CredibilityReviewStage(
        id=str(uuid.uuid4()),
        credibility_review_id=review_id,
        stage=ReviewStageEnum.FINANCIAL,
        reviewed_by_user_id=current_user.id,
        decision=ReviewDecision.APPROVED if payload.approve else ReviewDecision.REJECTED,
        financial_health_score=payload.financial_health_score,
        payment_history=payload.payment_history,
        financial_risk_level=payload.financial_risk_level,
        notes=payload.notes,
        reviewed_at=datetime.utcnow()
    )
    db.add(stage)

    # Update status
    if payload.approve:
        # Check if Legal is enabled
        legal_enabled = await is_legal_enabled(db)
        if legal_enabled:
            review.status = CredibilityReviewStatus.PENDING_LEGAL
            await NotificationService.send_to_role(
                db=db,
                role="LEGAL",
                title="New Credibility Review",
                message=f"Company {review.company_name} is pending your review in the credibility index process.",
                action_url="/dashboard/legal"
            )
        else:
            review.status = CredibilityReviewStatus.PENDING_OPERATIONS
            await NotificationService.send_to_role(
                db=db,
                role="OPERATIONS",
                title="New Credibility Review",
                message=f"Company {review.company_name} is pending your review in the credibility index process (Legal role disabled).",
                action_url="/dashboard/admin"
            )
    else:
        review.status = CredibilityReviewStatus.REJECTED_FINANCIAL
        # Notify master admin
        await NotificationService.send_to_role(
            db=db,
            role="MASTER_ADMIN",
            title="Credibility Review Rejected",
            message=f"Credibility review for {review.company_name} was rejected by Financial team.",
            action_url="/dashboard/master-admin"
        )

    await db.commit()
    await db.refresh(review)
    return {"message": "Review submitted successfully", "review": cred_schemas.CredibilityReviewOut.model_validate(review)}


@router.get("/pending/legal", response_model=list[cred_schemas.CredibilityReviewWithStagesOut])
async def get_pending_legal_reviews(
    current_user: User = Depends(require_role([UserRole.LEGAL])),
    db: AsyncSession = Depends(get_db)
):
    """Get all reviews pending legal team review with previous stage data"""
    result = await db.execute(
        select(CredibilityReview)
        .options(selectinload(CredibilityReview.stages))
        .where(CredibilityReview.status == CredibilityReviewStatus.PENDING_LEGAL)
        .order_by(CredibilityReview.created_at.desc())
    )
    reviews = result.scalars().all()
    return reviews


@router.post("/review/legal/{review_id}")
async def submit_legal_review(
    review_id: str,
    payload: cred_schemas.LegalReviewSubmit,
    current_user: User = Depends(require_role([UserRole.LEGAL])),
    db: AsyncSession = Depends(get_db)
):
    """Legal team submits review"""
    result = await db.execute(select(CredibilityReview).where(CredibilityReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    stage = CredibilityReviewStage(
        id=str(uuid.uuid4()),
        credibility_review_id=review_id,
        stage=ReviewStageEnum.LEGAL,
        reviewed_by_user_id=current_user.id,
        decision=ReviewDecision.APPROVED if payload.approve else ReviewDecision.REJECTED,
        legal_status=payload.legal_status,
        compliance_score=payload.compliance_score,
        court_cases=payload.court_cases,
        notes=payload.notes,
        reviewed_at=datetime.utcnow()
    )
    db.add(stage)

    if payload.approve:
        review.status = CredibilityReviewStatus.PENDING_OPERATIONS
        await NotificationService.send_to_role(
            db=db,
            role="OPERATIONS",
            title="New Credibility Review",
            message=f"Company {review.company_name} is pending your review in the credibility index process.",
            action_url="/dashboard/operations"
        )
    else:
        review.status = CredibilityReviewStatus.REJECTED_LEGAL
        await NotificationService.send_to_role(
            db=db,
            role="MASTER_ADMIN",
            title="Credibility Review Rejected",
            message=f"Credibility review for {review.company_name} was rejected by Legal team.",
            action_url="/dashboard/master-admin"
        )

    await db.commit()
    await db.refresh(review)
    return {"message": "Review submitted successfully"}


@router.get("/pending/operations", response_model=list[cred_schemas.CredibilityReviewWithStagesOut])
async def get_pending_ops_reviews(
    current_user: User = Depends(require_role([UserRole.OPERATION, "OPERATIONS"])),
    db: AsyncSession = Depends(get_db)
):
    """Get all reviews pending operations team review with all stages data"""
    result = await db.execute(
        select(CredibilityReview)
        .options(selectinload(CredibilityReview.stages))
        .where(CredibilityReview.status == CredibilityReviewStatus.PENDING_OPERATIONS)
        .order_by(CredibilityReview.created_at.desc())
    )
    reviews = result.scalars().all()
    return reviews


@router.post("/review/operations/{review_id}")
async def submit_ops_review(
    review_id: str,
    payload: cred_schemas.OperationsReviewSubmit,
    current_user: User = Depends(require_role([UserRole.OPERATION, "OPERATIONS"])),
    db: AsyncSession = Depends(get_db)
):
    """Operations team submits review"""
    result = await db.execute(select(CredibilityReview).where(CredibilityReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    stage = CredibilityReviewStage(
        id=str(uuid.uuid4()),
        credibility_review_id=review_id,
        stage=ReviewStageEnum.OPERATIONS,
        reviewed_by_user_id=current_user.id,
        decision=ReviewDecision.APPROVED if payload.approve else ReviewDecision.REJECTED,
        operational_reliability=payload.operational_reliability,
        dispute_history=payload.dispute_history,
        partner_trust_score=payload.partner_trust_score,
        ai_credit_risk_verdict=payload.ai_credit_risk_verdict,
        notes=payload.notes,
        reviewed_at=datetime.utcnow()
    )
    db.add(stage)

    if payload.approve:
        review.status = CredibilityReviewStatus.PENDING_MASTER_ADMIN
        await NotificationService.send_to_role(
            db=db,
            role="MASTER_ADMIN",
            title="Credibility Review for Final Approval",
            message=f"Company {review.company_name} is pending your final approval in the credibility index process.",
            action_url="/dashboard/master-admin"
        )
    else:
        review.status = CredibilityReviewStatus.REJECTED_OPERATIONS
        await NotificationService.send_to_role(
            db=db,
            role="MASTER_ADMIN",
            title="Credibility Review Rejected",
            message=f"Credibility review for {review.company_name} was rejected by Operations team.",
            action_url="/dashboard/master-admin"
        )

    await db.commit()
    await db.refresh(review)
    return {"message": "Review submitted successfully"}


@router.get("/pending/master-admin", response_model=list[cred_schemas.CredibilityReviewFullOut])
async def get_pending_master_admin_reviews(
    current_user: User = Depends(require_master_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all reviews pending master admin final approval with all stages data"""
    # Get reviews that are either pending master admin OR any rejected stage
    result = await db.execute(
        select(CredibilityReview)
        .options(selectinload(CredibilityReview.stages))
        .where(
            (CredibilityReview.status == CredibilityReviewStatus.PENDING_MASTER_ADMIN) |
            (CredibilityReview.status == CredibilityReviewStatus.REJECTED_FINANCIAL) |
            (CredibilityReview.status == CredibilityReviewStatus.REJECTED_LEGAL) |
            (CredibilityReview.status == CredibilityReviewStatus.REJECTED_OPERATIONS)
        )
        .order_by(CredibilityReview.created_at.desc())
    )
    reviews = result.scalars().all()
    return reviews


@router.post("/approve/master-admin/{review_id}")
async def submit_master_admin_decision(
    review_id: str,
    payload: cred_schemas.MasterAdminDecisionSubmit,
    current_user: User = Depends(require_master_admin),
    db: AsyncSession = Depends(get_db)
):
    """Master Admin submits final decision"""
    result = await db.execute(select(CredibilityReview).where(CredibilityReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    if payload.approve:
        # Create master admin stage entry
        master_stage = CredibilityReviewStage(
            id=str(uuid.uuid4()),
            credibility_review_id=review_id,
            stage=ReviewStageEnum.MASTER_ADMIN,
            reviewed_by_user_id=current_user.id,
            decision=ReviewDecision.APPROVED,
            partner_trust_score=payload.partner_trust_score,
            ai_credit_risk_verdict=payload.ai_credit_risk_verdict,
            notes=payload.notes,
            reviewed_at=datetime.utcnow()
        )
        db.add(master_stage)

        # Try to find existing company from business request's gstin
        company = None
        if review.business_request_id:
            business_req_result = await db.execute(
                select(BusinessRequest).where(BusinessRequest.id == review.business_request_id)
            )
            business_req = business_req_result.scalar_one_or_none()
            if business_req:
                company_result = await db.execute(
                    select(Company).where(Company.gstin == business_req.gstin)
                )
                company = company_result.scalar_one_or_none()

        # Try to find existing GCI entry (by company_id if we have it, or company name)
        gci_entry = None
        if company:
            gci_result = await db.execute(
                select(GlobalCredibilityIndex).where(GlobalCredibilityIndex.company_id == company.id)
            )
            gci_entry = gci_result.scalar_one_or_none()

        if not gci_entry:
            # Fallback: try to find by company name. Same duplicate-row
            # risk as fulfill_rating_request below — .first() instead of
            # .scalar_one_or_none(), since company_name has no unique
            # constraint and this app has pre-existing duplicate rows.
            gci_result = await db.execute(
                select(GlobalCredibilityIndex)
                .where(GlobalCredibilityIndex.company_name == review.company_name)
                .order_by(GlobalCredibilityIndex.approved_at.desc().nullslast())
            )
            gci_entry = gci_result.scalars().first()

        if gci_entry:
            # Update existing GCI entry
            gci_entry.company_registration_no = review.company_registration_no
            gci_entry.partner_trust_score = payload.partner_trust_score or 0
            gci_entry.ai_credit_risk_verdict = payload.ai_credit_risk_verdict
            gci_entry.credibility_status = payload.credibility_status
            gci_entry.approved_by_master_admin_id = current_user.id
            gci_entry.approved_at = datetime.utcnow()
            gci_entry.credibility_review_id = review.id
        else:
            # Create new GCI entry
            gci_entry = GlobalCredibilityIndex(
                id=str(uuid.uuid4()),
                company_id=company.id if company else None,
                company_name=review.company_name,
                company_registration_no=review.company_registration_no,
                partner_trust_score=payload.partner_trust_score or 0,
                ai_credit_risk_verdict=payload.ai_credit_risk_verdict,
                credibility_status=payload.credibility_status,
                approved_by_master_admin_id=current_user.id,
                approved_at=datetime.utcnow(),
                credibility_review_id=review.id
            )
            db.add(gci_entry)

        # Get previous stages to copy scores
        stages_result = await db.execute(
            select(CredibilityReviewStage)
            .where(CredibilityReviewStage.credibility_review_id == review.id)
        )
        stages = stages_result.scalars().all()
        for stage in stages:
            if stage.stage == ReviewStageEnum.FINANCIAL:
                gci_entry.financial_health_score = stage.financial_health_score
            if stage.stage == ReviewStageEnum.LEGAL:
                gci_entry.legal_status = stage.legal_status
            if stage.stage == ReviewStageEnum.OPERATIONS:
                gci_entry.operational_reliability = stage.operational_reliability

        review.status = CredibilityReviewStatus.APPROVED

        # Notify original user
        # Get the user who submitted the review
        user_result = await db.execute(select(User).where(User.id == review.submitted_by_user_id))
        submitter = user_result.scalar_one_or_none()
        if submitter and submitter.email:
            status_text = payload.credibility_status.value if hasattr(payload.credibility_status, 'value') else str(payload.credibility_status)
            await NotificationService.send(
                db=db,
                to_email=submitter.email,
                title="Company Added to Credibility Index",
                message=f"Your requested company {review.company_name} has been added to the Global Credibility Index with status {status_text}.",
                action_url="/credibility-index"
            )
    else:
        master_stage = CredibilityReviewStage(
            id=str(uuid.uuid4()),
            credibility_review_id=review_id,
            stage=ReviewStageEnum.MASTER_ADMIN,
            reviewed_by_user_id=current_user.id,
            decision=ReviewDecision.REJECTED,
            notes=payload.notes,
            reviewed_at=datetime.utcnow()
        )
        db.add(master_stage)
        review.status = CredibilityReviewStatus.REJECTED_FINAL

    await db.commit()
    await db.refresh(review)
    return {"message": "Decision submitted successfully"}


@router.get("/index", response_model=list[cred_schemas.GlobalCredibilityIndexOut])
async def get_global_credibility_index(
    db: AsyncSession = Depends(get_db)
):
    """Public endpoint to get all approved companies in Global Credibility Index"""
    result = await db.execute(
        select(GlobalCredibilityIndex)
        .order_by(GlobalCredibilityIndex.created_at.desc())
    )
    index_entries = result.scalars().all()
    return index_entries


@router.get("/status/{business_request_id}")
async def get_review_status(
    business_request_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Check status of credibility review for a business request"""
    result = await db.execute(
        select(CredibilityReview).where(CredibilityReview.business_request_id == business_request_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        return {"status": "not_initiated", "message": "No credibility review initiated yet"}
    return {
        "status": review.status.value if hasattr(review.status, "value") else str(review.status),
        "review_id": review.id
    }


@router.post("/rating-request")
async def request_company_rating(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lightweight "Request Company Rating" action from the Credibility
    Index pages — a user asks CreditDataWatch to add/rate a company not
    yet in the Network Trust Intelligence registry. Goes to Operations
    first to propose a rating, then to Master Admin for final approval —
    same pattern as PO/subscription/legal-notice approvals elsewhere.
    """
    company_name = (payload.get("company_name") or "").strip()
    if not company_name:
        raise HTTPException(status_code=400, detail="company_name is required")

    req = CompanyRatingRequest(
        id=str(uuid.uuid4()),
        requested_by_user_id=current_user.id,
        requested_by_email=current_user.email,
        company_name=company_name,
        status="PENDING",
    )
    db.add(req)
    await db.commit()

    try:
        await NotificationService.send_to_role(
            db=db,
            role="OPERATIONS",
            title="Company Rating Requested",
            message=f"{current_user.email} requested a credibility rating for '{company_name}', not yet in the Network Trust Intelligence registry. Please review and propose a rating.",
            ntype="INFO",
            action_url="/dashboard/operation",
        )
    except Exception as e:
        print(f"[RATING REQUEST] Failed to notify Operations: {e}")

    return {"message": "Rating Request Sent! Our team will update the registry within 24 hours.", "request_id": req.id}


@router.get("/rating-requests/pending-operations")
async def get_pending_rating_requests_for_operations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List rating requests waiting for Operations to propose a rating."""
    role_val = str(getattr(current_user.role, "value", current_user.role) or "").upper()
    if role_val not in ("OPERATIONS", "OPERATION", "MASTER_ADMIN"):
        raise HTTPException(status_code=403, detail="Operations access required")

    result = await db.execute(
        select(CompanyRatingRequest)
        .where(CompanyRatingRequest.status == "PENDING")
        .order_by(CompanyRatingRequest.created_at.desc())
    )
    reqs = result.scalars().all()
    return [
        {
            "id": r.id,
            "company_name": r.company_name,
            "requested_by_email": r.requested_by_email,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reqs
    ]


@router.post("/rating-requests/{request_id}/operations-propose")
async def operations_propose_rating(
    request_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Operations proposes a rating for a requested company. This does NOT
    write to GlobalCredibilityIndex yet — it just records the proposal and
    forwards it to Master Admin for final approval."""
    role_val = str(getattr(current_user.role, "value", current_user.role) or "").upper()
    if role_val not in ("OPERATIONS", "OPERATION", "MASTER_ADMIN"):
        raise HTTPException(status_code=403, detail="Operations access required")

    result = await db.execute(select(CompanyRatingRequest).where(CompanyRatingRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Rating request not found")
    if req.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Request is not pending Operations review (status: {req.status})")

    partner_trust_score = float(payload.get("partner_trust_score") or 0)
    verdict_raw = payload.get("ai_credit_risk_verdict") or "Not Rated"
    status_raw = payload.get("credibility_status") or "Standard"

    # Validate against the real enum values up front, even though we're
    # only storing strings at this stage — catches a typo now rather than
    # at Master Admin approval time.
    try:
        AICreditRiskVerdict(verdict_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid ai_credit_risk_verdict: {verdict_raw}")
    try:
        CredibilityStatus(status_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid credibility_status: {status_raw}")

    req.proposed_partner_trust_score = partner_trust_score
    req.proposed_ai_credit_risk_verdict = verdict_raw
    req.proposed_credibility_status = status_raw
    req.operations_reviewed_by = current_user.id
    req.operations_reviewed_at = datetime.utcnow()
    req.operations_notes = payload.get("notes") or ""
    req.status = "PENDING_MASTER_APPROVAL"
    await db.commit()

    try:
        await NotificationService.send_to_role(
            db=db,
            role="MASTER_ADMIN",
            title="Company Rating Ready for Approval",
            message=f"Operations proposed a rating for '{req.company_name}': {partner_trust_score}/5, {verdict_raw}. Please review and approve.",
            ntype="INFO",
            action_url="/dashboard/admin",
        )
    except Exception as e:
        print(f"[RATING REQUEST] Failed to notify Master Admin: {e}")

    return {"message": f"Proposal for '{req.company_name}' sent to Master Admin for approval."}


@router.get("/rating-requests/pending")
async def get_pending_rating_requests(
    current_user: User = Depends(require_master_admin),
    db: AsyncSession = Depends(get_db)
):
    """List rating requests Operations has proposed a rating for, waiting
    on Master Admin's final approval."""
    result = await db.execute(
        select(CompanyRatingRequest)
        .where(CompanyRatingRequest.status == "PENDING_MASTER_APPROVAL")
        .order_by(CompanyRatingRequest.operations_reviewed_at.desc())
    )
    reqs = result.scalars().all()
    return [
        {
            "id": r.id,
            "company_name": r.company_name,
            "requested_by_email": r.requested_by_email,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "proposed_partner_trust_score": r.proposed_partner_trust_score,
            "proposed_ai_credit_risk_verdict": r.proposed_ai_credit_risk_verdict,
            "proposed_credibility_status": r.proposed_credibility_status,
            "operations_notes": r.operations_notes,
            "operations_reviewed_at": r.operations_reviewed_at.isoformat() if r.operations_reviewed_at else None,
        }
        for r in reqs
    ]


@router.post("/rating-requests/{request_id}/fulfill")
async def fulfill_rating_request(
    request_id: str,
    payload: dict,
    current_user: User = Depends(require_master_admin),
    db: AsyncSession = Depends(get_db)
):
    """Master Admin approves Operations' proposed rating, writing it to
    the Network Trust Intelligence (GlobalCredibilityIndex) registry —
    the final step of the Operations -> Master Admin chain."""
    result = await db.execute(select(CompanyRatingRequest).where(CompanyRatingRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Rating request not found")
    if req.status != "PENDING_MASTER_APPROVAL":
        raise HTTPException(status_code=400, detail=f"Request is not pending Master Admin approval (status: {req.status})")

    # Master Admin can adjust before final approval, or just accept what
    # Operations proposed if the request body doesn't override a field.
    partner_trust_score = float(payload.get("partner_trust_score") or req.proposed_partner_trust_score or 0)
    verdict_raw = payload.get("ai_credit_risk_verdict") or req.proposed_ai_credit_risk_verdict or "Not Rated"
    status_raw = payload.get("credibility_status") or req.proposed_credibility_status or "Standard"

    try:
        verdict = AICreditRiskVerdict(verdict_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid ai_credit_risk_verdict: {verdict_raw}")
    try:
        cred_status = CredibilityStatus(status_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid credibility_status: {status_raw}")

    # Try to find an existing GCI entry for this company name first.
    # Using .first() rather than .scalar_one_or_none() deliberately — this
    # app has pre-existing duplicate rows for the same company_name from
    # earlier testing (no unique constraint enforces one row per company),
    # and scalar_one_or_none() raises MultipleResultsFound the moment more
    # than one row matches, crashing this endpoint entirely. .first() just
    # picks the most relevant one instead of failing on the duplicate.
    gci_result = await db.execute(
        select(GlobalCredibilityIndex)
        .where(GlobalCredibilityIndex.company_name == req.company_name)
        .order_by(GlobalCredibilityIndex.approved_at.desc().nullslast())
    )
    gci_entry = gci_result.scalars().first()

    if gci_entry:
        gci_entry.partner_trust_score = partner_trust_score
        gci_entry.ai_credit_risk_verdict = verdict
        gci_entry.credibility_status = cred_status
        gci_entry.approved_by_master_admin_id = current_user.id
        gci_entry.approved_at = datetime.utcnow()
    else:
        gci_entry = GlobalCredibilityIndex(
            id=str(uuid.uuid4()),
            company_name=req.company_name,
            partner_trust_score=partner_trust_score,
            ai_credit_risk_verdict=verdict,
            credibility_status=cred_status,
            approved_by_master_admin_id=current_user.id,
            approved_at=datetime.utcnow(),
        )
        db.add(gci_entry)

    req.status = "COMPLETED"
    req.completed_at = datetime.utcnow()
    req.master_approved_by = current_user.id
    req.master_notes = payload.get("notes") or ""
    await db.commit()

    if req.requested_by_email:
        try:
            await NotificationService.send(
                db, req.requested_by_email,
                title="Company Rating Added",
                message=f"{req.company_name}'s credibility rating is now available in the Network Trust Intelligence registry.",
                ntype="INFO",
                action_url="/credibility-index",
            )
        except Exception as e:
            print(f"[RATING REQUEST] Failed to notify requester: {e}")

    return {"message": f"{req.company_name}'s rating has been added to the registry."}
