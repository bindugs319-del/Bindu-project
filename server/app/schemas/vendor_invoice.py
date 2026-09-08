"""
Pydantic schemas for Vendor Invoices — bills RECEIVED from a vendor
(Accounts Payable), the mirror of sales_invoice.py (Accounts
Receivable). Deliberately simpler than SalesInvoice's schema: no
Draft/Sent workflow (a received bill either hasn't been paid yet or
has), no Bill To/Ship To/LUT/SEZ fields (those describe things WE do as
an issuer, not relevant when we're just recording someone else's bill),
and no PO reference (not every vendor bill has one).
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime

VALID_STATUSES = ["Unpaid", "Paid", "Overdue", "Cancelled"]


def _blank_to_none(v):
    """Same rationale as sales_invoice.py's version: an empty HTML date
    input submits "" rather than omitting the key, which Pydantic can't
    parse as a date — normalize that to None before validation runs."""
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class VendorInvoiceItem(BaseModel):
    """A single line item — same shape as SalesInvoiceItem, stored as
    one entry in the invoice's `items` JSON array."""
    desc: str = Field(..., min_length=1)
    hsn: Optional[str] = None
    qty: float = Field(default=1.0, gt=0)
    rate: float = Field(..., ge=0)
    amount: float = Field(..., ge=0)


class VendorInvoiceCreate(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=255)
    vendor_gstin: Optional[str] = Field(None, min_length=15, max_length=15)
    vendor_pan: Optional[str] = Field(None, min_length=10, max_length=10)
    vendor_email: Optional[str] = Field(None, max_length=255)
    vendor_phone: Optional[str] = Field(None, max_length=20)
    vendor_address: Optional[str] = None

    invoice_number: str = Field(..., min_length=1, max_length=100)
    invoice_date: date
    payment_due_date: date
    payment_terms: Optional[str] = None

    place_of_supply: Optional[str] = None
    currency: Optional[str] = "INR"

    subtotal: Optional[float] = 0.0
    tax_breakdown: Optional[Dict[str, Any]] = None
    tax_amount: Optional[float] = 0.0
    total: Optional[float] = 0.0
    balance_due: Optional[float] = 0.0

    status: Optional[str] = "Unpaid"
    notes: Optional[str] = None
    document_url: Optional[str] = None
    document_filename: Optional[str] = None

    items: List[VendorInvoiceItem] = Field(default_factory=list)

    _blank_payment_terms = field_validator("payment_terms", mode="before")(_blank_to_none)
    _blank_vendor_gstin = field_validator("vendor_gstin", mode="before")(_blank_to_none)
    _blank_vendor_pan = field_validator("vendor_pan", mode="before")(_blank_to_none)
    _blank_place_of_supply = field_validator("place_of_supply", mode="before")(_blank_to_none)
    _blank_notes = field_validator("notes", mode="before")(_blank_to_none)
    _blank_document_url = field_validator("document_url", mode="before")(_blank_to_none)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v):
        if v and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class VendorInvoiceUpdate(BaseModel):
    """Partial update — every field optional. `items`, if provided,
    fully replaces the invoice's existing items array."""
    vendor_name: Optional[str] = None
    vendor_gstin: Optional[str] = Field(None, min_length=15, max_length=15)
    vendor_pan: Optional[str] = Field(None, min_length=10, max_length=10)
    vendor_email: Optional[str] = Field(None, max_length=255)
    vendor_phone: Optional[str] = Field(None, max_length=20)
    vendor_address: Optional[str] = None

    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    payment_due_date: Optional[date] = None
    payment_terms: Optional[str] = None

    place_of_supply: Optional[str] = None
    currency: Optional[str] = None

    subtotal: Optional[float] = None
    tax_breakdown: Optional[Dict[str, Any]] = None
    tax_amount: Optional[float] = None
    total: Optional[float] = None
    balance_due: Optional[float] = None

    status: Optional[str] = None
    notes: Optional[str] = None
    document_url: Optional[str] = None
    document_filename: Optional[str] = None

    items: Optional[List[VendorInvoiceItem]] = None

    _blank_invoice_date = field_validator("invoice_date", mode="before")(_blank_to_none)
    _blank_payment_due_date = field_validator("payment_due_date", mode="before")(_blank_to_none)
    _blank_payment_terms = field_validator("payment_terms", mode="before")(_blank_to_none)
    _blank_vendor_gstin = field_validator("vendor_gstin", mode="before")(_blank_to_none)
    _blank_vendor_pan = field_validator("vendor_pan", mode="before")(_blank_to_none)
    _blank_place_of_supply = field_validator("place_of_supply", mode="before")(_blank_to_none)
    _blank_notes = field_validator("notes", mode="before")(_blank_to_none)
    _blank_document_url = field_validator("document_url", mode="before")(_blank_to_none)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v):
        if v and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class VendorInvoiceResponse(BaseModel):
    id: str
    company_id: Optional[str] = None
    user_id: str

    vendor_name: str
    vendor_gstin: Optional[str] = None
    vendor_pan: Optional[str] = None
    vendor_email: Optional[str] = None
    vendor_phone: Optional[str] = None
    vendor_address: Optional[str] = None

    invoice_number: str
    invoice_date: date
    payment_due_date: date
    payment_terms: Optional[str] = None

    place_of_supply: Optional[str] = None
    currency: str

    items: Optional[List[Dict[str, Any]]] = None

    subtotal: float
    tax_breakdown: Optional[Dict[str, Any]] = None
    tax_amount: float
    total: float
    balance_due: float

    status: str
    archived: bool

    payment_completed_at: Optional[datetime] = None
    payment_receipt_url: Optional[str] = None
    payment_receipt_filename: Optional[str] = None

    document_url: Optional[str] = None
    document_filename: Optional[str] = None
    notes: Optional[str] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VendorInvoiceMarkPaid(BaseModel):
    """Mirrors the sales invoice / PO mark-paid flow: an optional receipt
    file is handled separately as a multipart upload in the route, this
    just carries the non-file fields."""
    payment_date: Optional[datetime] = None
    notes: Optional[str] = None
