"""
Purchase order lifecycle endpoints (create, approve, pay, archive, legal escalation).
"""
from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form
from typing import Annotated
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text, update as sa_update
from datetime import datetime, timezone
from app.database import get_db, engine
from app.models import User, PurchaseOrder, DefaulterCase, CreditReport, Settlement, Company, BusinessRequest, CompanyCredibilityIndex
from app.models.credibility_index import GlobalCredibilityIndex, CredibilityStatus, AICreditRiskVerdict
from app.schemas import (
    UpdateProfileRequest, UserProfileResponse, SubscriptionResponse, POApprovalRequest,
    GSTINCheckRequest, GSTINCheckResponse, BusinessRequestSchema, BusinessReportSubmit, BusinessRequestCreate,
    PurchaseOrderRequest, PurchaseOrderUpdate, GenericReasonRequest, ArchiveRequest, ReminderRequest,
    AdminSettingsRequest, OTPVerifyRequest, PhoneChangeRequest, EmailChangeRequest,
    DefaulterCaseRequest, DefaulterCaseUpdate, DefaulterVerifyRequest,
    CreditReportRequest, CreditReportResponse, CreditReportUpdate, CreditReportCompleteRequest,
    SettlementRequest, SettlementResponse, SettlementUpdate, ChatRequest
)
from app.services import UserService, OTPService, AccessControlService
from app.utils import ResponseFormatter, format_phone_e164
from app.dependencies import get_current_user, require_role, require_master_admin, is_developer
from app.exceptions import UnauthorizedFeature
from app.utils.phone import is_valid_phone
from app.config import settings
import uuid
import json
import os
import shutil
from app.services.email_service import EmailService, send_email_with_attachment
from app.services.legal_notice_service import generate_legal_notice_pdf
from app.services.notification_service import NotificationService
from app.utils.audit import log_audit

from .common import *  # noqa: F401,F403 (logger + shared constants)

po_router = APIRouter()
pos_router = APIRouter()

async def write_audit_log(db, po_id, po_number, action, user_email, user_role, reason="", changes=""): 
    try: 
        await db.execute( 
            text(""" 
                INSERT INTO po_audit_logs 
                (po_id, po_number, action, performed_by_email, performed_by_role, reason, changes_made) 
                VALUES (:po_id, :po_number, :action, :email, :role, :reason, :changes) 
            """), 
            { 
                "po_id": str(po_id), 
                "po_number": str(po_number), 
                "action": action, 
                "email": user_email, 
                "role": user_role, 
                "reason": reason, 
                "changes": changes 
            } 
        ) 
        await db.commit() 
    except Exception as e: 
        print(f"Audit log error: {e}") 


async def sync_vendor_credibility(vendor_name: str, db: AsyncSession, current_user=None): 
    try: 
        import uuid as uuid_lib 
        from datetime import datetime
        if not vendor_name or not vendor_name.strip(): 
            return 
        
        vendor_name = vendor_name.strip() 
        print(f"[SYNC] Starting sync for: {vendor_name}") 
        
        # 1. Check if company exists by name
        stmt = select(Company).where(func.lower(Company.company_name) == vendor_name.lower())
        res = await db.execute(stmt)
        existing = res.scalars().first()
        
        # 2. If not found by name, try finding the PO to get the real GSTIN
        if not existing:
            po_stmt = select(PurchaseOrder.gstin).where(PurchaseOrder.vendor == vendor_name).order_by(PurchaseOrder.created_at.desc()).limit(1)
            po_res = await db.execute(po_stmt)
            real_gstin = po_res.scalar() or 'PENDING'
            
            if real_gstin != 'PENDING':
                stmt_gstin = select(Company).where(Company.gstin == real_gstin)
                res_gstin = await db.execute(stmt_gstin)
                existing = res_gstin.scalars().first()
        else:
            real_gstin = existing.gstin

        if not existing: 
            domain = f"{vendor_name.lower().replace(' ', '')}.com"
            company_id = str(uuid_lib.uuid4()) 
            
            new_company = Company(
                id=company_id,
                company_name=vendor_name,
                gstin=real_gstin,
                domain_name=domain,
                is_verified=False
            )
            db.add(new_company)
            await db.flush() # Flush to get it in the session

            # Auto-add to Global Credibility Index
            gci_entry = GlobalCredibilityIndex(
                id=str(uuid.uuid4()),
                company_id=new_company.id,
                company_name=new_company.company_name,
                company_registration_no=None,
                partner_trust_score=0.0,
                ai_credit_risk_verdict=AICreditRiskVerdict.NOT_RATED,
                credibility_status=CredibilityStatus.STANDARD,
                approved_by_master_admin_id=None,
                credibility_review_id=None,
            )
            db.add(gci_entry)
            
            print(f"[SYNC] Created company: {vendor_name} -> {company_id}") 
            
            # AUDIT LOG for company creation
            if current_user:
                await log_audit(db, current_user, "CREATE", company=new_company, reason="Company auto-created via PO")
        else: 
            company_id = existing.id
            print(f"[SYNC] Company exists: {existing.company_name} ({existing.gstin}) -> {company_id}") 
        
        # Now recalc using ORM service 
        from app.services.credibility_service import CredibilityService 
        await CredibilityService.recalc_for_company(db, company_id) 
        await db.commit() 
        print(f"[SYNC] Credibility updated for: {vendor_name}") 
        
    except Exception as e: 
        import traceback 
        print(f"[SYNC ERROR] {vendor_name}: {e}") 
        traceback.print_exc() 


@po_router.post("/{po_id}/request-approval") 
async def request_po_edit_approval( 
    po_id: str, 
    request: Request, 
    db: Annotated[AsyncSession, Depends(get_db)], 
    current_user: Annotated[any, Depends(get_current_user)] 
): 
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    body = await request.json() 
    from sqlalchemy import select 
    po = (await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id))).scalar_one_or_none() 
    if not po: 
        raise HTTPException(404, "PO not found") 
    
    from app.services.workflow_service import WorkflowService 
    req_id = await WorkflowService.start_po_approval( 
        db=db, 
        po_id=po_id, 
        po_number=po.po_number, 
        requester_email=current_user.email, 
        edit_data=body.get('edit_data', {}), 
        evidence_url=body.get('evidence_url'), 
        evidence_filename=body.get('evidence_filename'), 
        reason=body.get('reason', 'PO Edit') 
    ) 
    return {"success": True, "message": "Edit submitted for approval. Financial team notified.", "data": {"request_id": req_id}}


