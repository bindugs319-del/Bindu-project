"""
Subscription management routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.database import get_db
from app.schemas import (
    SubscriptionRequest, SubscriptionResponse, SubscriptionStatusResponse, 
    WorkflowActionRequest, ProofUploadRequest, RejectRequest
)
from app.services.subscription_service import SubscriptionService
from app.exceptions import PlanNotFound, UserNotFound
from app.utils.response import ResponseFormatter
from app.utils.audit import log_audit
from app.dependencies import get_current_user, require_role, require_master_admin
from app.models import UserRole, Subscription, User
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get("/plans", response_model=dict)
async def list_plans(db: Annotated[AsyncSession, Depends(get_db)]):
    """List all membership plans (public)"""
    try:
        from app.models import Plan
        from sqlalchemy import select
        
        stmt = select(Plan).where(Plan.is_active == True).order_by(Plan.price)
        result = await db.execute(stmt)
        plans = result.scalars().all()
        
        return ResponseFormatter.create_success(
            data=[{
                "id": p.id,
                "name": p.name,
                "display_name": p.display_name,
                "description": p.description,
                "duration_type": p.duration_type.value if hasattr(p.duration_type, 'value') else str(p.duration_type),
                "price": p.price,
                "validity_days": p.validity_days,
                "features": {
                    "follow_up_limit": p.follow_up_limit,
                    "legal_assistance_limit": p.legal_assistance_limit,
                }
            } for p in plans]
        )
    except Exception as e:
        logger.error(f"Error in list_plans: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=dict)
async def list_subscriptions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str = None
):
    """List subscriptions with role-based filtering"""
    stmt = select(Subscription).order_by(Subscription.created_at.desc())
    
    if current_user.role == UserRole.USER:
        stmt = stmt.where(Subscription.user_id == current_user.id)
    elif current_user.role == UserRole.FINANCIAL:
        pass 
    elif current_user.role == UserRole.OPERATION:
        pass
    
    if status:
        stmt = stmt.where(Subscription.status == status)
        
    result = await db.execute(stmt)
    subscriptions = result.scalars().all()
    
    return ResponseFormatter.create_success(
        data=[SubscriptionResponse.from_orm(s) for s in subscriptions]
    )


@router.post("/verify", response_model=dict)
async def verify_subscription(
    admin: Annotated[User, Depends(require_role(["FINANCIAL", "MASTER_ADMIN"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: WorkflowActionRequest
):
    """Verify payment (FINANCIAL only)"""
    sub = await SubscriptionService.process_workflow(
        subscription_id=request.subscription_id,
        action="VERIFY",
        admin_id=admin.id,
        db=db,
        notes=request.notes
    )
    await db.commit()
    await log_audit(
        db=db,
        user=admin,
        action="SUBSCRIPTION_VERIFIED",
        entity_obj=sub,
        reason=request.notes
    )
    return ResponseFormatter.create_success(message="Subscription payment verified")


@router.post("/process", response_model=dict)
async def process_subscription(
    admin: Annotated[User, Depends(require_role(["OPERATION", "MASTER_ADMIN"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: WorkflowActionRequest
):
    """Process subscription (OPERATION only)"""
    sub = await SubscriptionService.process_workflow(
        subscription_id=request.subscription_id,
        action="PROCESS",
        admin_id=admin.id,
        db=db,
        notes=request.notes
    )
    await db.commit()
    await log_audit(
        db=db,
        user=admin,
        action="SUBSCRIPTION_PROCESSED",
        entity_obj=sub,
        reason=request.notes
    )
    return ResponseFormatter.create_success(message="Subscription request processed")


@router.post("/approve", response_model=dict)
async def approve_subscription(
    admin: Annotated[User, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: WorkflowActionRequest
):
    """Approve or Reject subscription (MASTER_ADMIN only)"""
    action = request.action if request.action in ["APPROVE", "REJECT"] else "APPROVE"
    sub = await SubscriptionService.process_workflow(
        subscription_id=request.subscription_id,
        action=action,
        admin_id=admin.id,
        db=db,
        notes=request.notes
    )
    await db.commit()

    audit_action = "SUBSCRIPTION_APPROVED" if action == "APPROVE" else "SUBSCRIPTION_REJECTED"
    display_action = "approved" if action == "APPROVE" else "rejected"

    await log_audit(
        db=db,
        user=admin,
        action=audit_action,
        entity_obj=sub,
        reason=request.notes
    )
    return ResponseFormatter.create_success(message=f"Subscription {display_action} successfully")


@router.post("", response_model=dict)
async def purchase_subscription(
    request: SubscriptionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Purchase a subscription plan"""
    try:
        subscription = await SubscriptionService.purchase_subscription(
            user_id=getattr(current_user, "id"),
            plan_id=request.plan_id,
            payment_proof_url=request.payment_proof_url,
            payment_id=request.transaction_id,
            db=db,
        )
        
        await db.commit()
        
        await log_audit(
            db=db,
            user=current_user,
            action="SUBSCRIPTION_PURCHASED",
            entity_obj=subscription,
            reason=f"Purchased plan: {subscription.plan_id}"
        )
        
        try:
            from app.services.workflow_service import WorkflowService
            from app.models import Plan
            plan_stmt = select(Plan).where(Plan.id == request.plan_id)
            plan_res = await db.execute(plan_stmt)
            plan_obj = plan_res.scalars().first()
            
            await WorkflowService.create_subscription_request(
                db=db,
                user_id=str(current_user.id),
                user_email=current_user.email,
                company_name=current_user.company_name or "Unknown Company",
                plan_name=plan_obj.display_name if plan_obj else "Unknown Plan",
                amount=float(plan_obj.price if plan_obj else 0.0)
            )
        except Exception as workflow_err:
            logger.error(f"Failed to trigger workflow: {workflow_err}")
        
        return ResponseFormatter.create_success(
            message="Subscription request submitted. Waiting for verification.",
            data={
                "subscription_id": subscription.id,
                "status": subscription.status,
            },
        )
    except PlanNotFound:
        logger.warning(f"User {getattr(current_user, 'id', 'unknown')} tried to purchase non-existent plan")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found or inactive",
        )
    except UserNotFound:
        logger.error(f"Authenticated user {getattr(current_user, 'id', 'unknown')} not found in database")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except Exception as e:
        logger.error(f"Error purchasing subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to purchase subscription",
        )


