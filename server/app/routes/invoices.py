from datetime import datetime
from datetime import timezone, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Invoice, User
from app.schemas.features import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceListResponse,
    InvoiceFollowUpNote,
    InvoiceWorkflowAction,
)
from app.utils.response import ResponseFormatter

# Constants
INVOICE_NOT_FOUND_ERROR = "Invoice not found"

# Helper function
def get_utc_now():
    """Get current UTC time as a naive datetime.

    The Invoice model's DateTime columns are plain (timezone-naive), so
    this must return a naive datetime too — mixing an aware datetime
    (datetime.now(timezone.utc)) into these columns causes asyncpg to
    fail with "can't subtract offset-naive and offset-aware datetimes"
    at insert time.
    """
    return datetime.utcnow()

router = APIRouter(prefix="/invoices", tags=["Invoices"])

# Helper function for success responses
def success_response(data=None, message="Success"):
    return ResponseFormatter.create_success(data=data, message=message)


def serialize_invoice(invoice: Invoice) -> dict:
    """Convert an Invoice ORM object into a JSON-safe dict.

    Returning the raw SQLAlchemy object from a route causes FastAPI's
    JSON encoder to choke on internal ORM state (e.g. _sa_instance_state),
    resulting in a 500 error. Always serialize through the response schema
    before returning.
    """
    return InvoiceResponse.model_validate(invoice).model_dump(mode="json")


