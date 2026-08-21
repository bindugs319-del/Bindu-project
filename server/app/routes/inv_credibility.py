"""
Invoice Credibility Index (inv_credibility_index)

Mirrors app/routes/credibility.py (the Purchase-Order-based "Local CBI")
but computes the same Local Credibility Index using SalesInvoice records
instead of PurchaseOrder records. Used to power the Inv Credibility Index
page on the frontend, which is the invoice-equivalent of the Credibility
Index page.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import timezone
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Company, Subscription, SalesInvoice, User
from app.utils.response import ResponseFormatter

router = APIRouter(prefix="/inv-credibility", tags=["Invoice Credibility"])


def score_invoice(payment_completed_at, payment_due_date, is_paid_no_dates=False):
    """Per-invoice credibility score (0-5), based on payment timing —
    mirrors score_po() in routes/credibility.py. Same 5/4/3/0 scale.
    payment_due_date is a Date column while payment_completed_at is
    DateTime, so we normalize to date-only before comparing.
    """
    if not is_paid_no_dates and payment_completed_at is None:
        return 0
    if payment_completed_at is None or payment_due_date is None:
        return 5
    paid_date = payment_completed_at.date() if hasattr(payment_completed_at, 'date') else payment_completed_at
    delay_days = (paid_date - payment_due_date).days
    if delay_days <= 0:
        return 5
    if delay_days <= 15:
        return 4
    return 3


async def get_invoice_stats(company_name: str, db: AsyncSession):
    # Fetch every invoice with this counterparty so we can score each one
    # individually (on-time vs late payment), rather than just a flat
    # paid/total ratio — mirrors get_po_stats() in routes/credibility.py.
    stmt = select(
        SalesInvoice.payment_due_date,
        SalesInvoice.payment_completed_at,
        SalesInvoice.status,
    ).where(func.lower(SalesInvoice.counterparty_name) == company_name.lower())

    res = await db.execute(stmt)
    rows = res.all()
    total = len(rows)

    paid = 0
    inv_scores = []
    for payment_due_date, payment_completed_at, inv_status in rows:
        is_paid = payment_completed_at is not None or (inv_status or '').lower() in ('paid', 'closed')
        if is_paid:
            paid += 1
        inv_scores.append(score_invoice(payment_completed_at, payment_due_date, is_paid_no_dates=is_paid))

    stars = round(sum(inv_scores) / len(inv_scores), 1) if inv_scores else 0
    stars = max(0.0, min(5.0, stars))
    return total, paid, stars


async def _has_active_subscription(user_id: str, db: AsyncSession) -> bool:
    stmt = select(Subscription).where(
        (Subscription.user_id == user_id) &
        (Subscription.is_active == True)
    ).order_by(Subscription.start_date.desc())
    res = await db.execute(stmt)
    sub = res.scalars().first()
    if not sub:
        return False
    if sub.expiry_date and sub.expiry_date < __import__("datetime").datetime.now(timezone.utc).replace(tzinfo=None):
        return False
    return True


@router.get("")
async def list_inv_credibility(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    role = str(getattr(current_user.role, "value", current_user.role) or "").upper()
    bypass = bool(getattr(current_user, "subscription_bypass", False)) or bool(getattr(current_user, "full_access", False))
    if role != "MASTER_ADMIN" and not bypass:
        if not await _has_active_subscription(current_user.id, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active subscription required")

    # Get all unique counterparty names from Sales Invoices
    stmt = select(SalesInvoice.counterparty_name).where(
        SalesInvoice.company_id == current_user.company_id
    ).distinct()
    res = await db.execute(stmt)
    counterparties = [r[0] for r in res.all() if r[0] and r[0].strip()]

    data = []
    for counterparty_name in counterparties:
        # Try to find real company ID for this counterparty name
        stmt_comp = select(Company.id).where(func.lower(Company.company_name) == counterparty_name.lower())
        res_comp = await db.execute(stmt_comp)
        real_id = res_comp.scalar() or counterparty_name

        total, paid, stars = await get_invoice_stats(counterparty_name, db)
        pct = (paid / total * 100) if total else 0
        score = min(100, round(pct))
        if score >= 90: grade = 'A'
        elif score >= 75: grade = 'B'
        elif score >= 60: grade = 'C'
        else: grade = 'D'
        if score >= 75: risk = 'Low'
        elif score >= 50: risk = 'Medium'
        else: risk = 'High'
        data.append({
            "company_id": real_id,
            "company_name": counterparty_name,
            "score": score,
            "grade": grade,
            "risk_level": risk,
            "stars": stars,
            "total_invoices": total,
            "paid_invoices": paid,
            # kept for compatibility with the PO credibility table shape
            "total_pos": total,
            "paid_pos": paid,
        })

    data.sort(key=lambda x: x['score'], reverse=True)
    return ResponseFormatter.create_success(data=data)


@router.get("/{company_id}")
async def get_inv_credibility(
    company_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    try:
        # Check if company_id is a name or UUID
        import uuid
        is_uuid = False
        try:
            uuid.UUID(company_id)
            is_uuid = True
        except ValueError:
            is_uuid = False

        counterparty_name = company_id
        if is_uuid:
            stmt = select(Company).where(Company.id == company_id)
            res = await db.execute(stmt)
            comp = res.scalars().first()
            if comp:
                counterparty_name = comp.company_name

        total, paid, stars = await get_invoice_stats(counterparty_name, db)

        score = round((paid / total * 100)) if total > 0 else 0
        grade = 'D'
        if score >= 90:
            grade = 'A'
        elif score >= 75:
            grade = 'B'
        elif score >= 50:
            grade = 'C'
        if score >= 80:
            risk = 'Low'
        elif score >= 50:
            risk = 'Medium'
        else:
            risk = 'High'

        data = {
            "company_name": counterparty_name,
            "score": score,
            "grade": grade,
            "risk_level": risk,
            "stars": stars,
            "metrics": {
                "total_pos": total,
                "total_invoices": total,
                "paid_on_time": paid,
                "paid_invoices": paid,
                "unpaid": total - paid,
                "fulfillment_rate": round((paid / total * 100)) if total > 0 else 0,
                "avg_delay_days": 0,
                "total_value": 0,
                "paid_value": 0,
                "unpaid_value": 0,
                "avg_value": 0
            }
        }
        return ResponseFormatter.create_success(data=data)
    except Exception:
        import traceback; traceback.print_exc()
        return ResponseFormatter.create_error("Internal server error", status_code=500)


@router.post("/{company_id}/ai-analysis")
async def get_inv_ai_analysis(
    company_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """AI-style analysis for a counterparty's invoice credibility, mirroring
    /credibility/{company_id}/ai-analysis but based on invoice fulfillment."""
    import uuid
    is_uuid = False
    try:
        uuid.UUID(company_id)
        is_uuid = True
    except ValueError:
        is_uuid = False

    counterparty_name = company_id
    if is_uuid:
        stmt = select(Company).where(Company.id == company_id)
        res = await db.execute(stmt)
        comp = res.scalars().first()
        if comp:
            counterparty_name = comp.company_name

    total, paid, stars = await get_invoice_stats(counterparty_name, db)
    score = round((paid / total * 100)) if total > 0 else 0
    grade = 'D'
    if score >= 90:
        grade = 'A'
    elif score >= 75:
        grade = 'B'
    elif score >= 50:
        grade = 'C'
    risk = 'Low' if score >= 80 else ('Medium' if score >= 50 else 'High')

    if score >= 80:
        verdict = "RECOMMENDED TO DEAL WITH"
    elif score >= 50:
        verdict = "PROCEED WITH CAUTION"
    else:
        verdict = "NOT RECOMMENDED"
    strength_desc = "strong" if score >= 80 else ("moderate" if score >= 50 else "poor")

    return ResponseFormatter.create_success(data={
        "verdict": verdict,
        "analysis_points": [
            f"Credit score is {score}/100 — {strength_desc}",
            f"Invoice fulfillment rate is {round(paid/total*100 if total else 0, 1)}%",
            f"Grade: {grade} | Risk Level: {risk}",
            f"Stars: {stars}/5"
        ],
        "cards": []
    })