@po_router.post("")
async def create_po(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    po_number: str = Form(None),
    vendor: str = Form(None),
    gstin: str = Form(None),
    vendor_email: str = Form(None),
    vendor_phone: str = Form(None),
    amount: float = Form(None),
    due_date: str = Form(None),
    status: str = Form("open"),
    notes: str = Form(None),
    document_url: str = Form(None),
    evidence_url: str = Form(None),
    supplier_address: str = Form(None),
    delivery_address: str = Form(None),
    invoice_address: str = Form(None),
    payment_window_days: int = Form(50),
    reason: str = Form(None),
    file: UploadFile = File(None)
):
    """Create purchase order with optional file upload"""
    import traceback
    import uuid
    try:
        role = str(getattr(current_user.role, "value", current_user.role) or "").upper()
        if role not in ["MASTER_ADMIN", "COMPANY_ADMIN"]:
            if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
                raise UnauthorizedFeature(PO_FEATURE_NAME)
        
        gstin_norm = gstin.strip().upper() if gstin else None
        
        # Convert due_date string to datetime object
        from datetime import datetime, date, timedelta
        due_date_obj = None
        if due_date and isinstance(due_date, str):
            # Try multiple date formats
            date_formats = [
                '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y', 
                '%Y/%m/%d', '%Y%m%d', '%d-%b-%Y'
            ]
            for fmt in date_formats:
                try:
                    due_date_obj = datetime.strptime(due_date.strip(), fmt)
                    break
                except ValueError:
                    continue
        elif due_date and isinstance(due_date, date) and not isinstance(due_date, datetime):
            due_date_obj = datetime.combine(due_date, datetime.min.time())
        elif due_date and isinstance(due_date, datetime):
            due_date_obj = due_date
        
        # Fallback to 30 days from now if no valid due date is provided
        if due_date_obj is None:
            due_date_obj = datetime.utcnow() + timedelta(days=30)
        
        document_url_final = document_url
        
        if file:
            import shutil
            import uuid
            from app.utils.uploads import get_upload_subdir
            
            upload_dir = get_upload_subdir("purchase_orders")
            filename = f"{uuid.uuid4()}_{file.filename}"
            filepath = upload_dir / filename
            
            with open(filepath, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            document_url_final = f"/uploads/purchase_orders/{filename}"
        
        po = PurchaseOrder(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            company_id=current_user.company_id,
            po_number=po_number,
            vendor=vendor,
            gstin=gstin_norm,
            vendor_email=vendor_email,
            vendor_phone=vendor_phone,
            amount=amount,
            due_date=due_date_obj,
            status="PENDING_APPROVAL" if evidence_url else status,
            approval_status="PENDING_APPROVAL" if evidence_url else None,
            notes=notes,
            document_url=document_url_final,
            evidence_url=evidence_url,
            supplier_address=supplier_address,
            delivery_address=delivery_address,
            invoice_address=invoice_address,
            payment_window_days=payment_window_days,
        )
        db.add(po)
        await db.commit()
        await db.refresh(po)
        return ResponseFormatter.create_success(data={"id": po.id}, message="PO created")
    except UnauthorizedFeature:
        # Let subscription-required errors surface as a proper 403 upgrade
        # prompt instead of being caught by the generic handler below.
        raise
    except Exception as e:
        error_msg = f"ERROR creating PO: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return JSONResponse(status_code=500, content={"success": False, "detail": str(e)})


@po_router.get("/search")
async def search_pos_for_reference(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str = "",
    limit: int = 10,
):
    """
    Lightweight PO lookup used by the invoice form's PO Number field, so a
    user can pick a real, existing PO number (and have vendor/GSTIN/date
    auto-filled) instead of typing free text. This is intentionally a soft
    reference, not a foreign key — sales_invoices.po_number stays a plain
    string column, so invoices remain independent of the PurchaseOrder
    table and are unaffected if a referenced PO is later edited or deleted.
    """
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    try:
        stmt = select(PurchaseOrder).where(
            PurchaseOrder.company_id == current_user.company_id,
            PurchaseOrder.archived == False,
        )
        if q:
            stmt = stmt.where(PurchaseOrder.po_number.ilike(f"%{q}%"))
        stmt = stmt.order_by(PurchaseOrder.created_at.desc()).limit(min(limit, 25))

        result = await db.execute(stmt)
        pos = result.scalars().all()

        return {
            "success": True,
            "data": [{
                "po_number": p.po_number,
                "po_date": p.created_at.date().isoformat() if p.created_at else None,
                "vendor": p.vendor,
                "gstin": p.gstin,
                "amount": p.amount,
                "due_date": p.due_date.isoformat() if p.due_date else None,
            } for p in pos]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search purchase orders: {str(e)}")


@po_router.get("")
async def list_pos(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    page_size: int = 20,
    include_archived: bool = False,
    skip: int = 0,
    limit: int = 20,
):
    """List user's purchase orders"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    try:
        # Support both page/page_size and skip/limit
        if page_size and page_size > 0:
            limit = min(int(page_size), 1000)
        if page and page > 1:
            skip = (int(page) - 1) * limit
        
        stmt = select(PurchaseOrder).where(PurchaseOrder.company_id == current_user.company_id)
        if not include_archived:
            stmt = stmt.where(PurchaseOrder.archived == False)
        stmt = stmt.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(stmt)
        pos = result.scalars().all()
        
        rows = [{
            "id": p.id,
            "po_number": p.po_number,
            "vendor": p.vendor,
            "gstin": p.gstin,
            "vendor_email": p.vendor_email,
            "vendor_phone": p.vendor_phone,
            "amount": p.amount,
            "due_date": p.due_date.isoformat() if p.due_date else None,
            "status": p.status,
            "archived": p.archived,
            "payment_completed_at": p.payment_completed_at.isoformat() if p.payment_completed_at else None,
            "payment_receipt_url": getattr(p, "payment_receipt_url", None),
            "payment_receipt_filename": getattr(p, "payment_receipt_filename", None),
            "payment_window_days": getattr(p, "payment_window_days", 50),
            "legal_notice_sent_at": p.legal_notice_sent_at.isoformat() if p.legal_notice_sent_at else None,
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
        } for p in pos]
        return ResponseFormatter.create_success(data=rows)
    except Exception as e:
        import traceback; print("PURCHASE ORDER LIST ERROR (fallback without archived filter):"); traceback.print_exc()
        try:
            # Fallback: run without archived filter to avoid column mismatch errors
            if page_size and page_size > 0:
                limit = min(int(page_size), 1000)
            if page and page > 1:
                skip = (int(page) - 1) * limit
            stmt2 = select(PurchaseOrder).where(PurchaseOrder.company_id == current_user.company_id).order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit)
            result2 = await db.execute(stmt2)
            pos2 = result2.scalars().all()
            rows2 = [{
                "id": p.id,
                "po_number": p.po_number,
                "vendor": p.vendor,
                "gstin": p.gstin,
                "vendor_email": p.vendor_email,
                "vendor_phone": p.vendor_phone,
                "amount": p.amount,
                "due_date": p.due_date.isoformat() if p.due_date else None,
                "status": p.status,
                "archived": getattr(p, "archived", False),
                "payment_completed_at": p.payment_completed_at.isoformat() if p.payment_completed_at else None,
                "payment_receipt_url": getattr(p, "payment_receipt_url", None),
                "payment_receipt_filename": getattr(p, "payment_receipt_filename", None),
                "payment_window_days": getattr(p, "payment_window_days", 50),
                "legal_notice_sent_at": p.legal_notice_sent_at.isoformat() if p.legal_notice_sent_at else None,
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
            } for p in pos2]
            return ResponseFormatter.create_success(data=rows2)
        except Exception:
            # Final fallback: empty list
            return ResponseFormatter.create_success(data=[])


@po_router.get("/pending-approvals-queue") 
async def get_pending_approvals_list( 
    db: Annotated[AsyncSession, Depends(get_db)], 
    current_user: Annotated[any, Depends(get_current_user)] 
): 
    # Role check: Allow Master Admin, Operations
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    ALLOWED_BASE_ROLES = ["MASTER_ADMIN", "OPERATION", "OPERATIONS"]
    
    # Check string values and enum values for compatibility
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]

    if user_role_val not in ALLOWED_BASE_ROLES: 
        raise HTTPException(status_code=403, detail="Access denied") 
    try: 
        result = await db.execute(text(""" 
            SELECT id, po_number, vendor, amount, due_date, created_at, evidence_url, pending_changes, approval_notes 
            FROM purchase_orders  
            WHERE approval_status = 'PENDING_APPROVAL' 
        """)) 
        rows = result.fetchall() 
        data = [] 
        for r in rows: 
            data.append({ 
                "id": r[0], "po_number": r[1], "vendor": r[2], "amount": float(r[3]),  
                "due_date": r[4].isoformat() if r[4] else None, 
                "created_at": r[5].isoformat() if r[5] else None, 
                "evidence_url": r[6], "pending_changes": r[7], "approval_notes": r[8] 
            }) 
        return ResponseFormatter.create_success(data=data) 
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e)) 


@po_router.get("/{po_id}")
async def get_po(po_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Get single purchase order"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    stmt = select(PurchaseOrder).where(
        (PurchaseOrder.id == po_id) & 
        ((PurchaseOrder.company_id == current_user.company_id) | (PurchaseOrder.user_id == current_user.id))
    )
    result = await db.execute(stmt)
    po = result.scalars().first()
    if not po:
        # Check if user is MASTER_ADMIN - they can view any PO
        if str(getattr(current_user.role, "value", current_user.role) or "").upper() == "MASTER_ADMIN":
            stmt_admin = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
            result_admin = await db.execute(stmt_admin)
            po = result_admin.scalars().first()
            
        if not po:
            raise HTTPException(status_code=404, detail=PO_NOT_FOUND_ERROR)
    return ResponseFormatter.create_success(data={
        "id": po.id,
        "po_number": po.po_number,
        "vendor": po.vendor,
        "gstin": po.gstin,
        "vendor_email": po.vendor_email,
        "vendor_phone": po.vendor_phone,
        "amount": po.amount,
        "due_date": po.due_date.isoformat() if po.due_date else None,
        "status": po.status,
        "archived": po.archived,
        "document_url": po.document_url,
        "evidence_url": po.evidence_url,
        "approved_by": po.approved_by,
        "approved_at": po.approved_at.isoformat() if po.approved_at else None,
        "rejection_reason": po.rejection_reason,
        "notes": po.notes,
        "supplier_address": po.supplier_address,
        "delivery_address": po.delivery_address,
        "invoice_address": po.invoice_address,
        "created_at": po.created_at.isoformat() if po.created_at else None,
        "updated_at": po.updated_at.isoformat() if po.updated_at else None
    })


@po_router.get("/{po_id}/receipt")
async def get_po_receipt(po_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Get payment receipt for a paid purchase order, and log the view."""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    stmt = select(PurchaseOrder).where(
        (PurchaseOrder.id == po_id) &
        ((PurchaseOrder.company_id == current_user.company_id) | (PurchaseOrder.user_id == current_user.id))
    )
    result = await db.execute(stmt)
    po = result.scalars().first()
    if not po and str(getattr(current_user.role, "value", current_user.role) or "").upper() == "MASTER_ADMIN":
        result_admin = await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id))
        po = result_admin.scalars().first()
    if not po:
        raise HTTPException(status_code=404, detail=PO_NOT_FOUND_ERROR)
    if str(po.status or "").upper() not in ("PAID", "CLOSED"):
        raise HTTPException(status_code=400, detail="No receipt available — this PO has not been marked as paid")

    from app.utils.audit import log_audit
    await log_audit(
        db, current_user, "RECEIPT_VIEWED", entity_obj=po,
        reason=f"Viewed payment receipt for PO {po.po_number}"
    )
    await db.commit()

    return ResponseFormatter.create_success(data={
        "id": po.id,
        "po_number": po.po_number,
        "vendor": po.vendor,
        "amount": po.amount,
        "status": po.status,
        "payment_completed_at": po.payment_completed_at.isoformat() if po.payment_completed_at else None,
        "payment_receipt_url": po.payment_receipt_url,
        "payment_receipt_filename": po.payment_receipt_filename,
    })


