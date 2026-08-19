"""
Pydantic schemas for features (PO, defaulter, credit report, settlement)
"""
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class PurchaseOrderRequest(BaseModel):
    """Create/update purchase order"""
    po_number: str = Field(..., min_length=1, max_length=100)
    vendor: str = Field(..., min_length=2, max_length=255)
    gstin: Optional[str] = Field(None, min_length=15, max_length=15)
    amount: float = Field(..., gt=0)
    due_date: datetime
    vendor_email: Optional[str] = None
    vendor_phone: Optional[str] = None
    status: Optional[str] = "Open"
    notes: Optional[str] = None
    document_url: Optional[str] = None
    evidence_url: Optional[str] = None
    supplier_address: Optional[str] = None
    delivery_address: Optional[str] = None
    invoice_address: Optional[str] = None
    payment_window_days: Optional[int] = 50
    reason: Optional[str] = None

class PurchaseOrderUpdate(BaseModel):
    """Update purchase order"""
    po_number: Optional[str] = None
    vendor: Optional[str] = None
    gstin: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[datetime] = None
    vendor_email: Optional[str] = None
    vendor_phone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    document_url: Optional[str] = None
    evidence_url: Optional[str] = None
    supplier_address: Optional[str] = None
    delivery_address: Optional[str] = None
    invoice_address: Optional[str] = None
    payment_window_days: Optional[int] = None
    reason: Optional[str] = None

class GenericReasonRequest(BaseModel):
    """Generic request with reason"""
    reason: Optional[str] = "No reason provided"

class ArchiveRequest(BaseModel):
    """Archive/unarchive request"""
    reason: Optional[str] = "PO archive status updated"

class ReminderRequest(BaseModel):
    """Manual vendor reminder request"""
    subject: Optional[str] = None
    body: Optional[str] = None
    scheduled_at: Optional[str] = None
    include_legal_notice: Optional[bool] = False
    legal_notice_content: Optional[str] = ""

class AdminSettingsRequest(BaseModel):
    """Update admin settings request"""
    reminder_subject_template: Optional[str] = None
    reminder_body_template: Optional[str] = None
    payment_window_days: Optional[int] = 50

class OTPVerifyRequest(BaseModel):
    """Generic OTP verification request"""
    otp: str = Field(..., min_length=6, max_length=6)
    token: Optional[str] = None

class PhoneChangeRequest(BaseModel):
    """Request to change phone number"""
    new_phone: str = Field(..., min_length=10, max_length=15)

class EmailChangeRequest(BaseModel):
    """Request to change email"""
    new_email: EmailStr


class POApprovalRequest(BaseModel):
    """Approve/reject PO request"""
    action: str = Field(..., pattern="^(APPROVE|REJECT)$")
    reason: Optional[str] = None


class PurchaseOrderResponse(BaseModel):
    """Purchase order response"""

    id: str
    number: str
    vendor_name: str
    vendor_gstin: Optional[str] = None
    amount: float
    due_date: datetime
    status: str
    document_url: Optional[str] = None
    evidence_url: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GSTINCheckRequest(BaseModel):
    """GSTIN check request"""
    gstin: str = Field(..., min_length=15, max_length=15)


class GSTINCheckResponse(BaseModel):
    """GSTIN check response"""
    status: str
    credibility_score: int
    risk_level: str


class BusinessRequestSchema(BaseModel):
    """Business risk analysis request"""
    id: str
    company_name: str
    gstin: Optional[str] = None
    status: str
    risk_score: Optional[int] = None
    recommendation: Optional[str] = None
    legal_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BusinessReportSubmit(BaseModel):
    """LEGAL team report submission"""
    request_id: str
    risk_score: int = Field(..., ge=0, le=100)
    recommendation: str
    legal_notes: Optional[str] = None


class BusinessRequestCreate(BaseModel):
    """Create business risk analysis request"""
    company_name: str
    gstin: Optional[str] = Field(None, min_length=15, max_length=15)


