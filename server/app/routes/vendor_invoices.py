"""
Routes for Vendor Invoices — bills RECEIVED from a vendor (Accounts
Payable). The mirror of routes/sales_invoices.py (Accounts Receivable),
but deliberately leaner: no Draft/Sent/approval-workflow lifecycle (a
received bill either hasn't been paid yet or has), no PO linkage (not
every vendor bill has one), and no issuing-company snapshot fields
(we're the recipient here, not the issuer). Primarily populated via
/scan-pdf, which reads the vendor's own PDF and returns fields for the
frontend to fill the Add Vendor Invoice form with — nothing is saved
until the person reviews and submits via the normal create/update
routes below, same pattern as sales_invoices' scan flow.
"""
from datetime import datetime
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Form, File, UploadFile, Request
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import UnauthorizedFeature
from app.models import VendorInvoice, User
from app.services.access_control_service import AccessControlService
from app.schemas.vendor_invoice import (
    VendorInvoiceCreate,
    VendorInvoiceUpdate,
    VendorInvoiceResponse,
)
from app.utils.response import ResponseFormatter

VENDOR_INVOICE_NOT_FOUND_ERROR = "Vendor invoice not found"
VENDOR_INVOICE_FEATURE = "CREDIT_MANAGEMENT"  # same subscription gate as sales invoices

router = APIRouter(prefix="/vendor-invoices", tags=["Vendor Invoices"])


def _sync_tax_id_fields(data: dict) -> dict:
    """Dual-write helper for the vendor tax ID rollout (see migration
    n5c6d7e8f9g0_add_vendor_tax_id_fields.py). Keeps the old India-only
    vendor_gstin/vendor_pan columns and the new generic vendor_tax_id/
    vendor_tax_id_type columns in sync regardless of which pair the
    caller populated (old frontend still sending gstin/pan, or new
    frontend sending tax_id/tax_id_type), so both read paths agree until
    vendor_gstin/vendor_pan are dropped in a follow-up migration. Only
    touches keys already present in `data` — safe to call on a partial
    update dict.
    """
    gstin = data.get("vendor_gstin")
    pan = data.get("vendor_pan")
    tax_id = data.get("vendor_tax_id")
    tax_id_type = data.get("vendor_tax_id_type")

    if gstin:
        data["vendor_gstin"] = gstin.upper()
        if "vendor_tax_id" in data or "vendor_tax_id_type" in data or not tax_id:
            data["vendor_tax_id"] = gstin.upper()
            data["vendor_tax_id_type"] = "GSTIN"
    elif pan:
        data["vendor_pan"] = pan.upper()
        if "vendor_tax_id" in data or "vendor_tax_id_type" in data or not tax_id:
            data["vendor_tax_id"] = pan.upper()
            data["vendor_tax_id_type"] = "PAN"
    elif tax_id and tax_id_type:
        data["vendor_tax_id"] = tax_id.upper()
        data["vendor_tax_id_type"] = tax_id_type
        if tax_id_type == "GSTIN" and "vendor_gstin" in data:
            data["vendor_gstin"] = tax_id.upper()
        elif tax_id_type == "PAN" and "vendor_pan" in data:
            data["vendor_pan"] = tax_id.upper()

    return data