@po_router.put("/{po_id}")
async def update_po(po_id: str, req: PurchaseOrderUpdate, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Update purchase order"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    
    stmt = select(PurchaseOrder).where(
        (PurchaseOrder.id == po_id) & 
        ((PurchaseOrder.company_id == current_user.company_id) | (PurchaseOrder.user_id == current_user.id))
    )
    result = await db.execute(stmt)
    po = result.scalars().first()
    if not po:
        # MASTER_ADMIN can update any PO
        if str(getattr(current_user.role, "value", current_user.role) or "").upper() == "MASTER_ADMIN":
            stmt_admin = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
            result_admin = await db.execute(stmt_admin)
            po = result_admin.scalars().first()
            
        if not po:
            raise HTTPException(status_code=404, detail=PO_NOT_FOUND_ERROR)
    
    # Capture old data for audit
    old_data = {
        "po_number": po.po_number,
        "vendor": po.vendor,
        "gstin": po.gstin,
        "amount": po.amount,
        "status": po.status,
        "due_date": po.due_date.isoformat() if po.due_date else None,
        "notes": po.notes
    }
    
    # Update fields
    if po.payment_completed_at is not None:
        # Financially locked: prevent changes to critical fields
        locked_fields = {"status", "amount", "due_date"}
        req_data = req.model_dump(exclude_unset=True)
        attempted = locked_fields.intersection(set(req_data.keys()))
        if attempted:
            raise HTTPException(status_code=400, detail="Cannot modify paid purchase order")
            
    if req.po_number is not None:
        po.po_number = req.po_number
    if req.vendor is not None:
        po.vendor = req.vendor
    if req.gstin is not None:
        po.gstin = req.gstin.upper()
    if req.vendor_email is not None:
        email_val = (req.vendor_email or "").strip().lower()
        if email_val and "@" not in email_val:
            raise HTTPException(status_code=400, detail="Invalid vendor email")
        po.vendor_email = email_val or None
    if req.vendor_phone is not None:
        phone_raw = (req.vendor_phone or "").strip()
        if phone_raw:
            phone_fmt = format_phone_e164(phone_raw) or phone_raw
            if not is_valid_phone(phone_fmt):
                raise HTTPException(status_code=400, detail="Invalid vendor phone")
            po.vendor_phone = phone_fmt
        else:
            po.vendor_phone = None
    if req.amount is not None:
        po.amount = req.amount
    if req.status is not None:
        if po.payment_completed_at is not None:
            raise HTTPException(status_code=400, detail="Cannot change status of paid purchase order")
        po.status = req.status
    if req.notes is not None:
        po.notes = req.notes
    if req.document_url is not None:
        po.document_url = req.document_url
    if req.evidence_url is not None:
        po.evidence_url = req.evidence_url
        po.status = "PENDING_APPROVAL"
    if req.supplier_address is not None:
        po.supplier_address = req.supplier_address
    if req.delivery_address is not None:
        po.delivery_address = req.delivery_address
    if req.invoice_address is not None:
        po.invoice_address = req.invoice_address
    if req.payment_window_days is not None:
        po.payment_window_days = req.payment_window_days
    
    po.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    # Note: a "PO Paid" notification used to fire here unconditionally on
    # every edit to this endpoint (even unrelated fields like
    # invoice_address), via a NotificationService.notify_po_paid() method
    # that was never actually defined — so it silently did nothing anyway.
    # The correct paid-notification already lives in the dedicated
    # /{po_id}/mark-paid endpoint, which is the only place that should
    # fire it.

    # Audit log (Requirement 2: Ensure logging)
    await log_audit(
        db=db,
        user=current_user,
        action="PO_UPDATED",
        entity_obj=po,
        reason=req.reason or f"PO {po.po_number} updated",
        old_data=old_data,
        new_data=req.model_dump(exclude_unset=True)
    )
    
    # Send update notifications to both companies, include pending alert and credibility
    try:
        svc = EmailService()
        # Company admins (buyer)
        rec_stmt = select(User.email).where(
            (User.company_id == current_user.company_id) &
            (User.is_active == True) &
            (User.role.in_(["MASTER_ADMIN", "COMPANY_ADMIN"]))
        )
        rec_res = await db.execute(rec_stmt)
        recipients = [r[0] for r in rec_res.all()]
        if current_user.email and current_user.email not in recipients:
            recipients.append(current_user.email)
        from app.models import CompanyCredibilityIndex, Company
        idx_stmt = select(CompanyCredibilityIndex).where(CompanyCredibilityIndex.company_id == current_user.company_id)
        idx_res = await db.execute(idx_stmt)
        idx = idx_res.scalars().first()
        subj = f"PO {po.po_number} updated"
        pending_alert = ""
        if str(po.status or "").lower().find("pending") >= 0:
            pending_alert = "\nPending alert: This PO is currently pending."
        body_lines = [
            f"PO Number: {po.po_number}",
            f"Vendor: {po.vendor}",
            f"GSTIN: {po.gstin}",
            f"Amount: {po.amount}",
            f"Due Date: {po.due_date.date() if po.due_date else ''}",
            f"Status: {po.status}",
        ]
        if idx:
            body_lines.append(f"Credibility Index: {idx.score} (Grade {idx.grade}, Risk {idx.risk_level})")
        body = "\n".join(body_lines) + pending_alert
        for to in recipients:
            await svc.send_email(to, subj, body)
        # Vendor admins
        vendor_company_stmt = select(Company).where(Company.gstin == po.gstin)
        vres = await db.execute(vendor_company_stmt)
        vcompany = vres.scalars().first()
        if vcompany:
            admin_stmt = select(User).where(
                (User.company_id == vcompany.id) &
                (User.is_active == True) &
                (User.role.in_(["MASTER_ADMIN", "COMPANY_ADMIN"]))
            )
            admin_res = await db.execute(admin_stmt)
            admins = admin_res.scalars().all()
            subj_v = f"PO {po.po_number} updated by {current_user.company_name}"
            body_v_lines = [
                f"PO Number: {po.po_number}",
                f"Vendor: {po.vendor}",
                f"Company: {current_user.company_name}",
                f"GSTIN: {po.gstin}",
                f"Amount: {po.amount}",
                f"Due Date: {po.due_date.date() if po.due_date else ''}",
                f"Status: {po.status}",
            ]
            if idx:
                body_v_lines.append(f"Buyer Credibility Index: {idx.score} (Grade {idx.grade}, Risk {idx.risk_level})")
            if str(po.status or '').lower().find('pending') >= 0:
                body_v_lines.append("Pending alert: This PO is currently pending.")
            body_v = "\n".join(body_v_lines)
            for admin in admins:
                if admin.email:
                    await svc.send_email(admin.email, subj_v, body_v)
    except Exception as e:
        logger.warning(f"[PO] Failed to notify vendor admins for PO {po.po_number}: {e}")

    await sync_vendor_credibility(po.vendor, db, current_user)
    
    await log_audit(
        db=db,
        user=current_user,
        action="PO_UPDATED",
        entity_obj=po,
        old_data=old_data,
        new_data=req.model_dump(exclude_unset=True),
        reason=req.reason or "PO updated"
    )
    return ResponseFormatter.create_success(data={"id": po.id}, message="PO updated successfully")


@po_router.post("/{po_id}/submit-for-approval") 
async def submit_po_for_approval( 
    po_id: str, 
    request: Request, 
    db: Annotated[AsyncSession, Depends(get_db)], 
    current_user: Annotated[any, Depends(get_current_user)] 
): 
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    try: 
        body = await request.json() 
        evidence_url = body.get('evidence_url', '') 
        pending_changes = body.get('pending_changes', {}) 
        notes = body.get('notes', '') 
 
        await db.execute(text(""" 
            UPDATE purchase_orders SET 
                approval_status = 'PENDING_APPROVAL', 
                evidence_url = :evidence_url, 
                pending_changes = :pending_changes, 
                approval_notes = :notes 
            WHERE id = :id 
        """), { 
            "evidence_url": evidence_url, 
            "pending_changes": json.dumps(pending_changes), 
            "notes": notes, 
            "id": po_id 
        }) 
 
        # Integration with NEW WORKFLOW SYSTEM
        try:
            from app.services.workflow_service import WorkflowService
            # Get PO number for workflow
            po_stmt = select(PurchaseOrder.po_number).where(PurchaseOrder.id == po_id)
            po_res = await db.execute(po_stmt)
            po_number = po_res.scalar() or "Unknown PO"
            
            await WorkflowService.start_po_approval(
                db=db,
                po_id=po_id,
                po_number=po_number,
                requester_email=current_user.email,
                edit_data=pending_changes,
                evidence_url=evidence_url,
                evidence_filename='',
                reason=notes
            )
        except Exception as workflow_err:
            logger.error(f"Failed to trigger PO workflow: {workflow_err}")

        # Trigger notifications
        try:
            await NotificationService.notify_po_approval_submitted(db, po_number)
        except Exception as e:
            logger.warning(f"Failed to trigger approval notification: {e}")

        await db.commit()
        return {"success": True, "message": "PO submitted for approval successfully"} 
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e)) 


