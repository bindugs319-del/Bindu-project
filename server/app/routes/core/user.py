"""
User profile, settings, and subscription endpoints.
"""
from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form
from typing import Annotated
from fastapi.responses import JSONResponse
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
from app.utils.phone import is_valid_phone
from app.config import settings
from app.utils.audit import log_audit

from .common import *  # noqa: F401,F403 (logger + shared constants)

user_router = APIRouter()

@user_router.get("/admin/settings")
async def get_admin_settings(db: Annotated[AsyncSession, Depends(get_db)]):
    """Get application settings"""
    from app.models import AppSettings
    stmt = select(AppSettings).where(AppSettings.id == 'default')
    result = await db.execute(stmt)
    settings = result.scalars().first()
    if not settings:
        return ResponseFormatter.create_success(data={"payment_window_days": 50})
    return ResponseFormatter.create_success(data={"payment_window_days": settings.payment_window_days})


@user_router.post("/admin/settings")
async def update_admin_settings(req: AdminSettingsRequest, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Update application settings (MASTER_ADMIN only)"""
    if current_user.role != "MASTER_ADMIN":
        raise HTTPException(status_code=403, detail="Access denied")
    
    payment_window_days = req.payment_window_days
    if payment_window_days is None:
        raise HTTPException(status_code=400, detail="payment_window_days is required")
        
    from app.models import AppSettings
    stmt = select(AppSettings).where(AppSettings.id == 'default')
    result = await db.execute(stmt)
    settings = result.scalars().first()
    
    if not settings:
        settings = AppSettings(id='default', payment_window_days=payment_window_days)
        db.add(settings)
    else:
        settings.payment_window_days = payment_window_days
        settings.updated_at = datetime.now(timezone.utc)
        
    await log_audit(db, current_user, "UPDATE_SETTINGS", reason=f"Payment window updated to {payment_window_days} days")
    await db.commit()
    return ResponseFormatter.create_success(message="Settings updated successfully")


@user_router.get("/profile")
async def get_profile(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current user profile"""
    return ResponseFormatter.create_success(data=UserProfileResponse.model_validate(current_user).__dict__)


@user_router.options("/profile")
async def profile_options():
    # Empty response; CORSMiddleware will add CORS headers
    return JSONResponse(content={})


@user_router.put("/profile")
async def update_profile(req: UpdateProfileRequest, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Update user profile"""
    user = await UserService.update_profile(current_user.id, req, db)
    await log_audit(db, current_user, "UPDATE_PROFILE", target_user=user, reason="User updated their profile")
    return ResponseFormatter.create_success(data=UserProfileResponse.model_validate(user).__dict__)


@user_router.post("/phone-change/send-otp")
async def send_phone_change_otp(req: PhoneChangeRequest, current_user: Annotated[User, Depends(get_current_user)]):
    """Send OTP for phone change"""
    # Accept both 'new_phone' (from frontend) and 'phone' (for compatibility)
    new_phone = (req.new_phone or req.phone or "").strip()
    
    if not new_phone:
        from app.exceptions import InvalidPhone
        raise InvalidPhone("Phone number is required")
    
    # Try to format to E.164 first, then validate
    phone_e164 = format_phone_e164(new_phone)
    if not phone_e164:
        # If E.164 formatting fails, try validating as-is
        if not is_valid_phone(new_phone):
            from app.exceptions import InvalidPhone
            raise InvalidPhone(f"Invalid phone number format: {new_phone}. Please use format: +91XXXXXXXXXX")
        # If validation passes but formatting fails, use the original
        phone_e164 = new_phone
    
    # Send OTP via SMS (if configured) or email
    # Pass user email so OTP can be sent via email if SMS fails
    result = await OTPService.send_otp(phone_e164, purpose="phone_change", email=current_user.email)
    
    return ResponseFormatter.create_success(data={"sent": result["sent"], "message": result.get("message", "OTP sent")})


@user_router.post("/phone-change/verify-otp")
async def verify_phone_change_otp(req: OTPVerifyRequest, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Verify OTP and change phone"""
    # Use phone from request (could be in phone or new_phone field)
    # OTPVerifyRequest has 'phone' field
    new_phone = (req.phone or "").strip()
    otp_code = (req.otp_code or "").strip()
    
    if not new_phone:
        from app.exceptions import InvalidPhone
        raise InvalidPhone("Phone number is required")
    
    if not otp_code:
        from app.exceptions import InvalidOTP
        raise InvalidOTP("OTP code is required")
    
    # Format to E.164
    phone_e164 = format_phone_e164(new_phone) or new_phone
    
    # Verify OTP
    await OTPService.verify_otp(phone_e164, otp_code, purpose="phone_change")
    
    # Change phone
    await UserService.change_phone(current_user.id, phone_e164, db)
    await log_audit(db, current_user, "CHANGE_PHONE", target_user=current_user, reason=f"Phone changed to {phone_e164}")
    return ResponseFormatter.create_success(message="Phone changed successfully")


@user_router.post("/email-change/send-otp")
async def send_email_change_otp(req: EmailChangeRequest, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Send OTP for email change"""
    new_email = (req.new_email or req.email or "").strip().lower()
    
    if not new_email or "@" not in new_email:
        from app.exceptions import InvalidEmail
        raise InvalidEmail("Valid email address is required")
    
    # Check if email is already in use
    from sqlalchemy import select
    stmt = select(User).where(User.email == new_email, User.id != current_user.id)
    result = await db.execute(stmt)
    if result.scalars().first():
        from app.exceptions import InvalidEmail
        raise InvalidEmail("Email address already in use")
    
    # Send OTP to both current and new email addresses
    result = await OTPService.send_otp_for_email_change(new_email, current_user.email)
    
    return ResponseFormatter.create_success(
        data={"sent": result["sent"]},
        message=result.get("message", "OTP sent to both email addresses")
    )


@user_router.post("/email-change/verify-otp")
async def verify_email_change_otp(req: OTPVerifyRequest, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Verify OTP and change email"""
    new_email = (req.email or "").strip().lower()
    otp_code = (req.otp_code or "").strip()
    
    if not new_email or "@" not in new_email:
        from app.exceptions import InvalidEmail
        raise InvalidEmail("Valid email address is required")
    
    if not otp_code:
        from app.exceptions import InvalidOTP
        raise InvalidOTP("OTP code is required")
    
    # Verify OTP
    await OTPService.verify_otp_for_email_change(new_email, otp_code)
    
    # Change email
    from app.services import UserService
    from app.schemas import UpdateProfileRequest
    await UserService.update_profile(
        current_user.id,
        UpdateProfileRequest(email=new_email),
        db
    )
    await log_audit(db, current_user, "CHANGE_EMAIL", target_user=current_user, reason=f"Email changed to {new_email}")
    
    return ResponseFormatter.create_success(message="Email changed successfully")


@user_router.get("/subscription")
async def get_subscription(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Get user subscription"""
    from app.models import Subscription
    role = str(getattr(current_user.role, "value", current_user.role) or "").upper()
    if "." in role:
        role = role.split(".")[-1]
    if role == "MASTER_ADMIN" or getattr(current_user, "subscription_bypass", False) or getattr(current_user, "full_access", False):
        from datetime import datetime
        data = {
            "id": current_user.id,
            "plan": "ADMIN_FREE",
            "is_active": True,
            "start_date": datetime.now(timezone.utc),
            "expiry_date": None,
        }
        return ResponseFormatter.create_success(data=data)
    stmt = select(Subscription).where(Subscription.user_id == current_user.id)
    result = await db.execute(stmt)
    sub = result.scalars().first()
    if not sub:
        return ResponseFormatter.create_success(data=None)
    return ResponseFormatter.create_success(data=SubscriptionResponse.model_validate(sub).__dict__)


