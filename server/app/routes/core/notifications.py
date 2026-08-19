"""
User notification endpoints.
"""
from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text
from app.database import get_db, engine
from app.models import User, PurchaseOrder, DefaulterCase, CreditReport, Settlement, Company, BusinessRequest, CompanyCredibilityIndex
from app.utils import ResponseFormatter, format_phone_e164
from app.dependencies import get_current_user, require_role, require_master_admin, is_developer
from app.models import Notification

from .common import *  # noqa: F401,F403 (logger + shared constants)

notifications_router = APIRouter()

@notifications_router.get("/notifications")
async def list_notifications(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], skip: int = 0, limit: int = 50):
    stmt = select(Notification).where(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    res = await db.execute(stmt)
    notes = res.scalars().all()
    return ResponseFormatter.create_success(data=[{
        "id": n.id,
        "type": n.type,
        "message": n.message,
        "related_po_id": n.related_po_id,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    } for n in notes])


@notifications_router.post("/notifications/{note_id}/read")
async def mark_notification_read(note_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    stmt = select(Notification).where(Notification.id == note_id, Notification.user_id == current_user.id)
    res = await db.execute(stmt)
    note = res.scalars().first()
    if not note:
        raise HTTPException(status_code=404, detail="Notification not found")
    note.is_read = True
    await db.commit()
    return ResponseFormatter.create_success(message="Notification marked as read")


