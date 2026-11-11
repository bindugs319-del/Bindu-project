"""
Pydantic schemas for authentication
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal


class RegisterRequest(BaseModel):
    """User registration request"""

    company_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=64)
    phone: str = Field(..., min_length=10, max_length=20)
    gstin: str = Field(..., min_length=15, max_length=15)
    otp_code: Optional[str] = Field(None, min_length=4, max_length=10)
    # Organisation (optional): register as an independent company (default),
    # a head office, or a branch of an existing head office.
    org_type: Optional[Literal["INDEPENDENT", "HEAD_OFFICE", "BRANCH"]] = "INDEPENDENT"
    hq_gstin: Optional[str] = Field(None, min_length=15, max_length=15)
    branch_name: Optional[str] = Field(None, min_length=2, max_length=120)


class RegisterSendOTPRequest(BaseModel):
    """Send OTP for registration"""

    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=64)
    gstin: str



class TokenResponse(BaseModel):
    """Token response (access token in cookie, refresh token in httpOnly cookie)"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str


class ChangePhoneRequest(BaseModel):
    """Phone change request"""

    new_phone: str


class SendOTPRequest(BaseModel):
    """Send OTP request"""

    phone: str


class VerifyOTPRequest(BaseModel):
    """Verify OTP request"""

    phone: str
    otp_code: str = Field(..., min_length=4, max_length=10)


class EmailLoginSendOTPRequest(BaseModel):
    email: EmailStr


class EmailLoginVerifyOTPRequest(BaseModel):
    email: EmailStr
    gstin: str
    otp_code: str = Field(..., min_length=4, max_length=10)