@router.get("")
async def list_invoices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    
    search: Optional[str] = None
):
    """List invoices with optional filtering"""
    query = select(Invoice).where(Invoice.user_id == current_user.id)

    if status:
        query = query.where(Invoice.status == status)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Invoice.counterparty_name.ilike(search_term),
                Invoice.invoice_number.ilike(search_term),
                Invoice.notes.ilike(search_term),
            )
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar_one()

    # Get paginated results
    query = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    invoices = result.scalars().all()

    return success_response(
        data={
            "invoices": [serialize_invoice(inv) for inv in invoices],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    )


@router.post("", status_code=201)
async def create_invoice(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    invoice_data: InvoiceCreate
):
    """Create a new invoice (Draft)"""
    from uuid import uuid4

    invoice = Invoice(
        id=str(uuid4()),
        user_id=current_user.id,
        counterparty_name=invoice_data.counterparty_name,
        company_id=invoice_data.company_id or getattr(current_user, "company_id", None),
        invoice_number=invoice_data.invoice_number,
        amount=invoice_data.amount,
        due_date=invoice_data.due_date,
        status=invoice_data.status or "pending",
        workflow_status="Draft",
        reminder_frequency_days=invoice_data.reminder_frequency_days or 7,
        notes=invoice_data.notes,
        follow_up_history=[],
    )

    # Set initial reminder date if not acknowledged
    if invoice.status != "acknowledged":
        invoice.reminder_next_at = get_utc_now() + timedelta(
            days=invoice.reminder_frequency_days
        )

    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    from app.utils.audit import log_audit
    await log_audit(db, current_user, "INVOICE_CREATED", entity_obj=invoice,
                     reason=f"Invoice {invoice.invoice_number} created")
    await db.commit()

    return success_response(data=serialize_invoice(invoice))


@router.post("/{invoice_id}/submit")
async def submit_invoice(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Submit a draft invoice into the Operations -> Master Admin approval workflow."""
    result = await db.execute(
        select(Invoice).where(and_(Invoice.id == invoice_id, Invoice.user_id == current_user.id))
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=INVOICE_NOT_FOUND_ERROR)

    if invoice.workflow_status not in (None, "Draft", "Changes Required"):
        raise HTTPException(status_code=400, detail=f"Invoice cannot be submitted from status '{invoice.workflow_status}'")

    invoice.workflow_status = "Pending Operations Review"
    invoice.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(invoice)

    from app.utils.audit import log_audit
    from app.services.notification_service import NotificationService
    await log_audit(db, current_user, "INVOICE_SUBMITTED", entity_obj=invoice,
                     reason=f"Invoice {invoice.invoice_number} submitted for approval")
    await NotificationService.send_to_role(
        db=db, role="OPERATIONS",
        title="New Invoice Submitted",
        message=f"Invoice {invoice.invoice_number} ({invoice.counterparty_name}, ₹{invoice.amount}) is pending your review.",
        action_url="/dashboard/operation"
    )
    await db.commit()

    return success_response(data=serialize_invoice(invoice), message="Invoice submitted for approval")


def _require_role(current_user, allowed):
    role = str(getattr(current_user.role, "value", current_user.role) or "").upper()
    if role not in allowed:
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action")


@router.get("/workflow/pending-operations")
async def list_pending_operations_invoices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Invoices awaiting Operations Team verification."""
    _require_role(current_user, ["OPERATIONS", "OPERATION", "MASTER_ADMIN"])
    result = await db.execute(
        select(Invoice).where(Invoice.workflow_status == "Pending Operations Review").order_by(Invoice.created_at.desc())
    )
    invoices = result.scalars().all()
    return success_response(data=[serialize_invoice(i) for i in invoices])


@router.post("/{invoice_id}/operations-verify")
async def operations_verify_invoice(
    invoice_id: str,
    action: InvoiceWorkflowAction,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Operations Team verifies and forwards the invoice to Master Admin."""
    _require_role(current_user, ["OPERATIONS", "OPERATION", "MASTER_ADMIN"])
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=INVOICE_NOT_FOUND_ERROR)
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
    await log_audit(db, current_user, "INVOICE_OPERATIONS_VERIFIED", entity_obj=invoice,
                     reason=f"Invoice {invoice.invoice_number} verified by Operations, forwarded to Master Admin")

    owner_result = await db.execute(select(User).where(User.id == invoice.user_id))
    owner = owner_result.scalar_one_or_none()
    if owner:
        await NotificationService.send(
            db, owner.email, "Invoice Verified by Operations",
            f"Your invoice {invoice.invoice_number} has been verified by Operations and forwarded to Master Admin for final approval.",
            action_url="/invoices"
        )
    await NotificationService.send_to_role(
        db=db, role="MASTER_ADMIN",
        title="Invoice Pending Final Approval",
        message=f"Invoice {invoice.invoice_number} ({invoice.counterparty_name}, ₹{invoice.amount}) has been verified by Operations and needs your final approval.",
        action_url="/dashboard/admin"
    )
    await db.commit()

    return success_response(data=serialize_invoice(invoice), message="Invoice verified and forwarded to Master Admin")


@router.post("/{invoice_id}/operations-reject")
async def operations_reject_invoice(
    invoice_id: str,
    action: InvoiceWorkflowAction,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Operations Team rejects/sends back the invoice for changes."""
    _require_role(current_user, ["OPERATIONS", "OPERATION", "MASTER_ADMIN"])
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=INVOICE_NOT_FOUND_ERROR)
    if invoice.workflow_status != "Pending Operations Review":
        raise HTTPException(status_code=400, detail=f"Invoice is not pending Operations review (current: {invoice.workflow_status})")

    invoice.workflow_status = "Changes Required" if (action.notes and "changes" in action.notes.lower()) else "Rejected"
    invoice.operations_reviewed_by = current_user.id
    invoice.operations_reviewed_at = get_utc_now()
    invoice.operations_notes = action.notes
    invoice.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(invoice)

    from app.utils.audit import log_audit
    from app.services.notification_service import NotificationService
    await log_audit(db, current_user, "INVOICE_OPERATIONS_REJECTED", entity_obj=invoice,
                     reason=f"Invoice {invoice.invoice_number} {invoice.workflow_status.lower()} by Operations: {action.notes or ''}")

    owner_result = await db.execute(select(User).where(User.id == invoice.user_id))
    owner = owner_result.scalar_one_or_none()
    if owner:
        await NotificationService.send(
            db, owner.email, f"Invoice {invoice.workflow_status}",
            f"Your invoice {invoice.invoice_number} was marked '{invoice.workflow_status}' by Operations. {('Reason: ' + action.notes) if action.notes else ''}",
            action_url="/invoices"
        )
    await db.commit()

    return success_response(data=serialize_invoice(invoice), message=f"Invoice marked {invoice.workflow_status}")


@router.get("/workflow/pending-master")
async def list_pending_master_invoices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Invoices awaiting Master Admin final approval."""
    _require_role(current_user, ["MASTER_ADMIN"])
    result = await db.execute(
        select(Invoice).where(Invoice.workflow_status == "Pending Master Admin Approval").order_by(Invoice.created_at.desc())
    )
    invoices = result.scalars().all()
    return success_response(data=[serialize_invoice(i) for i in invoices])


@router.post("/{invoice_id}/master-approve")
async def master_approve_invoice(
    invoice_id: str,
    action: InvoiceWorkflowAction,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Master Admin gives final approval on the invoice."""
    _require_role(current_user, ["MASTER_ADMIN"])
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=INVOICE_NOT_FOUND_ERROR)
    if invoice.workflow_status != "Pending Master Admin Approval":
        raise HTTPException(status_code=400, detail=f"Invoice is not pending Master Admin approval (current: {invoice.workflow_status})")

    invoice.workflow_status = "Approved"
    invoice.master_approved_by = current_user.id
    invoice.master_approved_at = get_utc_now()
    invoice.master_notes = action.notes
    invoice.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(invoice)

    from app.utils.audit import log_audit
    from app.services.notification_service import NotificationService
    await log_audit(db, current_user, "INVOICE_APPROVED", entity_obj=invoice,
                     reason=f"Invoice {invoice.invoice_number} approved by Master Admin")

    owner_result = await db.execute(select(User).where(User.id == invoice.user_id))
    owner = owner_result.scalar_one_or_none()
    if owner:
        await NotificationService.send(
            db, owner.email, "Invoice Approved",
            f"Your invoice {invoice.invoice_number} has been fully approved.",
            action_url="/invoices"
        )
    await db.commit()

    return success_response(data=serialize_invoice(invoice), message="Invoice approved")


@router.post("/{invoice_id}/master-reject")
async def master_reject_invoice(
    invoice_id: str,
    action: InvoiceWorkflowAction,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Master Admin rejects/sends back the invoice."""
    _require_role(current_user, ["MASTER_ADMIN"])
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=INVOICE_NOT_FOUND_ERROR)
    if invoice.workflow_status != "Pending Master Admin Approval":
        raise HTTPException(status_code=400, detail=f"Invoice is not pending Master Admin approval (current: {invoice.workflow_status})")

    invoice.workflow_status = "Changes Required" if (action.notes and "changes" in action.notes.lower()) else "Rejected"
    invoice.master_approved_by = current_user.id
    invoice.master_approved_at = get_utc_now()
    invoice.master_notes = action.notes
    invoice.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(invoice)

    from app.utils.audit import log_audit
    from app.services.notification_service import NotificationService
    await log_audit(db, current_user, "INVOICE_MASTER_REJECTED", entity_obj=invoice,
                     reason=f"Invoice {invoice.invoice_number} {invoice.workflow_status.lower()} by Master Admin: {action.notes or ''}")

    owner_result = await db.execute(select(User).where(User.id == invoice.user_id))
    owner = owner_result.scalar_one_or_none()
    if owner:
        await NotificationService.send(
            db, owner.email, f"Invoice {invoice.workflow_status}",
            f"Your invoice {invoice.invoice_number} was marked '{invoice.workflow_status}' by Master Admin. {('Reason: ' + action.notes) if action.notes else ''}",
            action_url="/invoices"
        )
    await db.commit()

    return success_response(data=serialize_invoice(invoice), message=f"Invoice marked {invoice.workflow_status}")


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get a specific invoice"""
    role = str(getattr(current_user.role, "value", current_user.role) or "").upper()
    if role in ("OPERATIONS", "OPERATION", "MASTER_ADMIN"):
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    else:
        result = await db.execute(
            select(Invoice).where(
                and_(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
            )
        )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail=INVOICE_NOT_FOUND_ERROR)

    return success_response(data=serialize_invoice(invoice))


@router.put("/{invoice_id}")
async def update_invoice(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    invoice_data: InvoiceUpdate
):
    """Update an invoice"""
    result = await db.execute(
        select(Invoice).where(
            and_(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        )
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail=INVOICE_NOT_FOUND_ERROR)

    # Update fields
    update_data = invoice_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(invoice, field, value)

    # Update reminder schedule if frequency changed
    if "reminder_frequency_days" in update_data and invoice.status != "acknowledged":
        invoice.reminder_next_at = get_utc_now() + timedelta(
            days=invoice.reminder_frequency_days
        )

    invoice.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_invoice(invoice))


@router.delete("/{invoice_id}", status_code=204)
async def delete_invoice(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Delete an invoice"""
    result = await db.execute(
        select(Invoice).where(
            and_(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        )
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail=INVOICE_NOT_FOUND_ERROR)

    await db.delete(invoice)
    await db.commit()


@router.post("/{invoice_id}/acknowledge")
async def toggle_acknowledgment(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Toggle invoice acknowledgment status"""
    result = await db.execute(
        select(Invoice).where(
            and_(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        )
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail=INVOICE_NOT_FOUND_ERROR)

    if invoice.status == "acknowledged":
        # Unacknowledge - set back to pending and schedule next reminder
        invoice.status = "pending"
        invoice.acknowledged_at = None
        invoice.reminder_next_at = get_utc_now() + timedelta(
            days=invoice.reminder_frequency_days
        )
    else:
        # Acknowledge - clear reminder
        invoice.status = "acknowledged"
        invoice.acknowledged_at = get_utc_now()
        invoice.reminder_next_at = None

    invoice.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_invoice(invoice))


@router.post("/{invoice_id}/follow-up")
async def add_follow_up_note(
    invoice_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    note_data: InvoiceFollowUpNote
):
    """Add a follow-up note to an invoice"""
    result = await db.execute(
        select(Invoice).where(
            and_(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
        )
    )
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail=INVOICE_NOT_FOUND_ERROR)

    # Add note to follow-up history
    new_note = {
        "timestamp": get_utc_now().isoformat(),
        "note": note_data.note,
    }

    if invoice.follow_up_history is None:
        invoice.follow_up_history = []

    invoice.follow_up_history.append(new_note)
    invoice.last_follow_up_at = get_utc_now()
    invoice.updated_at = get_utc_now()

    # Schedule next reminder if not acknowledged
    if invoice.status != "acknowledged":
        invoice.reminder_next_at = get_utc_now() + timedelta(
            days=invoice.reminder_frequency_days
        )

    # Mark as modified to trigger SQLAlchemy update for JSON field
    from sqlalchemy.orm import attributes

    attributes.flag_modified(invoice, "follow_up_history")

    await db.commit()
    await db.refresh(invoice)

    return success_response(data=serialize_invoice(invoice))


@router.get("/reminders/due")
async def get_due_reminders(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get invoices with reminders due"""
    now = get_utc_now()
    query = select(Invoice).where(
        and_(
            Invoice.user_id == current_user.id,
            Invoice.status != "acknowledged",
            Invoice.reminder_next_at <= now,
        )
    )

    result = await db.execute(query)
    invoices = result.scalars().all()

    return success_response(
        data={
            "invoices": [serialize_invoice(inv) for inv in invoices],
            "total": len(invoices),
            "skip": 0,
            "limit": len(invoices),
        }
    )