class DefaulterCaseRequest(BaseModel):
    """Create defaulter case"""

    business_name: str = Field(..., min_length=2, max_length=255)
    business_gstin: Optional[str] = Field(None, min_length=15, max_length=15)
    pan: Optional[str] = Field(None, min_length=10, max_length=10)
    invoice_number: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0)
    due_date: datetime
    notes: Optional[str] = None
    documents_drive_folder: Optional[str] = None

    @field_validator("business_gstin", "pan", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        # Optional fields with min_length still validate an empty string
        # (it's not None) — treat "" the same as omitting the field, since
        # that's what an unfilled optional form input naturally sends.
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class DefaulterCaseUpdate(BaseModel):
    """Update defaulter case"""
    business_name: Optional[str] = None
    business_gstin: Optional[str] = None
    pan: Optional[str] = None
    invoice_number: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    documents_drive_folder: Optional[str] = None
    ledger_url: Optional[str] = None
    ca_certificate_url: Optional[str] = None


class DefaulterVerifyRequest(BaseModel):
    """Admin verifies defaulter case"""
    action: str = Field(..., pattern="^(approve|reject)$")
    notes: Optional[str] = None


class POReminderConfigUpdate(BaseModel):
    """Update PO reminder configuration"""
    before_days: Optional[int] = Field(None, ge=1)
    after_due_daily_enabled: Optional[bool] = None
    reminder_subject: Optional[str] = None
    reminder_body: Optional[str] = None


class DefaulterCaseResponse(BaseModel):
    """Defaulter case response"""

    id: str
    business_name: str
    business_gstin: Optional[str] = None
    invoice_number: str
    amount: float
    due_date: datetime
    status: str
    notes: Optional[str]
    documents_drive_folder: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreditReportRequest(BaseModel):
    """Request credit report"""

    entity_name: str = Field(..., min_length=2, max_length=255)
    entity_gstin: Optional[str] = Field(None, min_length=15, max_length=15)


class CreditReportUpdate(BaseModel):
    """Update credit report (admin/system)"""

    credit_score: Optional[int] = Field(None, ge=0, le=900)
    status: Optional[str] = None
    report_url: Optional[str] = None
    last_updated: Optional[datetime] = None


class CreditReportCompleteRequest(BaseModel):
    """LEGAL completes credit report"""

    report_url: str
    credit_score: int = Field(..., ge=0, le=900)


class CreditReportResponse(BaseModel):
    """Credit report response"""

    id: str
    entity_name: str
    entity_gstin: Optional[str] = None
    credit_score: Optional[int]
    status: str
    report_url: Optional[str]
    last_updated: Optional[datetime]
    requested_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SettlementRequest(BaseModel):
    """Create settlement record"""

    case_reference: str = Field(..., min_length=1, max_length=255)
    notes: Optional[str] = None


class SettlementUpdate(BaseModel):
    """Update settlement record"""

    case_reference: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = None
    notes: Optional[str] = None
    documents_drive_folder: Optional[str] = None


class ChatRequest(BaseModel):
    """AI Chat request"""
    message: str = Field(..., min_length=1)


class SettlementResponse(BaseModel):
    """Settlement response"""

    id: str
    case_reference: str
    status: str
    notes: Optional[str]
    documents_drive_folder: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InvoiceCreate(BaseModel):
    """Create invoice"""

    counterparty_name: str = Field(..., min_length=2, max_length=255)
    company_name: Optional[str] = None
    company_id: Optional[str] = None
    email: Optional[EmailStr] = None
    invoice_number: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0)
    due_date: datetime
    status: Optional[str] = "pending"
    reminder_frequency_days: Optional[int] = Field(7, ge=1, le=365)
    notes: Optional[str] = None


class InvoiceUpdate(BaseModel):
    """Update invoice"""

    counterparty_name: Optional[str] = Field(None, min_length=2, max_length=255)
    company_name: Optional[str] = None
    email: Optional[EmailStr] = None
    invoice_number: Optional[str] = Field(None, min_length=1, max_length=100)
    amount: Optional[float] = Field(None, gt=0)
    due_date: Optional[datetime] = None
    status: Optional[str] = None
    reminder_frequency_days: Optional[int] = Field(None, ge=1, le=365)
    notes: Optional[str] = None


class InvoiceResponse(BaseModel):
    """Invoice response"""

    id: UUID
    user_id: UUID
    counterparty_name: str
    counterparty_gstin: Optional[str] = None
    counterparty_pan: Optional[str] = None
    company_id: Optional[str] = None
    invoice_number: str
    amount: float
    due_date: datetime
    status: str
    workflow_status: Optional[str] = "Draft"
    operations_reviewed_by: Optional[str] = None
    operations_reviewed_at: Optional[datetime] = None
    operations_notes: Optional[str] = None
    master_approved_by: Optional[str] = None
    master_approved_at: Optional[datetime] = None
    master_notes: Optional[str] = None
    acknowledged_at: Optional[datetime]
    reminder_frequency_days: int
    reminder_next_at: Optional[datetime]
    last_follow_up_at: Optional[datetime]
    follow_up_history: List[Dict[str, Any]]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InvoiceWorkflowAction(BaseModel):
    """Operations/Master Admin review action on an invoice"""

    notes: Optional[str] = None


class InvoiceListResponse(BaseModel):
    """List of invoices"""

    invoices: List[InvoiceResponse]
    total: int
    skip: int
    limit: int


class InvoiceFollowUpNote(BaseModel):
    """Add follow-up note to invoice"""

    note: str = Field(..., min_length=1, max_length=2000)

