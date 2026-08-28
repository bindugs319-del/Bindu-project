"""
Routes for Sales Invoices — the GST tax-invoice workflow (company +
customer details, bill-to/ship-to, tax breakdown, line items). Line
items are stored as a JSON array directly on the sales_invoices row,
matching the supervisor's spec sheet. Separate from the simpler
Invoice model used by app/routes/invoices.py.
"""
import re
from datetime import datetime
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Form, File, UploadFile, Request
from fastapi.responses import Response
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import UnauthorizedFeature
from app.models import SalesInvoice, User
from app.services.access_control_service import AccessControlService
from app.services.business_profile_service import BusinessProfileService
from app.schemas.sales_invoice import (
    SalesInvoiceCreate,
    SalesInvoiceUpdate,
    SalesInvoiceResponse,
    SalesInvoiceWorkflowAction,
    SalesInvoiceReminderRequest,
    SalesInvoiceApprovalRequest,
)
from app.services.sales_invoice_pdf import build_sales_invoice_pdf
from app.utils.response import ResponseFormatter

SALES_INVOICE_NOT_FOUND_ERROR = "Sales invoice not found"


def get_utc_now():
    """Get current UTC time as a naive datetime, matching the plain
    (timezone-naive) DateTime columns on SalesInvoice's workflow fields."""
    return datetime.utcnow()


def _require_role(current_user, allowed):
    role = str(getattr(current_user.role, "value", current_user.role) or "").upper()
    if role not in allowed:
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action")


router = APIRouter(prefix="/sales-invoices", tags=["Sales Invoices"])

_COMPANY_SUFFIXES = {
    "pvt", "pvt.", "private", "ltd", "ltd.", "limited",
    "llp", "inc", "inc.", "incorporated", "co", "co.", "company", "corp", "corp.",
}


def _company_initials(name: Optional[str]) -> str:
    """Derive a short prefix from the company name for invoice numbers,
    e.g. "Preflex Solutions Pvt Ltd" -> "PS" (matching the format on the
    reference sample invoice: PS/INV/26/07/643)."""
    if not name:
        return "CO"

    words = [w for w in re.split(r"\s+", name.strip()) if w]
    significant = [w for w in words if w.lower().strip(".") not in _COMPANY_SUFFIXES]
    if not significant:
        significant = words
    if not significant:
        return "CO"

    initials = "".join(w[0].upper() for w in significant[:2] if w[0].isalpha())
    return initials or "CO"


def _format_invoice_number(seq: int, company_name: Optional[str] = None) -> str:
    """e.g. PS/INV/26/07/643 — company initials / INV / 2-digit year /
    2-digit month / running sequence."""
    now = datetime.utcnow()
    prefix = _company_initials(company_name)
    return f"{prefix}/INV/{now.strftime('%y')}/{now.strftime('%m')}/{seq}"


def _format_po_number(seq: int) -> str:
    return f"PO-{seq:04d}"


def success_response(data=None, message="Success"):
    return ResponseFormatter.create_success(data=data, message=message)


def serialize_sales_invoice(invoice: SalesInvoice) -> dict:
    """Convert a SalesInvoice ORM object into a JSON-safe dict. Always
    go through this rather than returning the raw ORM object directly —
    see the equivalent note in routes/invoices.py for why."""
    return SalesInvoiceResponse.model_validate(invoice).model_dump(mode="json")


