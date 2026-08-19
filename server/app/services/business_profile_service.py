"""
Business Profile service
"""
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import BusinessProfile, User
from app.exceptions import UserNotFound
import logging

logger = logging.getLogger(__name__)


class BusinessProfileService:
    """Handle business profile CRUD and management"""

    @staticmethod
    async def get_or_create_profile(user_id: str, db: AsyncSession) -> BusinessProfile:
        """
        Get user's business profile or create one if doesn't exist
        
        Args:
            user_id: User ID
            db: Database session
            
        Returns:
            BusinessProfile object
        """
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == user_id)
        result = await db.execute(stmt)
        profile = result.scalars().first()
        
        if profile:
            return profile
        
        # Create default profile from user data
        user_stmt = select(User).where(User.id == user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalars().first()
        
        if not user:
            raise UserNotFound()
        
        # business_profiles' DateTime columns are plain (timezone-naive) —
        # see the note on the same fix in update_profile() below.
        now = datetime.utcnow()
        new_profile = BusinessProfile(
            id=str(uuid4()),
            user_id=user_id,
            name=user.company_name or user.name or "",
            registered_name=user.company_name or "",
            email=user.email,
            phone=user.phone or "N/A",  # Ensure phone is not null
            gstin=user.gstin or "N/A",
            created_at=now,
            updated_at=now,
        )
        
        db.add(new_profile)
        await db.flush()
        
        logger.info(f"Created default business profile for user {user_id}")
        return new_profile

    @staticmethod
    async def update_profile(
        user_id: str,
        updates: dict,
        db: AsyncSession,
    ) -> BusinessProfile:
        """
        Update business profile
        
        Args:
            user_id: User ID
            updates: Dictionary of fields to update
            db: Database session
            
        Returns:
            Updated BusinessProfile
        """
        profile = await BusinessProfileService.get_or_create_profile(user_id, db)
        
        # Update allowed fields
        allowed_fields = {
            "name",
            "registered_name",
            "email",
            "phone",
            "gstin",
            "address",
            "pan",
            "cin",
            "msme_no",
            "bank_account_name",
            "bank_account_number",
            "bank_ifsc",
            "bank_name",
            "bank_upi_id",
            "profile_photo_url",
            "company_logo_url",
        }
        
        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                setattr(profile, field, value)
        
        # business_profiles.updated_at is a plain (timezone-naive) column —
        # datetime.now(timezone.utc) is aware and would crash asyncpg the
        # same way it did in invoices.py before that fix. Use a naive UTC
        # timestamp instead.
        profile.updated_at = datetime.utcnow()
        
        logger.info(f"Updated business profile for user {user_id}: {list(updates.keys())}")
        return profile

    @staticmethod
    async def set_profile_photo(
        user_id: str,
        photo_url: str,
        db: AsyncSession,
    ) -> BusinessProfile:
        """
        Set profile photo URL
        
        Args:
            user_id: User ID
            photo_url: Google Drive URL
            db: Database session
            
        Returns:
            Updated BusinessProfile
        """
        return await BusinessProfileService.update_profile(
            user_id,
            {"profile_photo_url": photo_url},
            db,
        )

    @staticmethod
    async def set_company_logo(
        user_id: str,
        logo_url: str,
        db: AsyncSession,
    ) -> BusinessProfile:
        """
        Set company logo URL
        
        Args:
            user_id: User ID
            logo_url: Google Drive URL
            db: Database session
            
        Returns:
            Updated BusinessProfile
        """
        return await BusinessProfileService.update_profile(
            user_id,
            {"company_logo_url": logo_url},
            db,
        )

    @staticmethod
    async def get_profile(user_id: str, db: AsyncSession) -> BusinessProfile:
        """
        Get user's business profile
        
        Args:
            user_id: User ID
            db: Database session
            
        Returns:
            BusinessProfile
        """
        return await BusinessProfileService.get_or_create_profile(user_id, db)
