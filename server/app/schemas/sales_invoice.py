"""
Pydantic schemas for Sales Invoices — the GST tax-invoice format
(company + customer details, structured bill-to/ship-to, tax breakdown,
line items) backed by the sales_invoices table. Line items are stored
as a single JSON array on the invoice row, matching the supervisor's
spec sheet exactly (desc/hsn/qty/rate/amount keys).
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime

# Allowed values for the status workflow. Kept as a plain list rather
# than a DB enum so new statuses can be added without a migration.
VALID_STATUSES = ["Draft", "Sent", "Paid", "Overdue", "Cancelled"]


def _blank_to_none(v):
    """Treat an empty string the same as "not provided" for optional
    fields. HTML date inputs left empty submit "" rather than omitting
    the key entirely, which Pydantic can't parse as a date/datetime —
    this normalizes that before validation runs."""
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class Address(BaseModel):
    """Structured address block used for both bill_to and ship_to.
    Matches the spec's example exactly: {"name": ..., "address": ...}."""
    name: Optional[str] = None
    address: Optional[str] = None


class TaxBreakdown(BaseModel):
    """Tax split — either cgst+sgst (intra-state) or igst (inter-state),
    not both, per GST rules."""
    cgst: Optional[float] = 0.0
    sgst: Optional[float] = 0.0
    igst: Optional[float] = 0.0


class SalesInvoiceItem(BaseModel):
    """A single line item, matching the spec's example keys exactly
    (desc/hsn/qty/rate/amount) — stored as one entry in the invoice's
    `items` JSON array, not a separate database row."""
    desc: str = Field(..., min_length=1)
    hsn: Optional[str] = None
    qty: float = Field(default=1.0, gt=0)
    rate: float = Field(..., ge=0)
    amount: float = Field(..., ge=0)