@po_router.post("/{po_id}/approve-edit") 
async def approve_po_edit( 
    po_id: str, 
    request: Request, 
    db: Annotated[AsyncSession, Depends(get_db)], 
    current_user: Annotated[any, Depends(get_current_user)] 
): 
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    if current_user.role not in ['MASTER_ADMIN', 'FINANCIAL'] and not is_developer(current_user): 
        raise HTTPException(status_code=403, detail="Access denied") 
    try: 
        body = await request.json() 
        notes = body.get('notes', 'Approved') 
 
        # Get pending changes 
        result = await db.execute(text(""" 
            SELECT pending_changes FROM purchase_orders WHERE id = :id 
        """), {"id": po_id}) 
        row = result.fetchone() 
        if not row: 
            raise HTTPException(status_code=404, detail="PO not found") 
 
        pending = {} 
        if row[0]: 
            import json as json_lib 
            pending = json_lib.loads(row[0]) if isinstance(row[0], str) else row[0] 
 
        # Apply pending changes 
        if pending: 
            import json as json_lib
            # Ensure pending is a dict
            if isinstance(pending, str):
                try:
                    pending = json_lib.loads(pending)
                except Exception as e:
                    logger.warning(f"[PO] Failed to parse pending_changes JSON for PO {po_id}: {e}")
            
            if isinstance(pending, dict) and pending:
                # SECURITY: only these columns may ever be updated via pending_changes.
                # pending_changes originates from user-submitted request bodies
                # (see submit_po_for_approval above), so its keys must never be
                # trusted as raw SQL column names without this whitelist.
                ALLOWED_PO_EDIT_FIELDS = {
                    "vendor", "gstin", "amount", "due_date", "evidence_url",
                    "po_number", "notes", "vendor_email", "vendor_phone",
                    "supplier_address", "delivery_address", "invoice_address"
                }
                if any(k in ALLOWED_PO_EDIT_FIELDS for k in pending):
                    # Use SQLAlchemy Core's update() construct instead of a raw
                    # SQL string here — with the ORM's expression builder there's
                    # no SQL text assembled from dynamic content at all, which is
                    # both safer and avoids static-analysis "dynamic SQL" flags
                    # that a hand-built SET clause triggers even when validated.
                    safe_values = {
                        k: v for k, v in pending.items() if k in ALLOWED_PO_EDIT_FIELDS
                    }
                    await db.execute(
                        sa_update(PurchaseOrder)
                        .where(PurchaseOrder.id == po_id)
                        .values(**safe_values)
                    )
 
        # Clear approval status 
        await db.execute(text(""" 
            UPDATE purchase_orders SET 
                approval_status = 'APPROVED', 
                approved_by = :approver, 
                approved_at = CURRENT_TIMESTAMP, 
                approval_notes = :notes, 
                pending_changes = NULL 
            WHERE id = :id 
        """), {"approver": current_user.email, "notes": notes, "id": po_id}) 
 
        await write_audit_log( 
            db, po_id, po_id, "EDIT_APPROVED", 
            current_user.email, current_user.role, reason=notes 
        ) 
 
        await db.commit() 

        # Notify whoever submitted the edit that it was approved
        try:
            from app.services.notification_service import NotificationService
            owner_stmt = select(User.email).where(
                User.id == select(PurchaseOrder.user_id).where(PurchaseOrder.id == po_id).scalar_subquery()
            )
            owner_email = (await db.execute(owner_stmt)).scalar()
            if owner_email:
                await NotificationService.send(
                    db, owner_email,
                    title="PO Edit Approved",
                    message=f"Your PO edit was approved.\n\nNotes: {notes}",
                    ntype="PO",
                    action_url="/purchase-orders",
                    related_po_id=po_id,
                )
        except Exception as e:
            print(f"[PO_EDIT_APPROVE] Failed to send notification: {e}")

        return {"success": True, "message": "PO edit approved and applied"} 
    except HTTPException: 
        raise 
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e)) 