@router.get("/status", response_model=dict)
async def get_subscription_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get current subscription status for authenticated user"""
    try:
        subscription = await SubscriptionService.get_active_subscription(
            user_id=getattr(current_user, "id"),
            db=db,
        )
        
        has_active = False
        days_remaining = None
        is_expired = False
        
        if subscription:
            is_valid = await SubscriptionService.is_subscription_valid(subscription)
            has_active = is_valid
            
            if subscription.expiry_date:
                now = datetime.now()
                if subscription.expiry_date < now:
                    is_expired = True
                    days_remaining = 0
                else:
                    delta = subscription.expiry_date - now
                    days_remaining = delta.days
        
        subscription_data = None
        if subscription:
            expiry_isoformat = subscription.expiry_date.isoformat() if subscription.expiry_date else None
            subscription_data = {
                "id": subscription.id,
                "plan_id": subscription.plan_id,
                "is_active": subscription.is_active,
                "start_date": subscription.start_date.isoformat(),
                "expiry_date": expiry_isoformat,
                "status": subscription.status.value if hasattr(subscription.status, 'value') else str(subscription.status),
            }
        
        pending_data = None
        if not has_active:
            from sqlalchemy import select
            from app.models import Subscription, MembershipStatus
            stmt = select(Subscription).where(
                Subscription.user_id == getattr(current_user, "id"),
                Subscription.status.in_([MembershipStatus.PENDING, MembershipStatus.VERIFIED, MembershipStatus.PROCESSED])
            ).order_by(Subscription.created_at.desc())
            res = await db.execute(stmt)
            pending_sub = res.scalars().first()
            if pending_sub:
                pending_data = {
                    "id": pending_sub.id,
                    "status": pending_sub.status.value if hasattr(pending_sub.status, 'value') else str(pending_sub.status),
                    "created_at": pending_sub.created_at.isoformat()
                }

        return ResponseFormatter.create_success(
            message="Subscription status retrieved",
            data={
                "has_active_subscription": has_active,
                "is_expired": is_expired,
                "days_remaining": days_remaining,
                "subscription": subscription_data,
                "pending_subscription": pending_data
            },
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error getting subscription status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subscription status: {str(e)}",
        )


@router.post("/{subscription_id}/upload-proof")
async def upload_proof(
    subscription_id: str,
    req: ProofUploadRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """USER uploads payment proof"""
    subscription = await SubscriptionService.get_subscription_details(subscription_id, db)
    if subscription.user_id != getattr(current_user, "id"):
        raise HTTPException(status_code=403, detail="Not authorized to update this subscription")
        
    updated = await SubscriptionService.upload_payment_proof(subscription_id, req.payment_proof_url, db)
    await db.commit()
    
    await log_audit(
        db=db,
        user_id=current_user.id,
        action="SUBSCRIPTION_PROOF_UPLOAD",
        entity="Subscription",
        entity_id=subscription_id,
        metadata={"proof_url": req.payment_proof_url}
    )
    
    return ResponseFormatter.create_success(message="Proof uploaded successfully")


@router.get("/{subscription_id}", response_model=dict)
async def get_subscription_details(
    subscription_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get details of a specific subscription"""
    try:
        subscription = await SubscriptionService.get_subscription_details(
            subscription_id=subscription_id,
            db=db,
        )
        
        if subscription.user_id != getattr(current_user, "id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized to view this subscription",
            )
        
        return ResponseFormatter.create_success(
            message="Subscription details retrieved",
            data={
                "id": subscription.id,
                "plan_id": subscription.plan_id,
                "is_active": subscription.is_active,
                "start_date": subscription.start_date.isoformat(),
                "expiry_date": subscription.expiry_date.isoformat() if subscription.expiry_date else None,
                "plan": {
                    "name": subscription.plan.name,
                    "display_name": subscription.plan.display_name,
                    "price": subscription.plan.price,
                    "validity_days": subscription.plan.validity_days,
                    "follow_up_limit": subscription.plan.follow_up_limit,
                    "legal_assistance_limit": subscription.plan.legal_assistance_limit,
                } if subscription.plan else None,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subscription details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get subscription details",
        )