class SalesInvoiceCreate(BaseModel):
    """Create a new sales invoice.

    Note: company_name / company_address / company_gstin / company_pan /
    cin / msme_no / bank_* are deliberately NOT accepted here — they're
    always taken from the user's saved BusinessProfile at creation time,
    so every invoice gets a consistent, auto-filled snapshot rather than
    depending on what the client happened to send.
    """
    invoice_number: Optional[str] = Field(None, max_length=100)
    invoice_date: date
    payment_due_date: date
    payment_terms: Optional[str] = None

    po_number: Optional[str] = None
    po_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None

    counterparty_name: str = Field(..., min_length=1, max_length=255)
    counterparty_gstin: Optional[str] = Field(None, min_length=15, max_length=15)
    counterparty_pan: Optional[str] = Field(None, min_length=10, max_length=10)
    counterparty_email: Optional[str] = Field(None, max_length=255)
    counterparty_phone: Optional[str] = Field(None, max_length=20)

    bill_to: Optional[Address] = None
    ship_to: Optional[Address] = None

    country: Optional[str] = "IN"
    currency: Optional[str] = "INR"
    exchange_rate: Optional[float] = Field(default=1.0, gt=0)

    lut_arn: Optional[str] = None
    lut_filing_date: Optional[date] = None
    place_of_supply: Optional[str] = None
    is_sez_export: Optional[bool] = False
    reverse_charge: Optional[bool] = False
    eway_bill_number: Optional[str] = None

    subtotal: Optional[float] = 0.0
    discount_amount: Optional[float] = 0.0
    tax_breakdown: Optional[TaxBreakdown] = None
    tax_amount: Optional[float] = 0.0
    round_off: Optional[float] = 0.0
    total: Optional[float] = 0.0
    balance_due: Optional[float] = 0.0

    status: Optional[str] = "Draft"
    notes: Optional[str] = None
    document_url: Optional[str] = None

    items: List[SalesInvoiceItem] = Field(default_factory=list)

    # Normalize empty-string optional fields (as sent by empty HTML date
    # inputs and empty text inputs) to None before type validation runs.
    _blank_po_date = field_validator("po_date", mode="before")(_blank_to_none)
    _blank_expected_delivery_date = field_validator("expected_delivery_date", mode="before")(_blank_to_none)
    _blank_lut_filing_date = field_validator("lut_filing_date", mode="before")(_blank_to_none)
    _blank_po_number = field_validator("po_number", mode="before")(_blank_to_none)
    _blank_payment_terms = field_validator("payment_terms", mode="before")(_blank_to_none)
    _blank_counterparty_gstin = field_validator("counterparty_gstin", mode="before")(_blank_to_none)
    _blank_counterparty_pan = field_validator("counterparty_pan", mode="before")(_blank_to_none)
    _blank_lut_arn = field_validator("lut_arn", mode="before")(_blank_to_none)
    _blank_place_of_supply = field_validator("place_of_supply", mode="before")(_blank_to_none)
    _blank_notes = field_validator("notes", mode="before")(_blank_to_none)
    _blank_eway_bill_number = field_validator("eway_bill_number", mode="before")(_blank_to_none)
    _blank_document_url = field_validator("document_url", mode="before")(_blank_to_none)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v):
        if v and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class SalesInvoiceUpdate(BaseModel):
    """Partial update — every field optional. `items`, if provided,
    fully replaces the invoice's existing items array."""
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    payment_due_date: Optional[date] = None
    payment_terms: Optional[str] = None

    po_number: Optional[str] = None
    po_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None

    counterparty_name: Optional[str] = None
    counterparty_gstin: Optional[str] = Field(None, min_length=15, max_length=15)
    counterparty_pan: Optional[str] = Field(None, min_length=10, max_length=10)
    counterparty_email: Optional[str] = Field(None, max_length=255)
    counterparty_phone: Optional[str] = Field(None, max_length=20)

    bill_to: Optional[Address] = None
    ship_to: Optional[Address] = None

    country: Optional[str] = None
    currency: Optional[str] = None
    exchange_rate: Optional[float] = Field(default=None, gt=0)

    lut_arn: Optional[str] = None
    lut_filing_date: Optional[date] = None
    place_of_supply: Optional[str] = None
    is_sez_export: Optional[bool] = None
    reverse_charge: Optional[bool] = None
    eway_bill_number: Optional[str] = None

    subtotal: Optional[float] = None
    discount_amount: Optional[float] = None
    tax_breakdown: Optional[TaxBreakdown] = None
    tax_amount: Optional[float] = None
    round_off: Optional[float] = None
    total: Optional[float] = None
    balance_due: Optional[float] = None

    status: Optional[str] = None
    notes: Optional[str] = None
    document_url: Optional[str] = None

    items: Optional[List[SalesInvoiceItem]] = None

    _blank_invoice_date = field_validator("invoice_date", mode="before")(_blank_to_none)
    _blank_payment_due_date = field_validator("payment_due_date", mode="before")(_blank_to_none)
    _blank_po_date = field_validator("po_date", mode="before")(_blank_to_none)
    _blank_expected_delivery_date = field_validator("expected_delivery_date", mode="before")(_blank_to_none)
    _blank_lut_filing_date = field_validator("lut_filing_date", mode="before")(_blank_to_none)
    _blank_po_number = field_validator("po_number", mode="before")(_blank_to_none)
    _blank_payment_terms = field_validator("payment_terms", mode="before")(_blank_to_none)
    _blank_counterparty_gstin = field_validator("counterparty_gstin", mode="before")(_blank_to_none)
    _blank_counterparty_pan = field_validator("counterparty_pan", mode="before")(_blank_to_none)
    _blank_lut_arn = field_validator("lut_arn", mode="before")(_blank_to_none)
    _blank_place_of_supply = field_validator("place_of_supply", mode="before")(_blank_to_none)
    _blank_notes = field_validator("notes", mode="before")(_blank_to_none)
    _blank_eway_bill_number = field_validator("eway_bill_number", mode="before")(_blank_to_none)
    _blank_document_url = field_validator("document_url", mode="before")(_blank_to_none)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v):
        if v and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class SalesInvoiceResponse(BaseModel):
    id: str
    user_id: str
    company_id: Optional[str] = None

    company_name: Optional[str] = None
    company_address: Optional[str] = None
    company_gstin: Optional[str] = None
    company_pan: Optional[str] = None
    cin: Optional[str] = None
    msme_no: Optional[str] = None

    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_name: Optional[str] = None
    bank_upi_id: Optional[str] = None

    invoice_number: str
    invoice_date: date
    payment_due_date: date
    payment_terms: Optional[str] = None

    po_number: Optional[str] = None
    po_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None

    counterparty_name: str
    counterparty_gstin: Optional[str] = None
    counterparty_pan: Optional[str] = None
    counterparty_email: Optional[str] = None
    counterparty_phone: Optional[str] = None

    bill_to: Optional[Dict[str, Any]] = None
    ship_to: Optional[Dict[str, Any]] = None

    country: str
    currency: str
    exchange_rate: float

    lut_arn: Optional[str] = None
    lut_filing_date: Optional[date] = None
    place_of_supply: Optional[str] = None
    is_sez_export: bool
    reverse_charge: Optional[bool] = False
    eway_bill_number: Optional[str] = None

    items: List[Dict[str, Any]] = Field(default_factory=list)

    subtotal: float
    discount_amount: float
    tax_breakdown: Optional[Dict[str, Any]] = None
    tax_amount: float
    round_off: float
    total: float
    balance_due: float

    status: str
    archived: bool

    # Approval workflow (User -> Operations -> Master Admin)
    workflow_status: Optional[str] = "Draft"
    operations_reviewed_by: Optional[str] = None
    operations_reviewed_at: Optional[datetime] = None
    operations_notes: Optional[str] = None
    master_approved_by: Optional[str] = None
    master_approved_at: Optional[datetime] = None
    master_notes: Optional[str] = None

    # Edit-approval (Operations Truth Check -> Master Admin)
    approval_status: Optional[str] = None
    pending_changes: Optional[Dict[str, Any]] = None
    pending_change_reason: Optional[str] = None
    pending_change_evidence_url: Optional[str] = None
    pending_change_evidence_filename: Optional[str] = None

    # Payment tracking
    payment_completed_at: Optional[datetime] = None
    payment_receipt_url: Optional[str] = None
    payment_receipt_filename: Optional[str] = None

    # Legal support escalation
    legal_support_status: Optional[str] = None
    legal_support_requested_at: Optional[datetime] = None
    legal_support_reason: Optional[str] = None
    legal_support_evidence_url: Optional[str] = None
    legal_support_evidence_filename: Optional[str] = None

    document_url: Optional[str] = None
    notes: Optional[str] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator("items", mode="before")
    @classmethod
    def _default_items(cls, v):
        return v or []


class SalesInvoiceListResponse(BaseModel):
    invoices: List[SalesInvoiceResponse]
    total: int
    skip: int
    limit: int


class SalesInvoiceWorkflowAction(BaseModel):
    """Operations/Master Admin review action on a sales invoice"""

    notes: Optional[str] = None


class SalesInvoiceApprovalRequest(BaseModel):
    """Submit an edit for the Operations -> Master Admin approval
    flow, mirroring purchase_orders' /request-approval."""

    edit_data: dict = Field(default_factory=dict)
    evidence_url: Optional[str] = None
    evidence_filename: Optional[str] = None
    reason: str


class SalesInvoiceReminderRequest(BaseModel):
    """Manual customer payment reminder request for a sales invoice,
    mirroring purchase_orders' ReminderRequest."""

    subject: Optional[str] = None
    body: Optional[str] = None
    scheduled_at: Optional[str] = None