async def _get_owned_invoice(db: AsyncSession, invoice_id: str, user_id: str) -> Optional[SalesInvoice]:
    result = await db.execute(
        select(SalesInvoice).where(
            and_(SalesInvoice.id == invoice_id, SalesInvoice.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


@router.get("")
async def list_sales_invoices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    include_archived: bool = Query(False),
):
    """List the current user's sales invoices, most recent first."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")

    conditions = [SalesInvoice.user_id == current_user.id]
    if not include_archived:
        conditions.append(SalesInvoice.archived == False)  # noqa: E712
    if status:
        conditions.append(SalesInvoice.status == status)
    if search:
        like = f"%{search}%"
        conditions.append(
            (SalesInvoice.invoice_number.ilike(like)) | (SalesInvoice.counterparty_name.ilike(like))
        )

    count_result = await db.execute(
        select(func.count()).select_from(SalesInvoice).where(and_(*conditions))
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(SalesInvoice)
        .where(and_(*conditions))
        .order_by(SalesInvoice.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    invoices = result.scalars().all()

    return success_response(
        data={
            "invoices": [serialize_sales_invoice(inv) for inv in invoices],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    )


@router.post("/{invoice_id}/upload-document")
async def upload_sales_invoice_document(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Attach a supporting document (PDF/image) to an existing sales
    invoice, mirroring the purchase_orders document upload."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)

    from app.services.file_storage_service import store_uploaded_file

    filename = f"{uuid4()}_{file.filename}"
    file_bytes = await file.read()
    result = await store_uploaded_file(file_bytes, filename, file.content_type, "sales_invoices")
    invoice.document_url = result["url"]
    invoice.updated_at = get_utc_now()

    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_sales_invoice(invoice), message="Document uploaded")


@router.post("/{invoice_id}/archive")
async def archive_sales_invoice(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Toggle archive status for a sales invoice, mirroring the
    purchase order archive endpoint."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)

    invoice.archived = not invoice.archived
    invoice.updated_at = get_utc_now()

    from app.utils.audit import log_audit
    await log_audit(
        db=db, user=current_user,
        action="SALES_INVOICE_ARCHIVED" if invoice.archived else "SALES_INVOICE_UNARCHIVED",
        entity_obj=invoice,
    )
    await db.commit()
    await db.refresh(invoice)

    return success_response(data={"is_archived": invoice.archived}, message="Sales invoice archive status updated")


@router.post("/{invoice_id}/mark-paid")
async def mark_sales_invoice_paid(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Form(...),
    file: UploadFile = File(None),
):
    """Mark a sales invoice as paid (immutable financial action),
    mirroring purchase_orders' mark-paid endpoint."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)

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
        db=db, user=current_user, action="SALES_INVOICE_MARKED_PAID",
        entity_obj=invoice, reason=reason or f"Invoice {invoice.invoice_number} marked as paid",
    )
    await db.commit()
    await db.refresh(invoice)

    # Notify the submitter (self-confirmation) and their company's admins
    try:
        from app.services.notification_service import NotificationService
        recipients_stmt = select(User.email).where(
            (User.company_id == current_user.company_id) &
            (User.is_active == True) &
            (User.role.in_(["MASTER_ADMIN", "COMPANY_ADMIN"]))
        )
        recipients_res = await db.execute(recipients_stmt)
        recipient_emails = {r[0] for r in recipients_res.all() if r[0]}
        if current_user.email:
            recipient_emails.add(current_user.email)
        for email in recipient_emails:
            await NotificationService.send(
                db, email,
                title="Invoice Marked Paid",
                message=f"Invoice {invoice.invoice_number} was marked as paid.\n\nReason: {reason or 'N/A'}",
                ntype="INVOICE",
                action_url="/invoices",
            )
    except Exception as e:
        print(f"[MARK_PAID] Failed to send notification: {e}")

    return success_response(data=serialize_sales_invoice(invoice), message="Invoice marked as paid successfully")


@router.post("/{invoice_id}/send-reminder")
async def send_sales_invoice_reminder(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    req: SalesInvoiceReminderRequest = SalesInvoiceReminderRequest(),
):
    """Send or schedule a payment reminder email to the customer for a
    sales invoice. Accepts an optional custom subject/body (from the
    reminder modal) and an optional scheduled_at to send later instead
    of immediately, mirroring purchase_orders' send-reminder endpoint."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)

    to_email = (invoice.counterparty_email or "").strip()
    if not to_email:
        raise HTTPException(status_code=400, detail="No customer email configured for this invoice")

    due_date_str = invoice.payment_due_date.isoformat() if invoice.payment_due_date else "N/A"
    amount_str = f"₹{invoice.total:,.2f}"

    subject = req.subject or f"Payment Reminder: Invoice {invoice.invoice_number} due on {due_date_str}"
    body = req.body or (
        f"Dear {invoice.counterparty_name or 'Customer'},\n\n"
        f"This is a reminder that Invoice {invoice.invoice_number} for amount {amount_str} "
        f"is due on {due_date_str}. Please arrange payment at the earliest.\n\n"
        f"Regards,\n{invoice.company_name or 'Your Vendor'}"
    )

    if req.scheduled_at:
        try:
            s = str(req.scheduled_at).replace("Z", "+00:00")
            if "T" in s and "+" not in s and s.count(":") == 1:
                s += ":00"
            sched_dt = datetime.fromisoformat(s)
            if sched_dt.tzinfo:
                from datetime import timezone
                sched_dt = sched_dt.astimezone(timezone.utc).replace(tzinfo=None)

            from app.models import ScheduledReminder
            sr = ScheduledReminder(
                id=str(uuid4()),
                sales_invoice_id=invoice.id,
                user_id=current_user.id,
                subject=subject,
                body=body,
                scheduled_at=sched_dt,
            )
            db.add(sr)
            await db.commit()

            from app.utils.audit import log_audit
            await log_audit(
                db=db, user=current_user, action="SALES_INVOICE_REMINDER_SCHEDULED",
                entity_obj=invoice, reason=f"Scheduled for {sched_dt.isoformat()}",
            )
            return success_response(message=f"Reminder scheduled for {sched_dt.isoformat()}")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid scheduled_at format")

    from app.services.email_service import EmailService, send_email_with_attachment
    from app.utils.audit import log_audit

    # Send NOW — optionally with a formal legal-notice PDF attached,
    # mirroring purchase_orders' send-reminder endpoint exactly.
    email_sent = False
    try:
        if req.include_legal_notice:
            import os
            from app.services.legal_notice_service import generate_legal_notice_pdf
            from app.utils.uploads import get_upload_subdir

            temp_dir_path = get_upload_subdir("temp")
            pdf_path = str(temp_dir_path / f"legal_notice_invoice_{invoice_id}.pdf")
            invoice_data = {
                "vendor": invoice.counterparty_name,
                "po_number": invoice.invoice_number,
                "amount": invoice.total,
                "due_date": str(invoice.payment_due_date) if invoice.payment_due_date else "N/A",
                "company_name": invoice.company_name or "Company",
            }
            generate_legal_notice_pdf(invoice_data, pdf_path, req.legal_notice_content)

            email_sent = await send_email_with_attachment(
                to_email=to_email,
                subject=subject,
                body=body,
                attachment_path=pdf_path,
                attachment_name=f"Legal_Notice_{invoice.invoice_number}.pdf",
            )

            if os.path.exists(pdf_path):
                os.remove(pdf_path)

            invoice.legal_notice_sent_at = get_utc_now()
            await log_audit(
                db=db, user=current_user, action="SALES_INVOICE_LEGAL_NOTICE_SENT",
                entity_obj=invoice, reason=f"To: {to_email}",
            )
        else:
            email_sent = await EmailService().send_email(to_email, subject, body)
            await log_audit(
                db=db, user=current_user, action="SALES_INVOICE_REMINDER_SENT",
                entity_obj=invoice, reason=f"Reminder sent to {to_email}" if email_sent else f"Reminder NOT delivered (email not configured) — intended for {to_email}",
            )

        invoice.updated_at = get_utc_now()
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send reminder email: {str(e)}")

    if not email_sent:
        # send_email() / send_email_with_attachment() return False (rather
        # than raising) specifically when no real email provider is
        # configured — see EmailService. Reporting success here anyway
        # would silently convince the user a customer was reminded when
        # nothing was actually sent.
        return success_response(
            message="Reminder logged, but no email was actually sent — email delivery isn't configured on this server yet. Ask your admin to set up BREVO_API_KEY.",
        )

    return success_response(
        message=f"Reminder with Legal Notice sent to {to_email}" if req.include_legal_notice else f"Reminder sent to {to_email}"
    )


@router.post("/{invoice_id}/send-to-legal-support")
async def send_sales_invoice_to_legal_support(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Form(""),
    file: UploadFile = File(None),
):
    """Escalate a sales invoice to the legal/operations team with a
    reason and optional evidence file, mirroring purchase_orders'
    send-to-legal-support endpoint."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)

    evidence_url = None
    evidence_filename = None
    if file:
        from app.services.file_storage_service import store_uploaded_file

        file_ext = file.filename.split(".")[-1] if file.filename else "pdf"
        fname = f"{uuid4()}.{file_ext}"
        file_bytes = await file.read()
        result = await store_uploaded_file(file_bytes, fname, file.content_type, "legal_evidence")
        evidence_url = result["url"] if result["storage"] == "drive" else f"{settings.BASE_URL}{result['url']}"
        evidence_filename = file.filename

    invoice.legal_support_status = "PENDING_LEGAL"
    invoice.legal_support_requested_at = get_utc_now()
    invoice.legal_support_reason = reason
    invoice.legal_support_evidence_url = evidence_url
    invoice.legal_support_evidence_filename = evidence_filename
    invoice.legal_support_requested_by = current_user.email
    invoice.updated_at = get_utc_now()

    from app.utils.audit import log_audit
    from app.services.notification_service import NotificationService
    await log_audit(
        db=db, user=current_user, action="SALES_INVOICE_LEGAL_SUPPORT_REQUEST",
        entity_obj=invoice, reason=reason,
    )
    await NotificationService.send_to_role(
        db=db, role="OPERATIONS",
        title=f"Legal Support Requested - {invoice.invoice_number}",
        message=f"User {current_user.email} requested legal support.\n\nInvoice: {invoice.invoice_number}\nCustomer: {invoice.counterparty_name}\nAmount: ₹{invoice.total}\n\nPlease review.",
        action_url="/dashboard/operation",
    )
    await NotificationService.send(
        db, current_user.email,
        f"Legal Support Requested - {invoice.invoice_number}",
        f"Your legal support request for Invoice {invoice.invoice_number} has been submitted. The team will review and contact you shortly.",
    )
    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_sales_invoice(invoice), message="Legal support request submitted")


