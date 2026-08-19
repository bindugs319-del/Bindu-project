"""
Business Profile management routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.schemas.business_profile import (
    BusinessProfileResponse,
    BusinessProfileUpdateRequest,
    FileUploadRequest,
)
from app.services.business_profile_service import BusinessProfileService
from app.services.drive_service import DriveService
from app.exceptions import UserNotFound
from app.utils.response import ResponseFormatter
from app.dependencies import get_current_user
import logging
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["Account"])


def _safe_attr(obj, name, default=None):
    """
    Safely read an attribute off an ORM object.

    Under async SQLAlchemy, touching an attribute that has been expired
    (e.g. after a rollback/commit elsewhere in the request) triggers an
    implicit lazy-load, which requires an awaited DB round-trip and
    crashes with MissingGreenlet if done from plain sync code like
    getattr(). This wrapper catches that (and any other unexpected
    error) and just falls back to `default` instead of taking down the
    whole endpoint.
    """
    if obj is None:
        return default
    try:
        value = getattr(obj, name, default)
        return value if value is not None else default
    except Exception:
        return default


@router.get("/profile", response_model=dict)
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Get current user's business profile
    """
    profile = None
    try:
        print(f"[PROFILE] Fetching for user: {current_user.email}")
        try:
            profile = await BusinessProfileService.get_profile(
                user_id=current_user.id,
                db=db,
            )
            print(f"[PROFILE] Got profile: {_safe_attr(profile, 'id')}")
        except Exception as prof_e:
            print(f"[PROFILE] Warning: failed to get BusinessProfile: {prof_e}")
            profile = None
        
        def _dt_iso(dt):
            if dt is None:
                return None
            try:
                return dt.isoformat()
            except Exception:
                return str(dt)

        return ResponseFormatter.create_success(
            message="Profile retrieved",
            data={
                "id": _safe_attr(profile, "id", current_user.id),
                "user_id": current_user.id,
                "name": _safe_attr(profile, "name") or _safe_attr(current_user, "name") or "",
                "registered_name": _safe_attr(profile, "registered_name") or _safe_attr(current_user, "company_name") or "",
                "email": _safe_attr(profile, "email") or _safe_attr(current_user, "email") or "",
                "phone": _safe_attr(profile, "phone") or "N/A",
                "gstin": _safe_attr(profile, "gstin") or _safe_attr(current_user, "gstin") or "N/A",
                "address": _safe_attr(profile, "address"),
                "pan": _safe_attr(profile, "pan"),
                "cin": _safe_attr(profile, "cin"),
                "msme_no": _safe_attr(profile, "msme_no"),
                "bank_account_name": _safe_attr(profile, "bank_account_name"),
                "bank_account_number": _safe_attr(profile, "bank_account_number"),
                "bank_ifsc": _safe_attr(profile, "bank_ifsc"),
                "bank_name": _safe_attr(profile, "bank_name"),
                "bank_upi_id": _safe_attr(profile, "bank_upi_id"),
                "profile_photo_url": _safe_attr(profile, "profile_photo_url"),
                "company_logo_url": _safe_attr(profile, "company_logo_url"),
                "role": _safe_attr(_safe_attr(current_user, "role"), "value", str(_safe_attr(current_user, "role", "USER"))),
                "company_name": _safe_attr(current_user, "company_name") or _safe_attr(profile, "registered_name") or "",
                "created_at": _dt_iso(_safe_attr(profile, "created_at")),
                "updated_at": _dt_iso(_safe_attr(profile, "updated_at")),
            },
        )
    except UserNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except Exception as e:
        try:
            await db.rollback()
        except Exception as rollback_err:
            logger.warning(f"[PROFILE] Rollback after error also failed: {rollback_err}")
        print(f"[PROFILE] ERROR:")
        import traceback
        print(traceback.format_exc())
        logger.exception(f"Error getting profile for {current_user.email}: {e}")
        
        def _dt_iso(dt):
            if dt is None:
                return None
            try:
                return dt.isoformat()
            except Exception:
                return str(dt)
        
        return ResponseFormatter.create_success(
            message="Profile retrieved (fallback)",
            data={
                "id": current_user.id,
                "user_id": current_user.id,
                "name": _safe_attr(current_user, "name") or current_user.email.split('@')[0],
                "email": current_user.email,
                "role": _safe_attr(_safe_attr(current_user, "role"), "value", str(_safe_attr(current_user, "role", "USER"))),
                "company_name": _safe_attr(current_user, "company_name") or "N/A",
                "gstin": _safe_attr(current_user, "gstin") or "N/A",
                "phone": "N/A"
            }
        )


@router.put("/profile", response_model=dict)
async def update_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: BusinessProfileUpdateRequest
):
    """
    Update business profile
    """
    try:
        updates = request.dict(exclude_unset=True)
        
        profile = await BusinessProfileService.update_profile(
            user_id=current_user.id,
            updates=updates,
            db=db,
        )
        
        await db.commit()
        
        return ResponseFormatter.create_success(
            message="Profile updated successfully",
            data={
                "id": profile.id,
                "name": profile.name,
                "registered_name": profile.registered_name,
                "email": profile.email,
                "phone": profile.phone,
                "gstin": profile.gstin,
                "address": profile.address,
                "pan": profile.pan,
                "cin": profile.cin,
                "msme_no": profile.msme_no,
                "bank_account_name": profile.bank_account_name,
                "bank_account_number": profile.bank_account_number,
                "bank_ifsc": profile.bank_ifsc,
                "bank_name": profile.bank_name,
                "bank_upi_id": profile.bank_upi_id,
                "profile_photo_url": profile.profile_photo_url,
                "company_logo_url": profile.company_logo_url,
            },
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile",
        )


@router.post("/profile-photo", response_model=dict)
async def upload_profile_photo(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file_request: FileUploadRequest
):
    """
    Set profile photo from Google Drive URL
    """
    try:
        profile = await BusinessProfileService.set_profile_photo(
            user_id=current_user.id,
            photo_url=file_request.drive_url,
            db=db,
        )
        
        await db.commit()
        
        return ResponseFormatter.create_success(
            message="Profile photo updated",
            data={"profile_photo_url": profile.profile_photo_url},
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating profile photo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile photo",
        )


@router.post("/company-logo", response_model=dict)
async def upload_company_logo(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file_request: FileUploadRequest
):
    """
    Set company logo from Google Drive URL
    """
    try:
        profile = await BusinessProfileService.set_company_logo(
            user_id=current_user.id,
            logo_url=file_request.drive_url,
            db=db,
        )
        
        await db.commit()
        
        return ResponseFormatter.create_success(
            message="Company logo updated",
            data={"company_logo_url": profile.company_logo_url},
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating company logo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update company logo",
        )