@po_router.post("/{po_id}/reject-edit") 
async def reject_po_edit( 
    po_id: str, 
    request: Request, 
    db: Annotated[AsyncSession, Depends(get_db)], 
    current_user: Annotated[any, Depends(get_current_user)] 
): 
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    if current_user.role not in ['MASTER_ADMIN', 'FINANCIAL'] and not is_developer(current_user): 
        raise HTTPException(status_code=403, detail="Access denied") 
    try: 
        body = await request.json() 
        notes = body.get('notes', 'Rejected') 
 
        await db.execute(text(""" 
            UPDATE purchase_orders SET 
                approval_status = 'REJECTED', 
                approved_by = :approver, 
                approved_at = CURRENT_TIMESTAMP, 
                approval_notes = :notes, 
                pending_changes = NULL 
            WHERE id = :id 
        """), {"approver": current_user.email, "notes": notes, "id": po_id}) 
 
        await write_audit_log( 
            db, po_id, po_id, "EDIT_REJECTED", 
            current_user.email, current_user.role, reason=notes 
        ) 
 
        await db.commit() 

        # Notify whoever submitted the edit that it was rejected
        try:
            from app.services.notification_service import NotificationService
            owner_stmt = select(User.email).where(
                User.id == select(PurchaseOrder.user_id).where(PurchaseOrder.id == po_id).scalar_subquery()
            )
            owner_email = (await db.execute(owner_stmt)).scalar()
            if owner_email:
                await NotificationService.send(
                    db, owner_email,
                    title="PO Edit Rejected",
                    message=f"Your PO edit was rejected.\n\nReason: {notes}",
                    ntype="PO",
                    action_url="/purchase-orders",
                    related_po_id=po_id,
                )
        except Exception as e:
            print(f"[PO_EDIT_REJECT] Failed to send notification: {e}")

        return {"success": True, "message": "PO edit rejected"} 
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e)) 


@po_router.get("/pending-approvals") 
async def get_pending_approvals( 
    db: Annotated[AsyncSession, Depends(get_db)], 
    current_user: Annotated[any, Depends(get_current_user)] 
): 
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    if current_user.role not in ['MASTER_ADMIN', 'FINANCIAL'] and not is_developer(current_user): 
        raise HTTPException(status_code=403, detail="Access denied") 
    result = await db.execute(text(""" 
        SELECT id, po_number, vendor, amount, due_date, status, 
               approval_status, evidence_url, approval_notes, 
               pending_changes, created_at 
        FROM purchase_orders 
        WHERE approval_status = 'PENDING_APPROVAL' 
        ORDER BY created_at DESC 
    """)) 
    rows = [dict(r._mapping) for r in result.fetchall()] 
    return {"success": True, "data": rows}


@po_router.post("/{po_id}/mark-paid")
async def mark_paid(
    po_id: str, 
    current_user: Annotated[User, Depends(get_current_user)], 
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: str = Form(...),
    file: UploadFile = File(None)
):
    """Mark purchase order as paid (immutable financial action)"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    try:
        role = str(getattr(current_user.role, "value", current_user.role) or "").upper()
        
        # Check if user is authorized (MASTER_ADMIN, COMPANY_ADMIN, OR any user from the PO's company)
        if role == "MASTER_ADMIN":
            stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
        else:
            # User must belong to the same company as the PO
            stmt = select(PurchaseOrder).where(
                (PurchaseOrder.id == po_id) & 
                (PurchaseOrder.company_id == current_user.company_id)
            )
            
        result = await db.execute(stmt)
        po = result.scalars().first()
        if not po:
            # Fallback check by user_id for legacy POs or if company_id is missing on PO
            stmt_fallback = select(PurchaseOrder).where(
                (PurchaseOrder.id == po_id) & (PurchaseOrder.user_id == current_user.id)
            )
            res_fallback = await db.execute(stmt_fallback)
            po = res_fallback.scalars().first()
            if not po:
                raise HTTPException(status_code=404, detail="Purchase Order not found or access denied")
                
        if po.payment_completed_at is not None:
            raise HTTPException(status_code=400, detail="Already marked paid")
        
        # Handle file upload if provided
        if file:
            import shutil
            import uuid
            from app.utils.uploads import get_upload_subdir
            
            upload_dir = get_upload_subdir("payment_receipts")
            
            filename = f"{uuid.uuid4()}_{file.filename}"
            filepath = upload_dir / filename
            
            with open(filepath, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            po.payment_receipt_url = f"{settings.BASE_URL}/uploads/payment_receipts/{filename}"
            po.payment_receipt_filename = file.filename
        
        # Update status to PAID as requested
        po.status = "PAID"
        po.payment_completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        po.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        await db.commit()
        
        # Audit log (Requirement 2: Ensure logging)
        await log_audit(
            db=db,
            user=current_user,
            action="PO_MARKED_PAID",
            entity_obj=po,
            reason=reason or f"PO {po.po_number} marked as paid"
        )
        
        # Notification: Mark Paid — use NotificationService.send() (not a
        # bare Notification(...) row) so user_email gets set; otherwise the
        # notification silently never shows up, since the read path
        # filters strictly on user_email.
        try:
            from app.services.notification_service import NotificationService
            if current_user.email:
                await NotificationService.send(
                    db, current_user.email,
                    title="PO Marked Paid",
                    message=f"PO {po.po_number} marked as paid",
                    ntype="PO_MARK_PAID",
                    action_url="/purchase-orders",
                    related_po_id=po.id,
                    send_email=False,  # the block below already emails admins
                )
        except Exception as e:
            print(f"[MARK_PAID] Failed to send in-app notification: {e}")
        
        # Email notification to admins
        try:
            svc = EmailService()
            rec_stmt = select(User.email).where(
                (User.company_id == current_user.company_id) &
                (User.is_active == True) &
                (User.role.in_(["MASTER_ADMIN", "COMPANY_ADMIN"]))
            )
            rec_res = await db.execute(rec_stmt)
            recipients = [r[0] for r in rec_res.all()]
            if current_user.email and current_user.email not in recipients:
                recipients.append(current_user.email)
                
            subj = f"PO {po.po_number} marked paid"
            body = f"PO {po.po_number} marked paid on {po.payment_completed_at.date()}"
            for to in recipients:
                await svc.send_email(to, subj, body)
        except Exception as e:
            logger.warning(f"[PO] Failed to send 'marked paid' notification for PO {po.po_number}: {e}")

        await sync_vendor_credibility(po.vendor, db, current_user)

        return ResponseFormatter.create_success(message="PO marked as paid successfully")
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        print("MARK PAID ERROR TRACEBACK:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@po_router.post("/{po_id}/upload-receipt")
async def upload_payment_receipt(
    po_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...)
):
    """Upload payment receipt for a purchase order"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    import shutil
    import uuid
    from app.utils.uploads import get_upload_subdir

    try:
        upload_dir = get_upload_subdir("payment_receipts")
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = upload_dir / filename

        with open(filepath, "wb") as f:
            shutil.copyfileobj(file.file, f)

        url = f"{settings.BASE_URL}/uploads/payment_receipts/{filename}"
        return ResponseFormatter.create_success(data={"url": url, "filename": file.filename})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@po_router.get("/financial/payment-activity")
