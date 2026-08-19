"""Payment schemas"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal
from enum import Enum


class PaymentMethodEnum(str, Enum):
    """Payment method options"""
    UPI = "upi"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    NET_BANKING = "net_banking"
    QR_CODE = "qr_code"


class PaymentStatusEnum(str, Enum):
    """Payment status options"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentInitiateRequest(BaseModel):
    """Initiate payment request"""
    plan_id: str = Field(..., description="Plan ID to purchase")
    payment_method: PaymentMethodEnum = Field(..., description="Payment method selected")


class PaymentVerifyRequest(BaseModel):
    """Verify payment request"""
    transaction_id: str = Field(..., description="Transaction ID from payment gateway")
    gateway_order_id: Optional[str] = Field(None, description="Gateway order ID")
    gateway_payment_id: Optional[str] = Field(None, description="Gateway payment ID")


class PaymentResponse(BaseModel):
    """Payment response schema"""
    id: str
    user_id: str
    plan_id: str
    amount: float
    currency: str
    payment_method: str
    payment_provider: Optional[str] = None
    status: str
    transaction_id: Optional[str] = None
    reference_id: str
    gateway_order_id: Optional[str] = None
    gateway_payment_id: Optional[str] = None
    failure_reason: Optional[str] = None
    payment_metadata: dict = {}
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaymentInitiateResponse(BaseModel):
    """Payment initiation response"""
    payment_id: str
    reference_id: str
    amount: float
    currency: str
    plan: dict  # Plan details
    payment_options: dict  # Payment method specific options (QR code, gateway URL, etc.)


class PaymentStatusResponse(BaseModel):
    """Payment status response"""
    payment_id: str
    status: str
    transaction_id: Optional[str] = None
    amount: float
    created_at: datetime
    completed_at: Optional[datetime] = None


class PaymentHistoryResponse(BaseModel):
    """Payment history entry"""
    id: str
    plan_name: str
    amount: float
    status: str
    payment_method: str
    transaction_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