@router.post("/_ensure-table")
async def ensure_vendor_invoices_table(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """One-time fix for environments where `alembic upgrade head` didn't
    actually create this table (e.g. a production database whose
    alembic_version bookkeeping is out of sync with its real schema, with
    no Shell access available to fix it via `alembic stamp`/direct SQL).
    Creates the table directly via idempotent DDL if it's missing —
    every statement uses IF NOT EXISTS, so calling this when the table
    already exists is a safe no-op. Requires being logged in, but not any
    particular role, since it's non-destructive either way.
    """
    from sqlalchemy import text

    ddl = """
    CREATE TABLE IF NOT EXISTS vendor_invoices (
        id VARCHAR(36) NOT NULL,
        company_id VARCHAR(36),
        user_id VARCHAR(36) NOT NULL,
        vendor_name VARCHAR(255) NOT NULL,
        vendor_gstin VARCHAR(15),
        vendor_pan VARCHAR(10),
        vendor_tax_id VARCHAR(30),
        vendor_tax_id_type VARCHAR(20),
        vendor_email VARCHAR(255),
        vendor_phone VARCHAR(20),
        vendor_address TEXT,
        invoice_number VARCHAR(100) NOT NULL,
        invoice_date DATE NOT NULL,
        payment_due_date DATE NOT NULL,
        payment_terms VARCHAR(100),
        place_of_supply VARCHAR(100),
        currency VARCHAR(3) NOT NULL DEFAULT 'INR',
        items JSON,
        subtotal FLOAT NOT NULL DEFAULT 0,
        tax_breakdown JSON,
        tax_amount FLOAT NOT NULL DEFAULT 0,
        total FLOAT NOT NULL DEFAULT 0,
        balance_due FLOAT NOT NULL DEFAULT 0,
        status VARCHAR(50) DEFAULT 'Unpaid',
        archived BOOLEAN DEFAULT false,
        payment_completed_at TIMESTAMP,
        payment_receipt_url VARCHAR(500),
        payment_receipt_filename VARCHAR(255),
        document_url VARCHAR(500),
        document_filename VARCHAR(255),
        notes TEXT,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP,
        PRIMARY KEY (id),
        FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_vendor_invoice_company_status ON vendor_invoices (company_id, status);
    CREATE INDEX IF NOT EXISTS idx_vendor_invoice_number ON vendor_invoices (invoice_number);
    CREATE INDEX IF NOT EXISTS idx_vendor_invoice_due_date ON vendor_invoices (payment_due_date);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_id ON vendor_invoices (id);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_company_id ON vendor_invoices (company_id);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_user_id ON vendor_invoices (user_id);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_vendor_name ON vendor_invoices (vendor_name);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_vendor_gstin ON vendor_invoices (vendor_gstin);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_vendor_tax_id ON vendor_invoices (vendor_tax_id);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_invoice_number ON vendor_invoices (invoice_number);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_invoice_date ON vendor_invoices (invoice_date);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_payment_due_date ON vendor_invoices (payment_due_date);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_status ON vendor_invoices (status);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_archived ON vendor_invoices (archived);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_payment_completed_at ON vendor_invoices (payment_completed_at);
    CREATE INDEX IF NOT EXISTS ix_vendor_invoices_created_at ON vendor_invoices (created_at);
    """
    for statement in ddl.strip().split(";"):
        statement = statement.strip()
        if statement:
            await db.execute(text(statement))
    await db.commit()

    return ResponseFormatter.create_success(
        data={"table_ready": True},
        message="vendor_invoices table verified/created.",
    )


def get_utc_now():
    return datetime.utcnow()


def success_response(data=None, message="Success"):
    return ResponseFormatter.create_success(data=data, message=message)


def serialize_vendor_invoice(invoice: VendorInvoice) -> dict:
    return VendorInvoiceResponse.model_validate(invoice).model_dump(mode="json")


async def _get_owned_invoice(db: AsyncSession, invoice_id: str, user_id: str) -> Optional[VendorInvoice]:
    result = await db.execute(
        select(VendorInvoice).where(
            and_(VendorInvoice.id == invoice_id, VendorInvoice.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


@router.get("")
async def list_vendor_invoices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    include_archived: bool = Query(False),
):
    """List the current user's received vendor invoices, most recent first."""
    if not await AccessControlService.can_access_feature(current_user.id, VENDOR_INVOICE_FEATURE, db):
        raise UnauthorizedFeature("Invoice Management")

    conditions = [VendorInvoice.user_id == current_user.id]
    if not include_archived:
        conditions.append(VendorInvoice.archived == False)  # noqa: E712
    if status:
        conditions.append(VendorInvoice.status == status)
    if search:
        like = f"%{search}%"
        conditions.append(
            (VendorInvoice.invoice_number.ilike(like)) | (VendorInvoice.vendor_name.ilike(like))
        )

    count_result = await db.execute(
        select(func.count()).select_from(VendorInvoice).where(and_(*conditions))
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(VendorInvoice)
        .where(and_(*conditions))
        .order_by(VendorInvoice.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    invoices = result.scalars().all()

    return success_response(
        data={
            "invoices": [serialize_vendor_invoice(inv) for inv in invoices],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    )


@router.post("/scan-pdf")
async def scan_vendor_invoice_pdf(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Reads a vendor's own invoice PDF and extracts fields/items for the
    frontend to fill the Add Vendor Invoice form with — nothing is saved
    here. Unlike sales_invoices' scan, this reads the ISSUER's own
    letterhead details as the vendor (not a "Bill To" block, which on an
    incoming bill would just be our own company)."""
    if not await AccessControlService.can_access_feature(current_user.id, VENDOR_INVOICE_FEATURE, db):
        raise UnauthorizedFeature("Invoice Management")

    ALLOWED_SCAN_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")
    if not file.filename.lower().endswith(ALLOWED_SCAN_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Please upload a PDF or an image (.pdf, .jpg, .jpeg, .png)")

    from app.services.vendor_invoice_scan_service import extract_vendor_invoice_fields
    pdf_bytes = await file.read()
    result = extract_vendor_invoice_fields(pdf_bytes, filename=file.filename)

    return ResponseFormatter.create_success(data=result)


@router.post("")
async def create_vendor_invoice(
    payload: VendorInvoiceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Record a bill received from a vendor. Unlike sales invoices,
    invoice_number is always required and taken as-is — it's the
    vendor's own number, not something we generate."""
    if not await AccessControlService.can_access_feature(current_user.id, VENDOR_INVOICE_FEATURE, db):
        raise UnauthorizedFeature("Invoice Management")
    now = datetime.utcnow()

    tax_fields = _sync_tax_id_fields({
        "vendor_gstin": payload.vendor_gstin,
        "vendor_pan": payload.vendor_pan,
        "vendor_tax_id": payload.vendor_tax_id,
        "vendor_tax_id_type": payload.vendor_tax_id_type,
    })

    invoice = VendorInvoice(
        id=str(uuid4()),
        user_id=current_user.id,
        company_id=getattr(current_user, "company_id", None),

        vendor_name=payload.vendor_name,
        vendor_gstin=tax_fields.get("vendor_gstin"),
        vendor_pan=tax_fields.get("vendor_pan"),
        vendor_tax_id=tax_fields.get("vendor_tax_id"),
        vendor_tax_id_type=tax_fields.get("vendor_tax_id_type"),
        vendor_email=payload.vendor_email,
        vendor_phone=payload.vendor_phone,
        vendor_address=payload.vendor_address,

        invoice_number=payload.invoice_number.strip(),
        invoice_date=payload.invoice_date,
        payment_due_date=payload.payment_due_date,
        payment_terms=payload.payment_terms,

        place_of_supply=payload.place_of_supply,
        currency=payload.currency or "INR",

        items=[item.model_dump() for item in payload.items],

        subtotal=payload.subtotal or 0.0,
        tax_breakdown=payload.tax_breakdown,
        tax_amount=payload.tax_amount or 0.0,
        total=payload.total or 0.0,
        balance_due=payload.balance_due or payload.total or 0.0,

        status=payload.status or "Unpaid",
        notes=payload.notes,
        document_url=payload.document_url,
        document_filename=payload.document_filename,
        created_at=now,
        updated_at=now,
    )

    db.add(invoice)
    await db.commit()

    from app.utils.audit import log_audit
    await log_audit(
        db=db, user=current_user, action="VENDOR_INVOICE_CREATED",
        entity_obj=invoice, reason=f"Vendor invoice {invoice.invoice_number} from {invoice.vendor_name} recorded",
    )
    await db.commit()

    invoice = await _get_owned_invoice(db, invoice.id, current_user.id)
    return success_response(data=serialize_vendor_invoice(invoice), message="Vendor invoice recorded")


@router.get("/{invoice_id}")
async def get_vendor_invoice(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not await AccessControlService.can_access_feature(current_user.id, VENDOR_INVOICE_FEATURE, db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=VENDOR_INVOICE_NOT_FOUND_ERROR)
    return success_response(data=serialize_vendor_invoice(invoice))


@router.put("/{invoice_id}")
async def update_vendor_invoice(
    invoice_id: str,
    payload: VendorInvoiceUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not await AccessControlService.can_access_feature(current_user.id, VENDOR_INVOICE_FEATURE, db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=VENDOR_INVOICE_NOT_FOUND_ERROR)

    if invoice.status == "Paid":
        raise HTTPException(status_code=400, detail="This vendor invoice is already marked paid and can't be edited.")

    # NOTE: mode="python" (the default) — NOT mode="json". With "json",
    # Pydantic serializes date/datetime fields to ISO strings, which then
    # get assigned directly onto the SQLAlchemy model below via setattr,
    # bypassing any conversion back to a real date object. asyncpg
    # requires actual date objects for a DATE column and raises
    # "'str' object has no attribute 'toordinal'" on a plain string —
    # surfaced to the user as a misleading "Database service is
    # unavailable" error, even though the database itself is fine.
    update_data = payload.model_dump(exclude_unset=True, exclude={"items"})
    update_data = _sync_tax_id_fields(update_data)
    for field, value in update_data.items():
        if field in ("vendor_gstin", "vendor_pan", "vendor_tax_id") and value:
            value = value.upper()
        setattr(invoice, field, value)

    if payload.items is not None:
        invoice.items = [item.model_dump() for item in payload.items]

    invoice.updated_at = datetime.utcnow()
    await db.commit()
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)

    return success_response(data=serialize_vendor_invoice(invoice), message="Vendor invoice updated")


@router.post("/{invoice_id}/archive")
async def archive_vendor_invoice(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Toggle archive status, mirroring sales_invoices' archive endpoint."""
    if not await AccessControlService.can_access_feature(current_user.id, VENDOR_INVOICE_FEATURE, db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=VENDOR_INVOICE_NOT_FOUND_ERROR)

    invoice.archived = not invoice.archived
    invoice.updated_at = get_utc_now()

    from app.utils.audit import log_audit
    await log_audit(
        db=db, user=current_user,
        action="VENDOR_INVOICE_ARCHIVED" if invoice.archived else "VENDOR_INVOICE_UNARCHIVED",
        entity_obj=invoice,
    )
    await db.commit()
    await db.refresh(invoice)

    return success_response(data={"is_archived": invoice.archived}, message="Vendor invoice archive status updated")


@router.post("/{invoice_id}/mark-paid")
async def mark_vendor_invoice_paid(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Form(...),
    file: UploadFile = File(None),
):
    """Mark a vendor invoice as paid — i.e. record that WE paid THEM.
    Mirrors sales_invoices' mark-paid endpoint exactly, including the
    optional receipt upload (here, proof of our own payment/transfer)."""
    if not await AccessControlService.can_access_feature(current_user.id, VENDOR_INVOICE_FEATURE, db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=VENDOR_INVOICE_NOT_FOUND_ERROR)

    if invoice.payment_completed_at is not None:
        raise HTTPException(status_code=400, detail="Already marked paid")

    if file:
        from app.services.file_storage_service import store_uploaded_file

        filename = f"{uuid4()}_{file.filename}"
        file_bytes = await file.read()
        result = await store_uploaded_file(file_bytes, filename, file.content_type, "payment_receipts")
        invoice.payment_receipt_url = result["url"] if result["storage"] == "drive" else f"{settings.BASE_URL}{result['url']}"
        invoice.payment_receipt_filename = file.filename

    invoice.status = "Paid"
    invoice.payment_completed_at = get_utc_now()
    invoice.updated_at = get_utc_now()

    from app.utils.audit import log_audit
    await log_audit(
        db=db, user=current_user, action="VENDOR_INVOICE_MARKED_PAID",
        entity_obj=invoice, reason=reason or f"Vendor invoice {invoice.invoice_number} marked as paid",
    )
    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_vendor_invoice(invoice), message="Vendor invoice marked as paid successfully")


@router.post("/{invoice_id}/upload-document")
async def upload_vendor_invoice_document(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Attach (or replace) the vendor's own scanned invoice/PDF on an
    existing record — separate from the mark-paid receipt, which is
    proof of OUR payment rather than the source document itself."""
    if not await AccessControlService.can_access_feature(current_user.id, VENDOR_INVOICE_FEATURE, db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=VENDOR_INVOICE_NOT_FOUND_ERROR)

    from app.services.file_storage_service import store_uploaded_file

    filename = f"{uuid4()}_{file.filename}"
    file_bytes = await file.read()
    result = await store_uploaded_file(file_bytes, filename, file.content_type, "vendor_invoices")
    invoice.document_url = result["url"] if result["storage"] == "drive" else f"{settings.BASE_URL}{result['url']}"
    invoice.document_filename = file.filename
    invoice.updated_at = get_utc_now()

    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_vendor_invoice(invoice), message="Document uploaded")


@router.delete("/{invoice_id}", status_code=204)
async def delete_vendor_invoice(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not await AccessControlService.can_access_feature(current_user.id, VENDOR_INVOICE_FEATURE, db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=VENDOR_INVOICE_NOT_FOUND_ERROR)

    await db.delete(invoice)
    await db.commit()
