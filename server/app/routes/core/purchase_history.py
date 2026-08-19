"""
Purchase order history endpoint.
"""
from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text
from app.database import get_db, engine
from app.models import User, PurchaseOrder, DefaulterCase, CreditReport, Settlement, Company, BusinessRequest, CompanyCredibilityIndex
from app.utils import ResponseFormatter, format_phone_e164
from app.dependencies import get_current_user, require_role, require_master_admin, is_developer

from .common import *  # noqa: F401,F403 (logger + shared constants)

purchase_history_router = APIRouter()

@purchase_history_router.get("/purchase-history")
async def purchase_history(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """List user's completed or archived purchase orders"""
    stmt = (
        select(PurchaseOrder)
        .where(
            ((PurchaseOrder.company_id == current_user.company_id) | (PurchaseOrder.user_id == current_user.id)) &
            (or_(PurchaseOrder.status == "Completed", PurchaseOrder.archived == True))
        )
        .order_by(PurchaseOrder.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return ResponseFormatter.create_success(data=[{
        "id": p.id,
        "po_number": p.po_number,
        "vendor": p.vendor,
        "gstin": p.gstin,
        "amount": p.amount,
        "due_date": p.due_date.isoformat() if p.due_date else None,
        "status": p.status,
        "archived": p.archived,
        "document_url": p.document_url,
        "evidence_url": p.evidence_url,
        "approved_by": p.approved_by,
        "approved_at": p.approved_at.isoformat() if p.approved_at else None,
        "rejection_reason": p.rejection_reason,
        "notes": p.notes,
        "supplier_address": p.supplier_address,
        "delivery_address": p.delivery_address,
        "invoice_address": p.invoice_address,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    } for p in rows])