async def get_payment_activity(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Get payment activity for financial dashboard (financial/master admin only)"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    role = str(getattr(current_user.role, "value", current_user.role) or "").upper()
    print(f"[PAYMENT ACTIVITY] Current user role: {repr(role)}, allowed roles: ['MASTER_ADMIN', 'FINANCIAL', 'FINANCE']")
    if role not in ["MASTER_ADMIN", "FINANCIAL", "FINANCE"]:
        raise HTTPException(status_code=403, detail="Financial team only")

    dburl = str(engine.url)
    is_sqlite = dburl.startswith("sqlite")

    try:
        result = await db.execute(text("""
            SELECT
                po.id,
                po.po_number,
                po.vendor,
                po.amount,
                po.payment_completed_at as paid_at,
                po.payment_receipt_url,
                po.payment_receipt_filename,
                al.reason,
                al.user_email,
                al.created_at
            FROM purchase_orders po
            LEFT JOIN audit_logs al ON al.entity_id = po.id
                AND al.action = 'PO_MARKED_PAID'
            WHERE po.status IN ('PAID', 'Closed')
                AND po.payment_completed_at IS NOT NULL
            ORDER BY po.payment_completed_at DESC
            LIMIT 50
        """))

        rows = result.mappings().all()
        data = []
        for row in rows:
            d = dict(row)
            for k, v in d.items():
                if v is not None and not isinstance(v, (int, float, bool, str)):
                    d[k] = str(v)
            data.append(d)

        return ResponseFormatter.create_success(data=data)
    except Exception as e:
        import traceback
        print(f"[PAYMENT ACTIVITY] Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get payment activity: {str(e)}")


@po_router.get("/workflow/pending")
async def list_pending_pos(
    current_user: Annotated[any, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List POs pending approval (MASTER_ADMIN only)"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    stmt = select(PurchaseOrder).where(PurchaseOrder.status == "PENDING_APPROVAL")
    result = await db.execute(stmt)
    pos = result.scalars().all()
    
    return ResponseFormatter.create_success(data=[{
        "id": p.id,
        "po_number": p.po_number,
        "vendor": p.vendor,
        "amount": p.amount,
        "document_url": p.document_url,
        "evidence_url": p.evidence_url,
        "created_at": p.created_at.isoformat()
    } for p in pos])


@po_router.post("/{po_id}/process-approval")
async def process_po_approval(
    po_id: str,
    req: POApprovalRequest,
    current_user: Annotated[any, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Approve or Reject PO evidence (MASTER_ADMIN only)"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
    result = await db.execute(stmt)
    po = result.scalars().first()
    
    if not po:
        raise HTTPException(status_code=404, detail=PO_NOT_FOUND_ERROR)
    
    # DateTime columns here are timezone-naive; datetime.now(timezone.utc)
    # is tz-aware and makes asyncpg fail with "can't subtract offset-naive
    # and offset-aware datetimes" at commit time. Use naive UTC instead.
    now = datetime.utcnow()

    if req.action == "APPROVE":
        po.status = "VERIFIED"
        po.approved_by = current_user.id
        po.approved_at = now
        po.rejection_reason = None
        action_log = "APPROVE"
        msg = "PO evidence approved"
    else:
        po.status = "REJECTED"
        po.rejection_reason = req.reason
        po.approved_by = current_user.id
        po.approved_at = now
        action_log = "REJECT"
        msg = f"PO evidence rejected: {req.reason}"
    
    po.updated_at = now
    
    await log_audit(
        db=db,
        user=current_user,
        action="PO_APPROVED" if req.action == "APPROVE" else "PO_REJECTED",
        entity_obj=po,
        reason=req.reason if req.action != "APPROVE" else None
    )
    await db.commit()

    # Notify the PO owner of the decision
    try:
        owner_stmt = select(User.email).where(User.id == po.user_id)
        owner_result = await db.execute(owner_stmt)
        owner_email = owner_result.scalar()
        if owner_email:
            from app.services.notification_service import NotificationService
            if req.action == "APPROVE":
                await NotificationService.send(
                    db, owner_email,
                    title="PO Evidence Approved",
                    message=f"Your evidence for PO {po.po_number} has been approved.",
                    ntype="PO",
                    action_url="http://localhost:3001/purchase-orders",
                    related_po_id=po.id,
                )
            else:
                await NotificationService.send(
                    db, owner_email,
                    title="PO Evidence Rejected",
                    message=f"Your evidence for PO {po.po_number} was rejected: {req.reason or 'No reason provided'}",
                    ntype="PO",
                    action_url="http://localhost:3001/purchase-orders",
                    related_po_id=po.id,
                )
    except Exception as e:
        logger.error(f"[PO_APPROVAL] Failed to send notification: {e}")
    
    return ResponseFormatter.create_success(message=msg)


@po_router.post("/{po_id}/reject")
async def reject_po(
    po_id: str,
    payload: dict,
    current_user: Annotated[any, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Reject PO evidence (MASTER_ADMIN only)"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    reason = payload.get("reason", "No reason provided")
    stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
    result = await db.execute(stmt)
    po = result.scalars().first()
    
    if not po:
        raise HTTPException(status_code=404, detail=PO_NOT_FOUND_ERROR)
        
    po.status = "REJECTED"
    po.updated_at = datetime.utcnow()  # naive UTC — see note in process_po_approval above
    
    await log_audit(
        db=db,
        user=current_user,
        action="PO_REJECTED",
        entity_obj=po,
        reason=reason
    )
    await db.commit()

    try:
        owner_stmt = select(User.email).where(User.id == po.user_id)
        owner_result = await db.execute(owner_stmt)
        owner_email = owner_result.scalar()
        if owner_email:
            from app.services.notification_service import NotificationService
            await NotificationService.send(
                db, owner_email,
                title="PO Rejected",
                message=f"Your PO {po.po_number} was rejected: {reason}",
                ntype="PO",
                action_url="http://localhost:3001/purchase-orders",
                related_po_id=po.id,
            )
    except Exception as e:
        logger.error(f"[PO_REJECT] Failed to send notification: {e}")
    
    return ResponseFormatter.create_success(message="PO rejected successfully")


@po_router.delete("/{po_id}")
async def delete_po(po_id: str, req: GenericReasonRequest, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Delete purchase order"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    
    stmt = select(PurchaseOrder).where(
        (PurchaseOrder.id == po_id) & 
        ((PurchaseOrder.company_id == current_user.company_id) | (PurchaseOrder.user_id == current_user.id))
    )
    result = await db.execute(stmt)
    po = result.scalars().first()
    if not po:
        # MASTER_ADMIN can delete any PO
        if str(getattr(current_user.role, "value", current_user.role) or "").upper() == "MASTER_ADMIN":
            stmt_admin = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
            result_admin = await db.execute(stmt_admin)
            po = result_admin.scalars().first()
            
        if not po:
            raise HTTPException(status_code=404, detail=PO_NOT_FOUND_ERROR)
    
    await log_audit(
        db=db,
        user=current_user,
        action="PO_DELETED",
        entity_obj=po,
        reason=req.reason or "PO deleted"
    )
    await db.delete(po)
    await db.commit()
    return ResponseFormatter.create_success(message="PO deleted successfully")


@po_router.post("/{po_id}/archive")
async def archive_po(po_id: str, req: ArchiveRequest, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Archive/unarchive purchase order"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    stmt = select(PurchaseOrder).where((PurchaseOrder.id == po_id) & (PurchaseOrder.user_id == current_user.id))
    result = await db.execute(stmt)
    po = result.scalars().first()
    if not po:
        raise HTTPException(status_code=404, detail=PO_NOT_FOUND_ERROR)
    
    po.archived = not po.archived
    po.updated_at = datetime.now(timezone.utc)
    
    await log_audit(
        db=db,
        user=current_user,
        action="PO_ARCHIVED" if po.archived else "PO_UNARCHIVED",
        entity_obj=po,
        reason=req.reason
    )
    await db.commit()
    return ResponseFormatter.create_success(data={"is_archived": po.archived}, message="PO archive status updated")


@po_router.post("/{po_id}/send-reminder")
async def send_vendor_reminder(po_id: str, req: ReminderRequest, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Manually send or schedule reminder email to vendor for a specific PO"""
    # Fetch PO for current user
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    stmt = select(PurchaseOrder, User).join(User, PurchaseOrder.user_id == User.id).where(
        (PurchaseOrder.id == po_id) & (PurchaseOrder.user_id == current_user.id)
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail=PO_NOT_FOUND_ERROR)
    po, owner = row
    
    # Require vendor email
    v_email = (po.vendor_email or "").strip()
    if not v_email:
        raise HTTPException(status_code=400, detail="No vendor email configured for this PO")

    # Use custom content if provided, otherwise fallback to template
    subject = req.subject
    body = req.body
    scheduled_at = req.scheduled_at
    include_legal_notice = req.include_legal_notice
    legal_notice_content = req.legal_notice_content

    if not subject or not body:
        # Compose email from template if not provided in request
        try:
            from app.models import POReminderConfig
            cfg_res = await db.execute(select(POReminderConfig))
            cfg = cfg_res.scalars().first()
        except Exception:
            cfg = None

        due_date_str = po.due_date.date().isoformat() if po.due_date else "N/A"
        amount_str = f"₹{po.amount:,.2f}"
        
        def format_val(template, default_val):
            if not template:
                return default_val
            return template.replace("{vendor_name}", po.vendor or "") \
                           .replace("{amount}", amount_str) \
                           .replace("{due_date}", due_date_str) \
                           .replace("{po_number}", po.po_number or "")

        if not subject:
            subject = format_val(cfg.reminder_subject if cfg else None, f"Payment Reminder: PO {po.po_number} due on {due_date_str}")
        if not body:
            body = format_val(cfg.reminder_body if cfg else None, (
                f"Dear {po.vendor or 'Vendor'},\n\n"
                f"This is a reminder that Purchase Order {po.po_number} for amount {amount_str} "
                f"is due on {due_date_str}. Please arrange payment at the earliest.\n\n"
                f"Regards,\n{owner.company_name or 'Your Customer'}"
            ))

    if scheduled_at:
        try:
            # Parse datetime-local format (YYYY-MM-DDTHH:MM) or ISO
            s = str(scheduled_at).replace("Z", "+00:00")
            if "T" in s and "+" not in s and s.count(":") == 1:
                # Add seconds if missing from datetime-local
                s += ":00"
            
            sched_dt = datetime.fromisoformat(s)
            if sched_dt.tzinfo:
                sched_dt = sched_dt.astimezone(timezone.utc).replace(tzinfo=None)
            
            from app.models import ScheduledReminder
            import uuid
            sr = ScheduledReminder(
                id=str(uuid.uuid4()),
                purchase_order_id=po.id,
                user_id=current_user.id,
                subject=subject,
                body=body,
                scheduled_at=sched_dt
            )
            db.add(sr)
            await db.commit()
            
            await log_audit(
                db=db,
                user=current_user,
                action="PO_REMINDER_SCHEDULED",
                entity_obj=po,
                reason=f"Scheduled for {sched_dt.isoformat()}"
            )
            return ResponseFormatter.create_success(message=f"Reminder scheduled for {sched_dt.isoformat()}")
        except Exception as e:
            logger.error(f"Failed to schedule reminder: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid scheduled_at format")

    # Send email NOW
    try:
        if include_legal_notice:
            # Ensure temp directory exists
            from app.utils.uploads import get_upload_subdir
            temp_dir_path = get_upload_subdir("temp")
            
            # Generate PDF
            pdf_path = str(temp_dir_path / f"legal_notice_{po_id}.pdf")
            po_data = {
                "vendor": po.vendor,
                "po_number": po.po_number,
                "amount": po.amount,
                "due_date": str(po.due_date),
                "company_name": owner.company_name or "Company"
            }
            generate_legal_notice_pdf(po_data, pdf_path, legal_notice_content)
            
            # Send with attachment
            await send_email_with_attachment(
                to_email=v_email,
                subject=subject,
                body=body,
                attachment_path=pdf_path,
                attachment_name=f"Legal_Notice_{po.po_number}.pdf"
            )
            
            # Cleanup
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                
            po.legal_notice_sent_at = datetime.utcnow()
            await db.commit()
            
            await log_audit(
                db=db,
                user=current_user,
                action="PO_LEGAL_NOTICE_SENT",
                entity_obj=po,
                reason=f"To: {v_email}"
            )
        else:
            await EmailService().send_email(v_email, subject, body)
            await log_audit(
                db=db,
                user=current_user,
                action="PO_REMINDER_SENT",
                entity_obj=po,
                reason=f"To: {v_email}"
            )
            
        # Optional: emit notification record
        try:
            from app.services.notification_service import NotificationService
            if current_user.email:
                await NotificationService.send(
                    db, current_user.email,
                    title="Vendor Reminder Sent",
                    message=f"Manual reminder sent to vendor for PO {po.po_number}",
                    ntype="PO_VENDOR_REMINDER",
                    action_url="/purchase-orders",
                    related_po_id=po.id,
                    send_email=False,
                )
        except Exception as e:
            logger.warning(f"[PO] Failed to record 'reminder sent' notification for PO {po.po_number}: {e}")
            
        return ResponseFormatter.create_success(message="Reminder sent successfully")
    except Exception as e:
        logger.error(f"Failed to send reminder: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to send reminder email: {str(e)}")


@po_router.post("/{po_id}/send-to-legal")
@po_router.post("/{po_id}/send-to-legal-support")
async def send_to_legal_support(
    po_id: str, 
    request: Request, 
    db: Annotated[AsyncSession, Depends(get_db)], 
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Send legal support request for a PO with reason and evidence"""
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    from sqlalchemy import text, select 

    # 1. Get the PO
    po = (await db.execute( 
        select(PurchaseOrder).where(PurchaseOrder.id == po_id) 
    )).scalar_one_or_none() 
    
    if not po: 
        raise HTTPException(404, "PO not found")
    
    # Get body data (to handle both form and JSON)
    body = {}
    reason = ''
    evidence_url = None
    evidence_filename = None
    
    try:
        body = await request.json()
        reason = body.get('reason', '')
        evidence_url = body.get('evidence_url')
        evidence_filename = body.get('evidence_filename')
    except Exception:
        # If not JSON, check form data
        try:
            form_data = await request.form()
            reason = form_data.get('reason', '')
            if 'file' in form_data:
                file = form_data['file']
                if file and isinstance(file, UploadFile):
                    try:
                        from app.utils.uploads import get_upload_subdir
                        upload_dir = get_upload_subdir("legal_evidence")
                        file_ext = file.filename.split(".")[-1] if file.filename else 'pdf'
                        file_id = str(uuid.uuid4())
                        file_path = upload_dir / f"{file_id}.{file_ext}"
                        
                        with open(file_path, "wb") as buffer:
                            shutil.copyfileobj(file.file, buffer)
                            
                        evidence_url = f"{settings.BASE_URL}/uploads/legal_evidence/{file_id}.{file_ext}"
                        evidence_filename = file.filename
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=f"Failed to upload evidence: {str(e)}")
        except HTTPException:
            # Let real failures (e.g. evidence upload above) propagate as a
            # proper error response instead of being swallowed below.
            raise
        except Exception as e:
            logger.warning(f"[PO] Failed to parse form data for legal support request on PO {po_id}: {e}")
    
    # 2. Save legal support request to DB
    await db.execute(text(""" 
        UPDATE purchase_orders 
        SET legal_support_requested_at = NOW(),
            legal_support_reason = :reason,
            legal_support_evidence_url = :evidence_url,
            legal_support_evidence_filename = :evidence_filename,
            legal_support_requested_by = :email
        WHERE id = :po_id 
    """), {"po_id": po_id, "reason": reason, "evidence_url": evidence_url, "evidence_filename": evidence_filename, "email": current_user.email}) 

    # Insert into legal_notice_requests
    await db.execute(text("""
        INSERT INTO legal_notice_requests (po_id, po_number, vendor, vendor_email, amount, requested_by_email, handler_role, status, created_at, updated_at)
        VALUES (:po_id, :po_number, :vendor, :vendor_email, :amount, :email, :handler_role, 'PENDING', NOW(), NOW())
    """), {
        "po_id": po_id, "po_number": po.po_number, "vendor": po.vendor, 
        "vendor_email": po.vendor_email, "amount": po.amount, 
        "email": current_user.email, "handler_role": 'OPERATIONS'
    })

    await db.commit() 
    print(f"[LEGAL] ✅ Legal support saved for PO {po.po_number}")
    
    # 3. Check if Legal role is enabled
    legal_enabled = False 
    try: 
        result = await db.execute( 
            text("SELECT value FROM system_settings WHERE key = 'legal_role_enabled'") 
        ) 
        row = result.fetchone() 
        legal_enabled = row[0] == 'true' if row else False 
    except Exception: 
        legal_enabled = False 
    
    notify_role = 'LEGAL' if legal_enabled else 'OPERATIONS' 
    print(f"[LEGAL] Legal enabled={legal_enabled}, notifying {notify_role}") 
    
    # Integration with NEW WORKFLOW SYSTEM
    try:
        from app.services.workflow_service import WorkflowService
        await WorkflowService.process_legal_notice_workflow(
            db=db,
            admin_email=current_user.email,
            po_id=po.id,
            po_number=po.po_number,
            vendor=po.vendor,
            reason=reason,
            evidence_url=evidence_url,
            evidence_filename=evidence_filename
        )
    except Exception as workflow_err:
        logger.error(f"Failed to trigger legal workflow: {workflow_err}")
    
    # 4. Send INSTANT notification to correct team
    try:
        await NotificationService.send_to_role(
            db, notify_role,
            title=f"Legal Support Requested - {po.po_number}",
            message=f"User {current_user.email} has requested legal support.\n\nPO: {po.po_number}\nVendor: {po.vendor}\nAmount: ₹{po.amount}\n\nPlease review and process this request.",
            ntype="LEGAL",
            action_url=f"http://localhost:3001/dashboard/{'legal' if legal_enabled else 'admin'}"
        )
        print(f"[LEGAL] Notification sent to {notify_role}")
    except Exception as e:
        print(f"[LEGAL] Notification failed: {e}")
    
    # 5. Confirm to user
    try:
        await NotificationService.send(
            db, current_user.email,
            title=f"Legal Support Requested - {po.po_number}",
            message=f"Your legal support request for PO {po.po_number} has been submitted. The team will review and contact you shortly.",
            ntype="SUCCESS"
        )
    except Exception as e:
        print(f"[LEGAL] User notification failed: {e}")
    
    # Audit log
    await log_audit(
        db=db,
        user=current_user,
        action="LEGAL_SUPPORT_REQUEST",
        entity_obj=po,
        reason=reason
    )
    
    return {
        "success": True,
        "message": f"Legal support requested for PO {po.po_number}. Team has been notified.",
        "data": {
            "evidence_url": evidence_url,
            "evidence_filename": evidence_filename
        }
    }


@po_router.post("/{po_id}/send-legal-notice")
async def send_legal_notice(po_id: str, request: Request, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    body = await request.json()
    include_legal = body.get("include_legal_notice", False)
    custom_text = body.get("legal_notice_content", None)

    # Fetch PO from DB
    stmt = select(PurchaseOrder).where((PurchaseOrder.id == po_id) & (PurchaseOrder.user_id == current_user.id))
    result = await db.execute(stmt)
    po = result.scalars().first()
    if not po:
        raise HTTPException(status_code=404, detail=PO_NOT_FOUND_ERROR)

    if not po.vendor_email:
        raise HTTPException(status_code=400, detail="Vendor email is required to send legal notice")

    # Clean email body - NO legal notice text here
    email_body = f"""Dear {po.vendor},

This is a reminder that PO {po.po_number} for the amount of Rs.{po.amount} is due on {po.due_date}.

Please ensure payment is processed on time.

Regards,
Team CreditWatch"""

    if include_legal:
        print(f"[DEBUG] include_legal_notice: {include_legal}")
        print(f"[DEBUG] vendor_email: {po.vendor_email}")
        # Generate PDF
        from app.utils.uploads import get_upload_subdir
        pdf_path = str(get_upload_subdir("temp") / f"legal_notice_{po_id}.pdf")
        print(f"[DEBUG] Generating PDF at: {pdf_path}")
        po_data = {
            "vendor": po.vendor,
            "po_number": po.po_number,
            "amount": po.amount,
            "due_date": str(po.due_date),
            "company_name": current_user.company_name or "Company"
        }
        generate_legal_notice_pdf(po_data, pdf_path, custom_text)
        print(f"[DEBUG] PDF generated. File exists: {os.path.exists(pdf_path)}")

        # Send with PDF attachment
        await send_email_with_attachment(
            to_email=po.vendor_email,
            subject=f"Payment Reminder - PO {po.po_number}",
            body=email_body,
            attachment_path=pdf_path,
            attachment_name=f"Legal_Notice_{po.po_number}.pdf"
        )
        print(f"[DEBUG] Email sent with attachment")

        # Delete temp PDF
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        # Update DB
        po.legal_notice_sent_at = datetime.now(timezone.utc)
        await log_audit(
            db=db,
            user=current_user,
            action="LEGAL_NOTICE_SENT",
            entity_obj=po,
            reason="Legal notice sent via email"
        )
        await db.commit()

        return {"message": f"Email with legal notice PDF sent to {po.vendor_email}"}
    else:
        # Send normal reminder without attachment
        await EmailService().send_email(po.vendor_email, f"Payment Reminder - PO {po.po_number}", email_body)
        return {"message": f"Reminder sent to {po.vendor_email}"}


@pos_router.post("/{po_id}/request-approval") 
async def request_po_edit_approval_pos( 
    po_id: str, 
    request: Request, 
    db: Annotated[AsyncSession, Depends(get_db)], 
    current_user: Annotated[User, Depends(get_current_user)] 
): 
    if not await AccessControlService.can_access_feature(current_user.id, PO_MANAGEMENT, db):
        raise UnauthorizedFeature(PO_FEATURE_NAME)
    body = await request.json() 
    from sqlalchemy import select 
    po = (await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id))).scalar_one_or_none() 
    if not po: 
        raise HTTPException(404, "PO not found") 
    
    from app.services.workflow_service import WorkflowService 
    req_id = await WorkflowService.start_po_approval( 
        db=db, 
        po_id=po_id, 
        po_number=po.po_number, 
        requester_email=current_user.email, 
        edit_data=body.get('edit_data', {}), 
        evidence_url=body.get('evidence_url'), 
        evidence_filename=body.get('evidence_filename'), 
        reason=body.get('reason', 'PO Edit') 
    ) 
    return {"success": True, "message": "Edit submitted for approval. Financial team notified.", "data": {"request_id": req_id}}


