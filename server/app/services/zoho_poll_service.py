"""
Periodic Zoho Invoice -> CreditDataWatch sync.

This is the sync path actually in use: Zoho's free plan doesn't include
Automation/Webhooks, so instead of Zoho pushing to us the moment an
invoice changes, this checks Zoho every ZOHO_POLL_INTERVAL_SECONDS (see
app/main.py's _zoho_poll_runner, started at app startup) and pulls in
anything new since the last check.

How "since the last check" works: Zoho's List Invoices endpoint returns
invoices sorted newest-modified-first. We remember the last_modified_time
of the newest invoice we've already synced (stored as a row in
system_settings, the same table/pattern used elsewhere in this app for
small persisted settings — see app/routes/admin.py's _get_stat_setting/
_save_stat_setting for the same pattern). Each poll walks the list from
the top and stops as soon as it reaches an invoice at or before that
watermark, then saves the newest invoice's timestamp as the new
watermark. On the very first run (no watermark saved yet) this instead
imports the most recent 100 invoices, so existing Zoho invoices show up
in CreditDataWatch too, not just ones created after setup.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services import zoho_service, zoho_sync_service

logger = logging.getLogger(__name__)

_WATERMARK_KEY = "zoho_poll_last_modified_time"


def zoho_configured() -> bool:
    """True once all the settings this sync needs are present. Lets the
    poll runner in app/main.py stay quiet (not log warnings every tick)
    until Zoho setup is actually finished."""
    return bool(
        settings.ZOHO_CLIENT_ID
        and settings.ZOHO_CLIENT_SECRET
        and settings.ZOHO_REFRESH_TOKEN
        and settings.ZOHO_ORGANIZATION_ID
        and settings.ZOHO_TARGET_USER_EMAIL
    )


def _parse_zoho_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Zoho's last_modified_time looks like '2013-11-17T10:00:00-0800'.
    Python 3.11+'s fromisoformat handles this directly; older formats
    (e.g. a 'Z' suffix) get a best-effort fallback. Returns None if it
    can't be parsed at all — callers should treat that as "sync it
    anyway", since sync_one_invoice is idempotent by invoice_number."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Could not parse Zoho last_modified_time %r", value)
            return None


async def _get_watermark(db: AsyncSession) -> Optional[str]:
    row = (await db.execute(
        text("SELECT value FROM system_settings WHERE key = :key"),
        {"key": _WATERMARK_KEY},
    )).mappings().first()
    return row["value"] if row and row["value"] else None


async def _save_watermark(db: AsyncSession, value: str) -> None:
    await db.execute(text("""
        INSERT INTO system_settings (id, key, value, description, updated_at)
        VALUES (gen_random_uuid(), :key, :value, :description, NOW())
        ON CONFLICT (key) DO UPDATE SET
            value = :value,
            updated_at = NOW()
    """), {
        "key": _WATERMARK_KEY,
        "value": value,
        "description": "Internal — last Zoho invoice last_modified_time synced by the Zoho poll (app/services/zoho_poll_service.py). Do not edit by hand.",
    })
    await db.commit()


async def run_zoho_poll_once(db: AsyncSession) -> dict:
    """Runs a single poll cycle. Returns a small summary dict — mainly
    useful for logging and for the one-off manual trigger, if added
    later."""
    if not zoho_configured():
        return {"status": "not_configured"}

    watermark_str = await _get_watermark(db)
    watermark_dt = _parse_zoho_timestamp(watermark_str)
    first_run = watermark_dt is None

    invoices = await zoho_service.list_invoices(per_page=100)
    if not invoices:
        logger.info("Zoho poll: checked 0 invoice(s), synced 0 (Zoho returned no invoices at all)")
        return {"status": "ok", "checked": 0, "synced": 0}

    target_user = await zoho_sync_service.get_target_user(db)

    to_sync = []
    newest_seen = watermark_str
    for inv in invoices:
        inv_modified_str = inv.get("last_modified_time")
        inv_modified_dt = _parse_zoho_timestamp(inv_modified_str)

        if not first_run and inv_modified_dt and watermark_dt and inv_modified_dt <= watermark_dt:
            # List is newest-first, so once we hit one at/before the
            # watermark, everything after it is old too — stop here.
            break

        to_sync.append(inv)

        # Track the newest timestamp we've seen this run, to save as
        # the new watermark once we're done.
        if inv_modified_str and (
            newest_seen is None or (inv_modified_dt and (_parse_zoho_timestamp(newest_seen) is None or inv_modified_dt > _parse_zoho_timestamp(newest_seen)))
        ):
            newest_seen = inv_modified_str

    synced = 0
    errors = 0
    for inv in to_sync:
        try:
            # list_invoices doesn't include full line-item detail, but
            # sync_one_invoice only needs the summary fields it already
            # has (totals, dates, customer info) — same fields
            # fetch_invoice would return for these purposes, so a
            # second per-invoice API call isn't needed here.
            await zoho_sync_service.sync_one_invoice(inv, db, target_user)
            synced += 1
        except Exception as e:
            errors += 1
            logger.error("Zoho poll: failed to sync invoice %s: %s", inv.get("invoice_number"), e)

    if newest_seen and newest_seen != watermark_str:
        await _save_watermark(db, newest_seen)

    logger.info(
        "Zoho poll: checked %d invoice(s), synced %d, %d error(s)%s",
        len(to_sync), synced, errors, " (first run — backfilled recent invoices)" if first_run else "",
    )
    return {"status": "ok", "checked": len(to_sync), "synced": synced, "errors": errors, "first_run": first_run}
