"""
Zoho Invoice -> CreditDataWatch sync — webhook path.

NOT required for the integration to work: on a free Zoho Invoice plan,
Zoho's Automation/Webhooks feature isn't available, so
app/services/zoho_poll_service.py (a periodic background check) is the
path actually in use. This webhook exists so that if the Zoho account
is later upgraded to a paid plan, near-instant sync can be turned on by
just adding a Webhook in Zoho Invoice > Settings > Automation, with no
code changes — it reuses the exact same upsert logic as the poller
(app/services/zoho_sync_service.py), so behavior is identical either way.

Setup instructions: see docs/zoho-integration-setup.md
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services import zoho_service, zoho_sync_service

logger = logging.getLogger(__name__)
router = APIRouter()


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

    invoice_id = payload.get("invoice_id") or (
        payload.get("invoice", {}).get("invoice_id") if isinstance(payload.get("invoice"), dict) else None
    )
    if not invoice_id:
        raise HTTPException(status_code=400, detail="No invoice_id found in webhook payload.")

    zoho_invoice = await zoho_service.fetch_invoice(str(invoice_id))
    target_user = await zoho_sync_service.get_target_user(db)
    result = await zoho_sync_service.sync_one_invoice(zoho_invoice, db, target_user)
    return result
