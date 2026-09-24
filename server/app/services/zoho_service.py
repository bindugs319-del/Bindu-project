"""
Zoho Invoice API client.

Handles OAuth token refresh and fetching a single invoice by ID. Used by
app/routes/integrations_zoho.py, which is called by a Zoho webhook the
moment an invoice is created/updated in Zoho Invoice, so it shows up in
CreditDataWatch automatically without a manual export/import step.

Setup reference: https://www.zoho.com/invoice/api/v3/oauth/
API reference:   https://www.zoho.com/invoice/api/v3/invoices/
"""
import time
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Cached in memory only — fine for a single Render instance on the free
# tier. Re-fetched automatically once expired (access tokens last ~1hr).
_cached_access_token: Optional[str] = None
_cached_expires_at: float = 0.0


async def get_access_token() -> str:
    """Returns a valid Zoho access token, refreshing it via the stored
    refresh token if the cached one is missing or about to expire."""
    global _cached_access_token, _cached_expires_at

    if _cached_access_token and time.time() < _cached_expires_at - 60:
        return _cached_access_token

    if not settings.ZOHO_CLIENT_ID or not settings.ZOHO_CLIENT_SECRET or not settings.ZOHO_REFRESH_TOKEN:
        raise RuntimeError(
            "Zoho integration is not configured — set ZOHO_CLIENT_ID, "
            "ZOHO_CLIENT_SECRET and ZOHO_REFRESH_TOKEN."
        )

    token_url = f"{settings.ZOHO_ACCOUNTS_BASE_URL}/oauth/v2/token"
    params = {
        "refresh_token": settings.ZOHO_REFRESH_TOKEN,
        "client_id": settings.ZOHO_CLIENT_ID,
        "client_secret": settings.ZOHO_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(token_url, data=params)

    if resp.status_code != 200:
        logger.error("Zoho token refresh failed: %s %s", resp.status_code, resp.text)
        raise RuntimeError(f"Zoho token refresh failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        raise RuntimeError(f"Zoho token refresh response had no access_token: {data}")

    _cached_access_token = access_token
    # expires_in is in seconds, typically 3600.
    _cached_expires_at = time.time() + float(data.get("expires_in", 3600))
    return access_token


async def fetch_invoice(invoice_id: str) -> dict:
    """Fetches one invoice's full details from Zoho by its invoice_id.

    We fetch the full invoice from the API rather than trusting the
    webhook's own request body, because Zoho's default webhook payload
    format is not tightly documented/versioned and has changed before.
    The GET /invoices/{id} response, by contrast, is part of the stable,
    documented v3 API.
    """
    if not settings.ZOHO_ORGANIZATION_ID:
        raise RuntimeError("ZOHO_ORGANIZATION_ID is not configured.")

    access_token = await get_access_token()
    url = f"{settings.ZOHO_API_BASE_URL}/invoices/{invoice_id}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-invoice-organizationid": settings.ZOHO_ORGANIZATION_ID,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers)

    if resp.status_code != 200:
        logger.error("Zoho fetch_invoice failed: %s %s", resp.status_code, resp.text)
        raise RuntimeError(f"Zoho fetch_invoice failed ({resp.status_code}): {resp.text}")

    body = resp.json()
    invoice = body.get("invoice")
    if not invoice:
        raise RuntimeError(f"Zoho fetch_invoice response had no 'invoice' key: {body}")
    return invoice


async def list_invoices(per_page: int = 100) -> list:
    """Fetches up to `per_page` invoices, most-recently-modified first.

    Used by the polling sync (app/services/zoho_poll_service.py) instead
    of a webhook, since Zoho's free plan doesn't include
    Automation/Webhooks. Zoho's List Invoices endpoint accepts a
    last_modified_time filter, but its exact matching behaviour (exact
    match vs. "since") isn't confirmed for this account, so we don't
    rely on it — we always fetch newest-first and let the caller decide
    where to stop based on its own saved watermark. per_page=100 covers
    a very large amount of invoicing activity per 15-minute poll; raise
    it (Zoho allows up to 200) if you have an unusually high volume.
    """
    if not settings.ZOHO_ORGANIZATION_ID:
        raise RuntimeError("ZOHO_ORGANIZATION_ID is not configured.")

    access_token = await get_access_token()
    url = f"{settings.ZOHO_API_BASE_URL}/invoices"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "X-com-zoho-invoice-organizationid": settings.ZOHO_ORGANIZATION_ID,
    }
    params = {
        "sort_column": "last_modified_time",
        "sort_order": "D",  # descending — newest first
        "per_page": per_page,
        "page": 1,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=headers, params=params)

    if resp.status_code != 200:
        logger.error("Zoho list_invoices failed: %s %s", resp.status_code, resp.text)
        raise RuntimeError(f"Zoho list_invoices failed ({resp.status_code}): {resp.text}")

    body = resp.json()
    return body.get("invoices") or []


async def fetch_invoice_pdf(invoice_id: str) -> Optional[bytes]:
    """Downloads the invoice as a PDF, exactly as Zoho itself renders it.
    Confirmed endpoint: GET /invoices/{id} with an Accept: application/pdf
    header returns the PDF bytes directly instead of the usual JSON —
    see https://www.zoho.com/invoice/api/v3/response/ ("Other Formats").
    Returns None (never raises) on any failure, since a PDF-attach
    problem shouldn't block the invoice record itself from syncing —
    see zoho_sync_service.py, which logs a warning and carries on."""
    if not settings.ZOHO_ORGANIZATION_ID:
        return None

    try:
        access_token = await get_access_token()
        url = f"{settings.ZOHO_API_BASE_URL}/invoices/{invoice_id}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "X-com-zoho-invoice-organizationid": settings.ZOHO_ORGANIZATION_ID,
            "Accept": "application/pdf",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code != 200 or "pdf" not in resp.headers.get("content-type", ""):
            logger.warning("Zoho fetch_invoice_pdf: unexpected response for %s (%s, %s)", invoice_id, resp.status_code, resp.headers.get("content-type"))
            return None
        return resp.content
    except Exception as e:
        logger.warning("Zoho fetch_invoice_pdf failed for %s: %s", invoice_id, e)
        return None
