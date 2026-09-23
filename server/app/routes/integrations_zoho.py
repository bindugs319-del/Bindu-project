"""
Zoho Invoice -> CreditDataWatch sync.

Zoho calls POST /integrations/zoho/webhook the moment an invoice is
created or updated in Zoho Invoice (configured as a Webhook under
Zoho Invoice > Settings > Automation > Webhooks). We then fetch the
full invoice from the Zoho API (see app/services/zoho_service.py for
why) and upsert it into sales_invoices by invoice_number, exactly like
the existing /sales-invoices/import-pdf flow — so it lands in the same
place a manually-imported invoice would, with no manual step at all.

Setup instructions: see docs/zoho-integration-setup.md
"""
import logging
from datetime import datetime, date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.config import settings
from app.database import get_db
from app.models import SalesInvoice, User
from app.services import zoho_service
from app.services.business_profile_service import BusinessProfileService

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_zoho_date(value: Optional[str]) -> Optional[date]:
    """Zoho dates are yyyy-mm-dd."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        logger.warning("Could not parse Zoho date %r", value)
        return None


def _first_present(d: dict, *keys, default=None):
    """Returns the first key present in d with a non-empty value. Used
    for fields where Zoho's exact key name varies by plan/edition and we
    haven't confirmed the exact one for this account (e.g. GSTIN)."""
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default


async def _get_target_user(db: AsyncSession) -> User:
    """The CreditDataWatch account that Zoho-synced invoices are filed
    under. Configured once via ZOHO_TARGET_USER_EMAIL — see setup docs."""
    if not settings.ZOHO_TARGET_USER_EMAIL:
        raise HTTPException(status_code=500, detail="ZOHO_TARGET_USER_EMAIL is not configured on the server.")
    stmt = select(User).where(User.email == settings.ZOHO_TARGET_USER_EMAIL.strip().lower())
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=500, detail=f"No CreditDataWatch user found for ZOHO_TARGET_USER_EMAIL={settings.ZOHO_TARGET_USER_EMAIL}")
    return user


@router.post("/integrations/zoho/webhook")
async def zoho_invoice_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # --- Basic shared-secret check ---------------------------------
    # Configure the webhook URL in Zoho as:
    #   https://<your-render-backend>/api/v1/integrations/zoho/webhook?secret=<ZOHO_WEBHOOK_SECRET>
    # This is not Zoho's official HMAC signature scheme (that's a Zoho
    # Billing/Books feature, not confirmed for Zoho Invoice); it just
    # stops randoms from calling this URL and triggering a lookup.
    if not settings.ZOHO_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="ZOHO_WEBHOOK_SECRET is not configured on the server.")
    if request.query_params.get("secret") != settings.ZOHO_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid or missing webhook secret.")

    # --- Get the invoice_id out of whatever Zoho sent ----------------
    # We only need the ID; everything else is re-fetched from the API.
    # Configure the webhook's body in Zoho to send:
    #   {"invoice_id": "${invoice.invoice_id}"}
    # so this works regardless of Zoho's default payload format.
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    invoice_id = _first_present(payload, "invoice_id") or _first_present(
        payload.get("invoice", {}) if isinstance(payload.get("invoice"), dict) else {}, "invoice_id"
    )
    if not invoice_id:
        raise HTTPException(status_code=400, detail="No invoice_id found in webhook payload.")

    zoho_invoice = await zoho_service.fetch_invoice(str(invoice_id))

    invoice_number = zoho_invoice.get("invoice_number")
    if not invoice_number:
        raise HTTPException(status_code=502, detail="Zoho invoice had no invoice_number.")

    invoice_date_obj = _parse_zoho_date(zoho_invoice.get("date")) or date.today()
    due_date_obj = _parse_zoho_date(zoho_invoice.get("due_date")) or invoice_date_obj

    counterparty_name = zoho_invoice.get("customer_name") or "Unknown Customer"
    counterparty_email = zoho_invoice.get("email") or None
    # NOTE: the exact key Zoho uses for the customer's GSTIN varies by
    # account/edition. Common candidates are tried here; if none match,
    # confirm the real key from a logged payload (see setup docs) and
    # add it to this list.
    counterparty_gstin = _first_present(zoho_invoice, "gst_no", "tax_reg_no", "gst_treatment", default=None)
    if counterparty_gstin:
        counterparty_gstin = str(counterparty_gstin).strip().upper() or None

    total = float(zoho_invoice.get("total") or 0)
    balance = float(zoho_invoice.get("balance") or total)
    # Subtotal/tax key names aren't confirmed for this account either —
    # see docs/zoho-integration-setup.md for how to check a live payload.
    subtotal = float(_first_present(zoho_invoice, "sub_total", "subtotal", default=total) or total)
    tax_amount = float(_first_present(zoho_invoice, "tax_total", "total_tax", default=max(total - subtotal, 0)) or 0)

    target_user = await _get_target_user(db)

    stmt = select(SalesInvoice).where(
        SalesInvoice.user_id == target_user.id,
        SalesInvoice.invoice_number == invoice_number,
        SalesInvoice.archived == False,  # noqa: E712
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        if existing.status == "Paid":
            logger.info("Zoho webhook: invoice %s is already Paid in CreditDataWatch, skipping update.", invoice_number)
            return {"status": "skipped", "reason": "already paid", "invoice_number": invoice_number}
        existing.counterparty_name = counterparty_name
        if counterparty_gstin:
            existing.counterparty_gstin = counterparty_gstin
        if counterparty_email:
            existing.counterparty_email = counterparty_email
        existing.subtotal = subtotal
        existing.tax_amount = tax_amount
        existing.total = total
        existing.balance_due = balance
        existing.invoice_date = invoice_date_obj
        existing.payment_due_date = due_date_obj
        existing.updated_at = datetime.utcnow()
        await db.commit()
        logger.info("Zoho webhook: updated existing invoice %s (id=%s)", invoice_number, existing.id)
        return {"status": "updated", "invoice_number": invoice_number, "id": existing.id}

    profile = await BusinessProfileService.get_or_create_profile(target_user.id, db)
    now = datetime.utcnow()
    invoice = SalesInvoice(
        id=str(uuid4()),
        user_id=target_user.id,
        company_id=getattr(target_user, "company_id", None),
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
        counterparty_gstin=counterparty_gstin,
        counterparty_email=counterparty_email,
        country="IN",
        currency=(zoho_invoice.get("currency_code") or "INR")[:3].upper(),
        exchange_rate=1.0,
        items=[],
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=total,
        balance_due=balance,
        status="Draft",
        notes="Imported automatically from Zoho Invoice.",
        created_at=now,
        updated_at=now,
    )
    db.add(invoice)
    await db.commit()
    logger.info("Zoho webhook: created new invoice %s (id=%s)", invoice_number, invoice.id)
    return {"status": "created", "invoice_number": invoice_number, "id": invoice.id}
