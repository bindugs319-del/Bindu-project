from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Appointment, User
from app.utils.response import ResponseFormatter

# Constants
APPOINTMENT_NOT_FOUND_ERROR = "Appointment not found"

router = APIRouter(prefix="/appointments", tags=["Appointments"])


def _parse_naive_datetime(value: str) -> datetime:
    """Parse a datetime string from the frontend into a naive datetime
    matching the DB column type.

    The frontend sends `new Date(...).toISOString()`, which always ends
    in "Z" (e.g. "2026-09-01T14:09:00.000Z"). On Python 3.11+,
    datetime.fromisoformat() correctly parses that "Z" and returns a
    timezone-AWARE datetime — but Appointment.appointment_date is a
    plain (naive) DateTime column ("timestamp without time zone" in
    Postgres). asyncpg refuses to bind a tz-aware datetime to a naive
    column and raises DataError ("can't subtract offset-naive and
    offset-aware datetimes"), which was crashing this endpoint with an
    unhandled exception on every submission.
    """
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


@router.post("", status_code=201)
async def create_appointment(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    data: dict
):
    """Create a new appointment"""
    required_fields = ["contact_name", "contact_email", "contact_phone", "appointment_date", "purpose"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required field(s): {', '.join(missing)}")

    try:
        appointment_date = _parse_naive_datetime(data["appointment_date"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Invalid appointment_date format")

    appointment = Appointment(
        id=str(uuid4()),
        user_id=current_user.id,
        contact_name=data["contact_name"],
        contact_email=data["contact_email"],
        contact_phone=data["contact_phone"],
        appointment_date=appointment_date,
        purpose=data["purpose"],
        notes=data.get("notes"),
        status="scheduled",
    )

    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)

    return ResponseFormatter.create_success(
        data={
            "id": appointment.id,
            "contact_name": appointment.contact_name,
            "contact_email": appointment.contact_email,
            "contact_phone": appointment.contact_phone,
            "appointment_date": appointment.appointment_date.isoformat(),
            "purpose": appointment.purpose,
            "status": appointment.status,
            "notes": appointment.notes,
            "created_at": appointment.created_at.isoformat(),
        },
        message="Appointment created successfully",
    )


@router.get("")
async def list_appointments(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """List appointments"""
    query = select(Appointment).where(Appointment.user_id == current_user.id)

    if status:
        query = query.where(Appointment.status == status)

    query = query.order_by(Appointment.appointment_date.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    appointments = result.scalars().all()

    return ResponseFormatter.create_success(
        data=[
            {
                "id": a.id,
                "contact_name": a.contact_name,
                "contact_email": a.contact_email,
                "contact_phone": a.contact_phone,
                "appointment_date": a.appointment_date.isoformat(),
                "purpose": a.purpose,
                "status": a.status,
                "notes": a.notes,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            }
            for a in appointments
        ]
    )


@router.get("/{appointment_id}")
async def get_appointment(
    appointment_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get appointment details"""
    result = await db.execute(
        select(Appointment).where(
            and_(Appointment.id == appointment_id, Appointment.user_id == current_user.id)
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=404, detail=APPOINTMENT_NOT_FOUND_ERROR)

    return ResponseFormatter.create_success(
        data={
            "id": appointment.id,
            "contact_name": appointment.contact_name,
            "contact_email": appointment.contact_email,
            "contact_phone": appointment.contact_phone,
            "appointment_date": appointment.appointment_date.isoformat(),
            "purpose": appointment.purpose,
            "status": appointment.status,
            "notes": appointment.notes,
            "created_at": appointment.created_at.isoformat(),
            "updated_at": appointment.updated_at.isoformat() if appointment.updated_at else None,
        }
    )


@router.put("/{appointment_id}")
async def update_appointment(
    appointment_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    data: dict
):
    """Update appointment"""
    result = await db.execute(
        select(Appointment).where(
            and_(Appointment.id == appointment_id, Appointment.user_id == current_user.id)
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=404, detail=APPOINTMENT_NOT_FOUND_ERROR)

    # Update fields
    if "contact_name" in data:
        appointment.contact_name = data["contact_name"]
    if "contact_email" in data:
        appointment.contact_email = data["contact_email"]
    if "contact_phone" in data:
        appointment.contact_phone = data["contact_phone"]
    if "appointment_date" in data:
        try:
            appointment.appointment_date = _parse_naive_datetime(data["appointment_date"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid appointment_date format")
    if "purpose" in data:
        appointment.purpose = data["purpose"]
    if "status" in data:
        appointment.status = data["status"]
    if "notes" in data:
        appointment.notes = data["notes"]

    await db.commit()
    await db.refresh(appointment)

    return ResponseFormatter.create_success(message="Appointment updated successfully")


@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Delete appointment"""
    result = await db.execute(
        select(Appointment).where(
            and_(Appointment.id == appointment_id, Appointment.user_id == current_user.id)
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=404, detail=APPOINTMENT_NOT_FOUND_ERROR)

    await db.delete(appointment)
    await db.commit()
