"""Business Profile schemas"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class BusinessProfileResponse(BaseModel):
    """Business profile response"""
    id: str
    user_id: str
    name: str
    registered_name: str
    email: str
    phone: str
    gstin: Optional[str] = None
    address: Optional[str] = None
    pan: Optional[str] = None
    cin: Optional[str] = None
    msme_no: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_name: Optional[str] = None
    bank_upi_id: Optional[str] = None
    profile_photo_url: Optional[str] = None
    company_logo_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BusinessProfileUpdateRequest(BaseModel):
    """Business profile update request"""
    name: Optional[str] = None
    registered_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    gstin: Optional[str] = Field(None, min_length=15, max_length=15)
    address: Optional[str] = None
    pan: Optional[str] = Field(None, min_length=10, max_length=10)
    cin: Optional[str] = None
    msme_no: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_name: Optional[str] = None
    bank_upi_id: Optional[str] = None
    profile_photo_url: Optional[str] = None
    company_logo_url: Optional[str] = None


class FileUploadRequest(BaseModel):
    """File upload response with Drive URL"""
    file_type: str = Field(..., description="'profile_photo' or 'company_logo'")
    drive_url: str = Field(..., description="Google Drive file URL")