@router.get("/pending-summary")
async def get_pending_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Count and total outstanding amount for invoices not yet fully
    paid (status = Draft, Sent, or Overdue) — used for the Dashboard's
    "Pending Invoices" card."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")

    pending_statuses = ["Draft", "Sent", "Overdue"]
    conditions = [
        SalesInvoice.user_id == current_user.id,
        SalesInvoice.archived == False,  # noqa: E712
        SalesInvoice.status.in_(pending_statuses),
    ]

    result = await db.execute(
        select(func.count(), func.coalesce(func.sum(SalesInvoice.balance_due), 0.0))
        .select_from(SalesInvoice)
        .where(and_(*conditions))
    )
    count, total_due = result.one()

    return success_response(
        data={"count": count, "total_due": float(total_due)}
    )


@router.get("/next-number")
async def get_next_numbers(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Preview the next auto-generated invoice number and PO number,
    without consuming them. The actual number is only reserved when the
    invoice is created (see create_sales_invoice) — if the user cancels
    the form, no gap is introduced."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    profile = await BusinessProfileService.get_or_create_profile(current_user.id, db)
    await db.commit()
    return success_response(
        data={
            "invoice_number": _format_invoice_number(profile.next_invoice_seq, profile.registered_name or profile.name),
            "po_number": _format_po_number(profile.next_po_seq),
        }
    )


@router.post("/scan-pdf")
async def scan_sales_invoice_pdf(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Reads an uploaded invoice PDF and extracts fields for preview only —
    nothing is saved here. Mirrors /purchase-orders/scan-pdf."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")

    ALLOWED_SCAN_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")
    if not file.filename.lower().endswith(ALLOWED_SCAN_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Please upload a PDF or an image (.pdf, .jpg, .jpeg, .png)")

    from app.services.invoice_pdf_scan_service import extract_invoice_fields
    pdf_bytes = await file.read()
    result = extract_invoice_fields(pdf_bytes, filename=file.filename)

    will_update = False
    existing_invoice_id = None
    invoice_number = (result.get("fields") or {}).get("invoice_number")
    if invoice_number:
        stmt = select(SalesInvoice).where(
            SalesInvoice.user_id == current_user.id,
            SalesInvoice.invoice_number == invoice_number,
            SalesInvoice.archived == False,  # noqa: E712
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            will_update = True
            existing_invoice_id = existing.id

    return ResponseFormatter.create_success(data={
        **result,
        "will_update_existing": will_update,
        "existing_invoice_id": existing_invoice_id,
    })


@router.post("/import-pdf")
async def import_sales_invoice_pdf(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    invoice_number: str = Form(...),
    counterparty_name: str = Form(...),
    counterparty_gstin: str = Form(None),
    counterparty_email: str = Form(None),
    counterparty_phone: str = Form(None),
    subtotal: float = Form(0),
    tax_amount: float = Form(0),
    total: float = Form(0),
    invoice_date: str = Form(...),
    payment_due_date: str = Form(...),
):
    """Confirms a scanned invoice PDF's fields and either updates the
    matching open invoice for this user, or creates a new one if no
    invoice with that number exists yet. Mirrors /purchase-orders/import-pdf.
    Line items aren't extracted from the PDF, so a matched invoice keeps
    its existing items untouched, and a newly created one starts with none."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")

    try:
        invoice_date_obj = datetime.strptime(invoice_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invoice date could not be parsed; please re-check it in the preview.")
    try:
        due_date_obj = datetime.strptime(payment_due_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Due date could not be parsed; please re-check it in the preview.")

    gstin_norm = counterparty_gstin.strip().upper() if counterparty_gstin else None

    stmt = select(SalesInvoice).where(
        SalesInvoice.user_id == current_user.id,
        SalesInvoice.invoice_number == invoice_number,
        SalesInvoice.archived == False,  # noqa: E712
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        if existing.status == "Paid":
            raise HTTPException(status_code=400, detail=f"Invoice {invoice_number} is already paid; cannot update it via scan.")
        existing.counterparty_name = counterparty_name
        if gstin_norm:
            existing.counterparty_gstin = gstin_norm
        if counterparty_email:
            existing.counterparty_email = counterparty_email
        if counterparty_phone:
            existing.counterparty_phone = counterparty_phone
        if subtotal:
            existing.subtotal = subtotal
        if tax_amount:
            existing.tax_amount = tax_amount
        if total:
            existing.total = total
        existing.invoice_date = invoice_date_obj
        existing.payment_due_date = due_date_obj
        existing.updated_at = datetime.utcnow()
        await db.commit()
        from app.utils.audit import log_audit
        await log_audit(
            db=db, user=current_user, action="SALES_INVOICE_UPDATED",
            entity_obj=existing, reason=f"Sales invoice {invoice_number} updated from scanned PDF",
        )
        await db.commit()
        return ResponseFormatter.create_success(
            data={"id": existing.id, "action": "updated"},
            message=f"Existing invoice {invoice_number} updated from scanned PDF",
        )

    profile = await BusinessProfileService.get_or_create_profile(current_user.id, db)
    now = datetime.utcnow()
    invoice = SalesInvoice(
        id=str(uuid4()),
        user_id=current_user.id,
        company_id=getattr(current_user, "company_id", None),
        company_name=profile.registered_name or profile.name,
        company_address=profile.address,
        company_gstin=profile.gstin,
        company_pan=profile.pan,
        cin=profile.cin,
        msme_no=profile.msme_no,
        bank_account_name=profile.bank_account_name,
        bank_account_number=profile.bank_account_number,
        bank_ifsc=profile.bank_ifsc,
        bank_name=profile.bank_name,
        bank_upi_id=profile.bank_upi_id,
        invoice_number=invoice_number,
        invoice_date=invoice_date_obj,
        payment_due_date=due_date_obj,
        counterparty_name=counterparty_name,
        counterparty_gstin=gstin_norm,
        counterparty_email=counterparty_email,
        counterparty_phone=counterparty_phone,
        country="IN",
        currency="INR",
        exchange_rate=1.0,
        items=[],
        subtotal=subtotal or 0.0,
        tax_amount=tax_amount or 0.0,
        total=total or 0.0,
        balance_due=total or 0.0,
        status="Draft",
        created_at=now,
        updated_at=now,
    )
    db.add(invoice)
    await db.commit()
    from app.utils.audit import log_audit
    await log_audit(
        db=db, user=current_user, action="SALES_INVOICE_CREATED",
        entity_obj=invoice, reason=f"Sales invoice {invoice_number} created from scanned PDF",
    )
    await db.commit()
    return ResponseFormatter.create_success(
        data={"id": invoice.id, "action": "created"},
        message=f"New invoice {invoice_number} created from scanned PDF",
    )


@router.post("")
async def create_sales_invoice(
    payload: SalesInvoiceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new sales invoice.

    If invoice_number / po_number are left blank, they're auto-generated
    from the user's saved company profile's running counters, which are
    incremented atomically as part of this same commit. Company details
    (name, address, GSTIN, PAN, CIN, MSME no) are always taken from the
    profile too — the invoice keeps a snapshot of them as they stood at
    creation time, regardless of what the client sends. Line items are
    stored as a plain JSON array on the row.
    """
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    now = datetime.utcnow()

    profile = await BusinessProfileService.get_or_create_profile(current_user.id, db)

    invoice_number = payload.invoice_number.strip() if payload.invoice_number else ""
    if not invoice_number:
        invoice_number = _format_invoice_number(profile.next_invoice_seq, profile.registered_name or profile.name)
        profile.next_invoice_seq += 1

    po_number = payload.po_number
    if payload.po_number is not None and not payload.po_number.strip():
        po_number = _format_po_number(profile.next_po_seq)
        profile.next_po_seq += 1

    invoice = SalesInvoice(
        id=str(uuid4()),
        user_id=current_user.id,
        company_id=getattr(current_user, "company_id", None),

        company_name=profile.registered_name or profile.name,
        company_address=profile.address,
        company_gstin=profile.gstin,
        company_pan=profile.pan,
        cin=profile.cin,
        msme_no=profile.msme_no,

        bank_account_name=profile.bank_account_name,
        bank_account_number=profile.bank_account_number,
        bank_ifsc=profile.bank_ifsc,
        bank_name=profile.bank_name,
        bank_upi_id=profile.bank_upi_id,

        invoice_number=invoice_number,
        invoice_date=payload.invoice_date,
        payment_due_date=payload.payment_due_date,
        payment_terms=payload.payment_terms,

        po_number=po_number,
        po_date=payload.po_date,
        expected_delivery_date=payload.expected_delivery_date,

        counterparty_name=payload.counterparty_name,
        counterparty_gstin=payload.counterparty_gstin.upper() if payload.counterparty_gstin else None,
        counterparty_pan=payload.counterparty_pan.upper() if payload.counterparty_pan else None,
        counterparty_email=payload.counterparty_email,
        counterparty_phone=payload.counterparty_phone,

        bill_to=payload.bill_to.model_dump() if payload.bill_to else None,
        ship_to=payload.ship_to.model_dump() if payload.ship_to else None,

        country=payload.country or "IN",
        currency=payload.currency or "INR",
        exchange_rate=payload.exchange_rate or 1.0,

        lut_arn=payload.lut_arn,
        lut_filing_date=payload.lut_filing_date,
        place_of_supply=payload.place_of_supply,
        is_sez_export=bool(payload.is_sez_export),
        reverse_charge=bool(payload.reverse_charge),
        eway_bill_number=payload.eway_bill_number,

        items=[item.model_dump() for item in payload.items],

        subtotal=payload.subtotal or 0.0,
        discount_amount=payload.discount_amount or 0.0,
        tax_breakdown=payload.tax_breakdown.model_dump() if payload.tax_breakdown else None,
        tax_amount=payload.tax_amount or 0.0,
        round_off=payload.round_off or 0.0,
        total=payload.total or 0.0,
        balance_due=payload.balance_due or 0.0,

        status=payload.status or "Draft",
        notes=payload.notes,
        document_url=payload.document_url,
        created_at=now,
        updated_at=now,
    )

    db.add(invoice)
    await db.commit()

    from app.utils.audit import log_audit
    await log_audit(
        db=db, user=current_user, action="SALES_INVOICE_CREATED",
        entity_obj=invoice, reason=f"Sales invoice {invoice.invoice_number} created",
    )
    await db.commit()

    invoice = await _get_owned_invoice(db, invoice.id, current_user.id)
    return success_response(data=serialize_sales_invoice(invoice), message="Sales invoice created")


@router.get("/workflow/pending-operations")
async def list_sales_invoices_pending_operations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Invoice edits awaiting Operations Truth Check."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    _require_role(current_user, ["OPERATIONS", "OPERATION", "MASTER_ADMIN"])
    result = await db.execute(
        select(SalesInvoice).where(SalesInvoice.workflow_status == "Pending Operations Review").order_by(SalesInvoice.updated_at.desc())
    )
    invoices = result.scalars().all()
    return success_response(data=[serialize_sales_invoice(i) for i in invoices])


@router.get("/workflow/pending-master")
async def list_sales_invoices_pending_master(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Invoice edits verified by Operations, awaiting Master Admin
    final approval."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    _require_role(current_user, ["MASTER_ADMIN"])
    result = await db.execute(
        select(SalesInvoice).where(SalesInvoice.workflow_status == "Pending Master Admin Approval").order_by(SalesInvoice.updated_at.desc())
    )
    invoices = result.scalars().all()
    return success_response(data=[serialize_sales_invoice(i) for i in invoices])


@router.get("/{invoice_id}")
async def get_sales_invoice(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)
    return success_response(data=serialize_sales_invoice(invoice))


@router.get("/{invoice_id}/pdf")
async def download_sales_invoice_pdf(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Generate and stream the invoice as a PDF, in a tax-invoice layout.

    Uses the company snapshot already stored on the invoice row — no
    separate profile lookup needed.
    """
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)

    pdf_bytes = build_sales_invoice_pdf(invoice)

    filename = f"{invoice.invoice_number or invoice.id}.pdf".replace("/", "-")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/{invoice_id}")
async def update_sales_invoice(
    invoice_id: str,
    payload: SalesInvoiceUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Normal edit — applies changes immediately. For edits that need
    Operations/Master Admin sign-off, the frontend instead uses
    /upload-evidence + /request-approval (mirroring purchase_orders'
    EditPOModal's "Submit for internal approval flow" checkbox)."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)

    update_data = payload.model_dump(exclude_unset=True, exclude={"items"}, mode="json")
    for field, value in update_data.items():
        if field in ("counterparty_gstin", "counterparty_pan") and value:
            value = value.upper()
        setattr(invoice, field, value)

    if payload.items is not None:
        invoice.items = [item.model_dump() for item in payload.items]

    invoice.updated_at = datetime.utcnow()
    await db.commit()
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)

    return success_response(data=serialize_sales_invoice(invoice), message="Sales invoice updated")


@router.post("/{invoice_id}/upload-evidence")
async def upload_sales_invoice_evidence(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Upload an evidence file for an edit-approval request, returning
    its URL — step 1 of the two-step flow, mirroring purchase_orders'
    generic /upload/evidence endpoint."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)

    from app.services.file_storage_service import store_uploaded_file

    filename = f"{uuid4()}_{file.filename}"
    file_bytes = await file.read()
    result = await store_uploaded_file(file_bytes, filename, file.content_type, "sales_invoice_evidence")

    return success_response(data={
        "url": result["url"],
        "filename": file.filename,
    })


@router.post("/{invoice_id}/request-approval")
async def request_sales_invoice_approval(
    invoice_id: str,
    payload: SalesInvoiceApprovalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Step 2 — submit an edit for approval instead of applying it
    immediately: Operations does a Truth Check, then Master Admin gives
    final approval (which applies edit_data), mirroring
    purchase_orders' /request-approval + WorkflowService.start_po_approval."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)

    invoice.pending_changes = payload.edit_data
    invoice.pending_change_reason = payload.reason
    invoice.pending_change_evidence_url = payload.evidence_url
    invoice.pending_change_evidence_filename = payload.evidence_filename
    invoice.approval_status = "PENDING_APPROVAL"
    invoice.workflow_status = "Pending Operations Review"
    invoice.operations_reviewed_by = None
    invoice.operations_reviewed_at = None
    invoice.operations_notes = None
    invoice.master_approved_by = None
    invoice.master_approved_at = None
    invoice.master_notes = None
    invoice.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(invoice)

    from app.utils.audit import log_audit
    from app.services.notification_service import NotificationService
    await log_audit(
        db=db, user=current_user, action="SALES_INVOICE_EDIT_SUBMITTED",
        entity_obj=invoice, reason=payload.reason,
    )
    await NotificationService.send_to_role(
        db=db, role="OPERATIONS",
        title="Invoice Edit Truth Check Needed",
        message=f"Invoice {invoice.invoice_number} has been edited. Please check activity logs and confirm before forwarding to Master Admin.\n\nReason: {payload.reason}",
        action_url="/dashboard/operation"
    )
    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_sales_invoice(invoice), message="Edit submitted for approval. Operations team has been notified.")


@router.post("/{invoice_id}/operations-verify")
async def sales_invoice_operations_verify(
    invoice_id: str,
    action: SalesInvoiceWorkflowAction,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Step 3 — Operations confirms the Truth Check and forwards to
    Master Admin, mirroring WorkflowService.operations_verify_po."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    _require_role(current_user, ["OPERATIONS", "OPERATION", "MASTER_ADMIN"])
    result = await db.execute(select(SalesInvoice).where(SalesInvoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)
    if invoice.workflow_status != "Pending Operations Review":
        raise HTTPException(status_code=400, detail=f"Invoice is not pending Operations review (current: {invoice.workflow_status})")

    invoice.workflow_status = "Pending Master Admin Approval"
    invoice.operations_reviewed_by = current_user.id
    invoice.operations_reviewed_at = get_utc_now()
    invoice.operations_notes = action.notes
    invoice.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(invoice)

    from app.utils.audit import log_audit
    from app.services.notification_service import NotificationService
    await log_audit(
        db=db, user=current_user, action="SALES_INVOICE_EDIT_OPERATIONS_VERIFIED",
        entity_obj=invoice, reason=action.notes,
    )
    await NotificationService.send_to_role(
        db=db, role="MASTER_ADMIN",
        title="Invoice Edit Ready for Final Approval",
        message=f"Operations has verified invoice {invoice.invoice_number}'s edit.\n\nNotes: {action.notes or ''}\n\nPlease give final approval to apply changes.",
        action_url="/dashboard/admin"
    )
    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_sales_invoice(invoice), message="Verified and forwarded to Master Admin")


@router.post("/{invoice_id}/operations-reject")
async def sales_invoice_operations_reject(
    invoice_id: str,
    action: SalesInvoiceWorkflowAction,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Operations rejects the edit at the Truth Check stage."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    _require_role(current_user, ["OPERATIONS", "OPERATION", "MASTER_ADMIN"])
    result = await db.execute(select(SalesInvoice).where(SalesInvoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)
    if invoice.workflow_status != "Pending Operations Review":
        raise HTTPException(status_code=400, detail=f"Invoice is not pending Operations review (current: {invoice.workflow_status})")

    invoice.workflow_status = "Rejected"
    invoice.approval_status = "REJECTED"
    invoice.operations_reviewed_by = current_user.id
    invoice.operations_reviewed_at = get_utc_now()
    invoice.operations_notes = action.notes
    invoice.pending_changes = None
    invoice.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(invoice)

    from app.utils.audit import log_audit
    from app.services.notification_service import NotificationService
    await log_audit(
        db=db, user=current_user, action="SALES_INVOICE_EDIT_OPERATIONS_REJECTED",
        entity_obj=invoice, reason=action.notes,
    )
    owner_result = await db.execute(select(User).where(User.id == invoice.user_id))
    owner = owner_result.scalar_one_or_none()
    if owner:
        await NotificationService.send(
            db, owner.email, "Invoice Edit Rejected",
            f"Your edit to invoice {invoice.invoice_number} was rejected during Operations review. {('Reason: ' + action.notes) if action.notes else ''}",
            action_url="/invoices"
        )
    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_sales_invoice(invoice), message="Edit rejected")


@router.post("/{invoice_id}/master-approve")
async def sales_invoice_master_approve(
    invoice_id: str,
    action: SalesInvoiceWorkflowAction,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Master Admin gives final approval, applying pending_changes."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    _require_role(current_user, ["MASTER_ADMIN"])
    result = await db.execute(select(SalesInvoice).where(SalesInvoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)
    if invoice.workflow_status != "Pending Master Admin Approval":
        raise HTTPException(status_code=400, detail=f"Invoice is not pending Master Admin approval (current: {invoice.workflow_status})")

    pending = invoice.pending_changes or {}
    date_fields = {"invoice_date", "payment_due_date", "po_date", "expected_delivery_date", "lut_filing_date"}
    for field, value in pending.items():
        if field == "items":
            invoice.items = value
            continue
        if field in date_fields and isinstance(value, str):
            from datetime import date as date_cls
            value = date_cls.fromisoformat(value)
        setattr(invoice, field, value)

    invoice.approval_status = "APPROVED"
    invoice.workflow_status = "Approved"
    invoice.master_approved_by = current_user.id
    invoice.master_approved_at = get_utc_now()
    invoice.master_notes = action.notes or "Approved"
    invoice.pending_changes = None
    invoice.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(invoice)

    from app.utils.audit import log_audit
    from app.services.notification_service import NotificationService
    await log_audit(
        db=db, user=current_user, action="SALES_INVOICE_EDIT_APPROVED",
        entity_obj=invoice, reason=action.notes or f"Invoice {invoice.invoice_number} edit approved",
    )
    owner_result = await db.execute(select(User).where(User.id == invoice.user_id))
    owner = owner_result.scalar_one_or_none()
    if owner:
        await NotificationService.send(
            db, owner.email, "Invoice Edit Approved",
            f"Your edit to invoice {invoice.invoice_number} has been approved and applied.",
            action_url="/invoices"
        )
    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_sales_invoice(invoice), message="Invoice edit approved and applied")


@router.post("/{invoice_id}/master-reject")
async def sales_invoice_master_reject(
    invoice_id: str,
    action: SalesInvoiceWorkflowAction,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Master Admin rejects the edit at the final stage, discarding
    pending_changes."""
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    _require_role(current_user, ["MASTER_ADMIN"])
    result = await db.execute(select(SalesInvoice).where(SalesInvoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)
    if invoice.workflow_status != "Pending Master Admin Approval":
        raise HTTPException(status_code=400, detail=f"Invoice is not pending Master Admin approval (current: {invoice.workflow_status})")

    invoice.approval_status = "REJECTED"
    invoice.workflow_status = "Rejected"
    invoice.master_approved_by = current_user.id
    invoice.master_approved_at = get_utc_now()
    invoice.master_notes = action.notes or "Rejected"
    invoice.pending_changes = None
    invoice.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(invoice)

    from app.utils.audit import log_audit
    from app.services.notification_service import NotificationService
    await log_audit(
        db=db, user=current_user, action="SALES_INVOICE_EDIT_REJECTED",
        entity_obj=invoice, reason=action.notes or f"Invoice {invoice.invoice_number} edit rejected",
    )
    owner_result = await db.execute(select(User).where(User.id == invoice.user_id))
    owner = owner_result.scalar_one_or_none()
    if owner:
        await NotificationService.send(
            db, owner.email, "Invoice Edit Rejected",
            f"Your edit to invoice {invoice.invoice_number} was rejected. {('Reason: ' + action.notes) if action.notes else ''}",
            action_url="/invoices"
        )
    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_sales_invoice(invoice), message="Invoice edit rejected")


@router.delete("/{invoice_id}", status_code=204)
async def delete_sales_invoice(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not await AccessControlService.can_access_feature(current_user.id, "CREDIT_MANAGEMENT", db):
        raise UnauthorizedFeature("Invoice Management")
    invoice = await _get_owned_invoice(db, invoice_id, current_user.id)
    if not invoice:
        raise HTTPException(status_code=404, detail=SALES_INVOICE_NOT_FOUND_ERROR)

    await db.delete(invoice)
    await db.commit()