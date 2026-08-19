import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.dependencies import get_current_user
from app.services.workflow_service import WorkflowService
from app.services.notification_service import NotificationService

router = APIRouter()

async def get_role_setting(db, key: str) -> bool:
    try:
        from sqlalchemy import text
        result = await db.execute(text("SELECT value FROM system_settings WHERE key = :key"), {"key": key})
        row = result.fetchone()
        return str(row[0] if row else 'false').lower() == 'true'
    except Exception as e:
        print(f"[SETTINGS] Error: {e}")
        return False


@router.get("/my-tasks")
async def get_my_tasks(db=Depends(get_db), current_user=Depends(get_current_user)):
    from sqlalchemy import text
    role_str = str(current_user.role or '').upper().strip()
    role = role_str.split('.')[-1] if '.' in role_str else role_str
    financial_enabled = await get_role_setting(db, 'financial_role_enabled')
    legal_enabled = await get_role_setting(db, 'legal_role_enabled')
    print(f"[MY-TASKS] Role={role} Fin={financial_enabled} Legal={legal_enabled}")

    if role in ['FINANCIAL', 'FINANCE']:
        if not financial_enabled:
            return {"success": True, "data": {"role": role, "role_disabled": True, "role_disabled_title": "Financial Role is Disabled", "role_disabled_message": "Master Admin has disabled the Financial role. Operations team is handling all subscription tasks."}}
        try:
            result = await db.execute(text("""
                SELECT wi.id as workflow_id, sr.id as request_id, sr.company_name, sr.plan_name,
                    CAST(sr.amount AS TEXT) as amount, sr.user_email, CAST(sr.created_at AS TEXT) as created_at,
                    wi.status
                FROM workflow_items wi
                JOIN subscription_requests sr ON wi.entity_id = sr.id
                WHERE wi.type = 'SUBSCRIPTION' AND UPPER(wi.status) = 'PENDING_FINANCIAL'
                ORDER BY sr.created_at DESC
            """))
            subs = [dict(r) for r in result.mappings().all()]
        except Exception as e:
            await db.rollback()  # prevent this failure from poisoning later queries in this same request
            print(f"[MY-TASKS] Financial error: {e}")
            subs = []
        return {"success": True, "data": {"role": role, "role_disabled": False, "pending_subscriptions": subs}}

    if role == 'LEGAL':
        if not legal_enabled:
            return {"success": True, "data": {"role": role, "role_disabled": True, "role_disabled_title": "Legal Role is Disabled", "role_disabled_message": "Master Admin has disabled the Legal role. Operations team is handling all legal tasks."}}
        try:
            result = await db.execute(text("""
                SELECT wi.id as workflow_id, CAST(lnr.id AS TEXT) as id, lnr.po_id, lnr.po_number, lnr.vendor, CAST(lnr.amount AS TEXT) as amount,
                    lnr.vendor_email, lnr.requested_by_email, CAST(lnr.created_at AS TEXT) as created_at,
                    po.legal_support_reason, po.legal_support_evidence_url, po.legal_support_evidence_filename,
                    CAST(po.legal_support_requested_at AS TEXT) as legal_support_requested_at, po.due_date, wi.status
                FROM workflow_items wi
                LEFT JOIN legal_notice_requests lnr ON wi.entity_id = lnr.po_id
                LEFT JOIN purchase_orders po ON po.id = wi.entity_id
                WHERE wi.type='LEGAL_NOTICE' AND UPPER(wi.status) = 'PENDING_LEGAL'
                ORDER BY wi.created_at DESC LIMIT 100
            """))
            legal_reqs = [dict(r) for r in result.mappings().all()]
        except Exception as e:
            await db.rollback()  # prevent this failure from poisoning later queries in this same request
            print(f"[MY-TASKS] Legal error: {e}")
            legal_reqs = []
        return {"success": True, "data": {"role": role, "role_disabled": False, "legal_support_requests": legal_reqs}}

    if role in ['OPERATIONS', 'OPERATION']:
        data = {"role": role, "handling_financial": not financial_enabled, "handling_legal": not legal_enabled}
        if not financial_enabled:
            try:
                r = await db.execute(text("""
                    SELECT wi.id as workflow_id, sr.id as request_id, sr.company_name, sr.plan_name,
                        CAST(sr.amount AS TEXT) as amount, sr.user_email, CAST(sr.created_at AS TEXT) as created_at,
                        wi.status
                    FROM workflow_items wi
                    JOIN subscription_requests sr ON wi.entity_id = sr.id
                    WHERE wi.type = 'SUBSCRIPTION' AND UPPER(wi.status) = 'PENDING_OPERATION'
                    ORDER BY sr.created_at DESC
                """))
                data['pending_subscriptions'] = [dict(x) for x in r.mappings().all()]
            except Exception as e:
                await db.rollback()  # prevent this failure from poisoning later queries in this same request
                print(f"[MY-TASKS] Ops subs error: {e}")
                data['pending_subscriptions'] = []
        try:
            r = await db.execute(text("""
                SELECT wi.id as workflow_id, COALESCE(wi.title,'PO Edit') as title, wi.status,
                    CAST(wi.created_at AS TEXT) as created_at, COALESCE(par.po_number,'') as po_number,
                    COALESCE(par.evidence_url,'') as evidence_url, COALESCE(par.evidence_filename,'') as evidence_filename,
                    COALESCE(par.requested_by_email,'') as requested_by_email, COALESCE(par.reason,'') as reason
                FROM workflow_items wi LEFT JOIN po_approval_requests par ON par.id = wi.entity_id
                WHERE wi.type='PO_APPROVAL' AND UPPER(wi.status) NOT IN ('MASTER_APPROVED','REJECTED','COMPLETED','OPERATIONS_APPROVED')
                ORDER BY wi.created_at DESC
            """))
            data['po_edit_verification'] = [dict(x) for x in r.mappings().all()]
        except Exception as e:
            await db.rollback()  # prevent this failure from poisoning later queries in this same request
            print(f"[MY-TASKS] po_edit_verification error: {e}")
            data['po_edit_verification'] = []
        try:
            r = await db.execute(text("""
                SELECT CAST(id AS TEXT) as id, company_name, gstin, reason, additional_info,
                    user_email as requested_by_email, status, CAST(created_at AS TEXT) as created_at
                FROM business_check_requests
                WHERE UPPER(status) IN ('PENDING_OPERATION', 'PENDING_OPERATIONS')
                ORDER BY created_at DESC
            """))
            data['business_check_requests'] = [dict(x) for x in r.mappings().all()]
        except Exception as e:
            await db.rollback()  # prevent this failure from poisoning later queries in this same request
            print(f"[MY-TASKS] Business check requests error: {e}")
            data['business_check_requests'] = []
        try:
            r = await db.execute(text("""
                SELECT CAST(id AS TEXT) as id, COALESCE(request_type,'Support Request') as title,
                    COALESCE(request_details,'') as description, status,
                    COALESCE(user_email,'') as requested_by_email,
                    CAST(created_at AS TEXT) as created_at
                FROM support_requests WHERE UPPER(status) IN ('PENDING','OPEN','NEW','IN_PROGRESS')
                ORDER BY created_at DESC LIMIT 50
            """))
            data['support_requests'] = [dict(x) for x in r.mappings().all()]
        except Exception as e:
            await db.rollback()  # prevent this failure from poisoning later queries in this same request
            print(f"[MY-TASKS] support requests error: {e}")
            data['support_requests'] = []
        if not legal_enabled:
            try:
                r = await db.execute(text("""
                    SELECT wi.id as workflow_id, CAST(lnr.id AS TEXT) as id, lnr.po_id, lnr.po_number, lnr.vendor,
                        CAST(lnr.amount AS TEXT) as amount, lnr.vendor_email, lnr.requested_by_email,
                        CAST(wi.created_at AS TEXT) as created_at, wi.status
                    FROM workflow_items wi
                    LEFT JOIN legal_notice_requests lnr ON wi.entity_id = lnr.po_id
                    WHERE wi.type='LEGAL_NOTICE' AND UPPER(wi.status) = 'PENDING_LEGAL'
                    ORDER BY wi.created_at DESC LIMIT 50
                """))
                data['legal_notice_requests'] = [dict(x) for x in r.mappings().all()]
            except Exception as e:
                await db.rollback()  # prevent this failure from poisoning later queries in this same request
                data['legal_notice_requests'] = []
        return {"success": True, "data": data}

    if role == 'MASTER_ADMIN':
        data = {"role": role, "financial_enabled": financial_enabled, "legal_enabled": legal_enabled}
        try:
            r = await db.execute(text("""
                SELECT COALESCE(wi.id, CAST(sr.id AS TEXT)) as workflow_id, sr.company_name, sr.plan_name,
                    CAST(sr.amount AS TEXT) as amount, sr.user_email, CAST(sr.created_at AS TEXT) as created_at,
                    COALESCE(wi.status,'PENDING') as status,
                    COALESCE(wi.reviewed_by_email,'') as reviewed_by_email,
                    COALESCE(wi.review_notes,'') as review_notes
                FROM subscription_requests sr
                LEFT JOIN workflow_items wi ON wi.entity_id=sr.id AND wi.type='SUBSCRIPTION'
                WHERE UPPER(COALESCE(wi.status,'')) IN ('OPERATIONS_APPROVED','FINANCIAL_APPROVED')
                ORDER BY sr.created_at DESC
            """))
            data['pending_subscriptions'] = [dict(x) for x in r.mappings().all()]
        except Exception as e:
            await db.rollback()  # prevent this failure from poisoning later queries in this same request
            data['pending_subscriptions'] = []
        try:
            r = await db.execute(text("""
                SELECT wi.id as workflow_id, COALESCE(wi.title,'') as title, wi.status,
                    CAST(wi.created_at AS TEXT) as created_at,
                    COALESCE(wi.reviewed_by_email,'') as reviewed_by_email,
                    COALESCE(wi.review_notes,'') as review_notes,
                    COALESCE(par.po_number,'') as po_number, COALESCE(par.evidence_url,'') as evidence_url,
                    COALESCE(par.requested_by_email,'') as requested_by_email, COALESCE(par.reason,'') as reason
                FROM workflow_items wi LEFT JOIN po_approval_requests par ON par.id=wi.entity_id
                WHERE wi.type='PO_APPROVAL' AND UPPER(wi.status) IN ('OPERATIONS_APPROVED','FINANCIAL_APPROVED','LEGAL_APPROVED')
                ORDER BY wi.created_at DESC
            """))
            data['pending_po_approvals'] = [dict(x) for x in r.mappings().all()]
        except Exception as e:
            await db.rollback()  # prevent this failure from poisoning later queries in this same request
            data['pending_po_approvals'] = []
        try:
            r = await db.execute(text("""
                SELECT CAST(id AS TEXT) as id, company_name, gstin, verdict,
                    report_text, report_url, ops_reviewed_by, user_email as requested_by_email,
                    CAST(created_at AS TEXT) as created_at,
                    (CASE WHEN NOT EXISTS (
                        SELECT 1 FROM global_credibility_index
                        WHERE company_registration_no = gstin OR company_name = company_name
                    ) THEN true ELSE false END) as is_new_company
                FROM business_check_requests
                WHERE UPPER(status) IN ('PENDING_MASTER_ADMIN', 'PENDING_MASTER')
                ORDER BY created_at DESC
            """))
            data['pending_business_requests'] = [dict(x) for x in r.mappings().all()]
        except Exception as e:
            await db.rollback()  # prevent this failure from poisoning later queries in this same request
            print(f"[MY-TASKS] Master business requests error: {e}")
            import traceback
            traceback.print_exc()
            data['pending_business_requests'] = []
        try:
            r = await db.execute(text("""
                SELECT wi.id as workflow_id, CAST(lnr.id AS TEXT) as id, CAST(lnr.po_id AS TEXT) as po_id, lnr.po_number, lnr.vendor,
                    CAST(lnr.amount AS TEXT) as amount, lnr.vendor_email, lnr.requested_by_email,
                    lnr.ops_notes, lnr.ops_processed_by, CAST(wi.created_at AS TEXT) as created_at,
                    po.legal_support_reason, po.legal_support_evidence_url, po.legal_support_evidence_filename, wi.status
                FROM workflow_items wi
                LEFT JOIN legal_notice_requests lnr ON wi.entity_id = lnr.po_id
                LEFT JOIN purchase_orders po ON po.id = wi.entity_id
                WHERE wi.type='LEGAL_NOTICE' AND UPPER(wi.status) IN ('OPERATIONS_APPROVED', 'LEGAL_REVIEWED')
                ORDER BY wi.created_at DESC
            """))
            data['pending_legal_notices'] = [dict(x) for x in r.mappings().all()]
        except Exception as e:
            await db.rollback()  # prevent this failure from poisoning later queries in this same request
            print(f"[MY-TASKS] Master legal notices error: {e}")
            import traceback
            traceback.print_exc()
            data['pending_legal_notices'] = []
        data['summary'] = {
            'pending_subscriptions': len(data['pending_subscriptions']),
            'pending_po_approvals': len(data['pending_po_approvals']),
            'pending_business': len(data['pending_business_requests']),
            'pending_legal': len(data['pending_legal_notices']),
            'total': len(data['pending_subscriptions']) + len(data['pending_po_approvals']) + len(data['pending_business_requests']) + len(data['pending_legal_notices'])
        }
        return {"success": True, "data": data}

    return {"success": True, "data": {"role": role, "message": "Unknown role"}}


# ─── SUBSCRIPTION ACTIONS ───
@router.post("/subscription/{wf_id}/operations-approve")
async def ops_approve_sub(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    financial_enabled = await is_financial_enabled(db)
    allowed_roles = ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']
    if financial_enabled:
        allowed_roles.extend(['FINANCIAL', 'FINANCE'])
    if role not in allowed_roles:
        raise HTTPException(403, f"Not authorized (you are {role})")
    body = await request.json()
    await WorkflowService.financial_verify_subscription(
        db, wf_id, user.email, body.get('notes', 'Reviewed by Operations team'))
    return {"success": True, "message": "Verified! Sent to Master Admin for final activation."}


@router.post("/subscription/{wf_id}/financial-verify")
async def fin_verify_sub_compat(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    financial_enabled = await is_financial_enabled(db)

    allowed_roles = ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']
    if financial_enabled:
        allowed_roles.append('FINANCIAL')

    if role not in allowed_roles:
        raise HTTPException(403, f"Operations team only (you are {role})")
    body = await request.json()
    await WorkflowService.financial_verify_subscription(
        db, wf_id, user.email, body.get('notes', 'Reviewed by Operations team'))
    return {"success": True, "message": "Verified! Sent to Master Admin for final activation."}


@router.post("/subscription/{wf_id}/master-approve")
async def master_approve_sub(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    if role != 'MASTER_ADMIN':
        raise HTTPException(403, "Master Admin only")
    body = await request.json()
    await WorkflowService.master_approve_subscription(
        db, wf_id, user.email, body.get('notes', 'Approved'))
    return {"success": True, "message": "Subscription activated! User has been notified."}


@router.post("/subscription/{wf_id}/reject")
async def reject_sub(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    financial_enabled = await is_financial_enabled(db)
    allowed_roles = ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']
    if financial_enabled:
        allowed_roles.extend(['FINANCIAL', 'FINANCE'])
    if role not in allowed_roles:
        raise HTTPException(403)
    body = await request.json()
    await WorkflowService.reject_subscription(
        db, wf_id, user.email, body.get('reason', 'Not approved'))
    return {"success": True, "message": "Subscription rejected. User has been notified."}


# ─── PO APPROVAL ACTIONS ───
@router.post("/po/{wf_id}/operations-verify")
async def ops_verify_po(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    if role not in ['MASTER_ADMIN', 'OPERATION', 'OPERATIONS']:
        raise HTTPException(403, "Operations team only")
    body = await request.json()
    await WorkflowService.operations_verify_po(
        db, wf_id, user.email, body.get('notes', 'Truth verified by Operations team'))
    return {"success": True, "message": "Verified! Sent for next step."}


@router.post("/po/{wf_id}/legal-verify")
async def legal_verify_po_compat(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    legal_enabled = await is_legal_enabled(db)

    allowed_roles = ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']
    if legal_enabled:
        allowed_roles.append('LEGAL')

    if role not in allowed_roles:
        raise HTTPException(403, "Operations team only")
    body = await request.json()
    await WorkflowService.legal_verify_po(
        db, wf_id, user.email, body.get('notes', 'Compliance verified by Operations team'))
    return {"success": True, "message": "Verified! Sent to master admin for review."}


@router.post("/po/{wf_id}/financial-verify")
async def fin_verify_po_compat(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    financial_enabled = await is_financial_enabled(db)

    allowed_roles = ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']
    if financial_enabled:
        allowed_roles.append('FINANCIAL')

    if role not in allowed_roles:
        raise HTTPException(403, "Operations team only")
    body = await request.json()
    await WorkflowService.financial_verify_po(
        db, wf_id, user.email, body.get('notes', 'Financial review completed'))
    return {"success": True, "message": "Verified! Sent to Master Admin for final apply."}


@router.post("/po/{wf_id}/operations-approve")
async def ops_approve_po(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    if role not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']:
        raise HTTPException(403, "Operations team only")
    body = await request.json()
    await WorkflowService.financial_verify_po(
        db, wf_id, user.email, body.get('notes', 'Reviewed by Operations team'))
    return {"success": True, "message": "Sent to Master Admin for final approval."}


@router.post("/po/{wf_id}/master-approve")
async def master_approve_po(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    if role != 'MASTER_ADMIN':
        raise HTTPException(403, "Master Admin only")
    body = await request.json()
    try:
        await WorkflowService.master_approve_po(
            db, wf_id, user.email, body.get('notes', 'Final approval by Master Admin'))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Error in master_approve_po: {str(e)}")
    return {"success": True, "message": "PO edit approved and changes applied."}


@router.post("/po/{wf_id}/reject")
async def reject_po(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    if role not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']:
        raise HTTPException(403)
    body = await request.json()
    await WorkflowService.reject_workflow(
        db, wf_id, user.email, body.get('reason', 'Rejected'))
    return {"success": True, "message": "PO edit rejected. Requester notified."}


# ─── LEGAL NOTICE ACTIONS ───
@router.post("/legal-notice/{wf_id}/process")
async def process_legal_notice(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    legal_enabled = await is_legal_enabled(db)
    allowed_roles = ['MASTER_ADMIN']
    if legal_enabled:
        allowed_roles.append('LEGAL')
    else:
        allowed_roles.extend(['OPERATIONS', 'OPERATION'])
    if role not in allowed_roles:
        raise HTTPException(403, f"Not authorized (you are {role})")
    try:
        body = await request.json()
        notes = body.get('notes', 'Processed by team')
    except Exception:
        notes = 'Processed by team'
    
    if role in ['OPERATIONS', 'OPERATION']:
        await WorkflowService.ops_process_legal_notice(db, wf_id, user.email, notes)
    elif role == 'LEGAL':
        await WorkflowService.legal_review_complete(db, wf_id, user.email, notes)
    
    return {"success": True, "message": "Legal notice processed! Sent to Master Admin for final approval."}

@router.post("/legal/ops-process/{legal_request_id}")
@router.post("/ops-process-legal/{legal_request_id}")
async def ops_process_legal_notice(legal_request_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    if role not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']:
        raise HTTPException(403, "Operations team or Master Admin only")
    
    req_res = await db.execute(text("SELECT * FROM legal_notice_requests WHERE id=:id"), {"id": legal_request_id})
    req = req_res.mappings().first()
    if not req:
        raise HTTPException(404, "Legal notice request not found")
    if req['status'] != 'PENDING':
        raise HTTPException(400, f"Invalid status: {req['status']}")

    try:
        body = await request.json()
        notes = body.get('notes', 'Processed by Operations team')
    except Exception:
        notes = 'Processed by Operations team'

    await db.execute(text("""
        UPDATE legal_notice_requests
        SET status='OPS_APPROVED', ops_notes=:notes, ops_processed_by=:email, ops_processed_at=NOW(), updated_at=NOW()
        WHERE id=:id
    """), {"id": legal_request_id, "notes": notes, "email": user.email})
    await db.commit()
    return {"success": True, "message": "Legal notice processed! Sent to Master Admin for final approval."}


@router.post("/legal/master-approve/{legal_request_id}")
@router.post("/master-approve-legal/{legal_request_id}")
async def master_approve_legal_notice(legal_request_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    import traceback
    try:
        print("[DEBUG] master-approve-legal called with id:", legal_request_id)
        if user.role != 'MASTER_ADMIN' and (hasattr(user.role, 'value') and user.role.value != 'MASTER_ADMIN'):
            raise HTTPException(403, "Master Admin only")
        
        req_res = await db.execute(text("SELECT * FROM legal_notice_requests WHERE id=:id"), {"id": legal_request_id})
        req = req_res.mappings().first()
        if not req:
            raise HTTPException(404, "Legal notice request not found")
        if req['status'] != 'OPS_APPROVED':
            raise HTTPException(400, f"Invalid status: {req['status']}")

        try:
            body = await request.json()
            notes = body.get('notes', 'Approved by Master Admin')
        except Exception:
            notes = 'Approved by Master Admin'

        print("[DEBUG] Got legal notice request:", req)

        # 1. Fetch PO and company info
        po_res = await db.execute(text("SELECT * FROM purchase_orders WHERE id=:id"), {"id": req['po_id']}) 
        po = po_res.mappings().first() 
        if not po:
            raise HTTPException(404, "Purchase order not found")
        
        print("[DEBUG] Got PO:", po)
        
        owner_res = await db.execute(text("SELECT company_name FROM companies WHERE id=:cid"), {"cid": po['company_id']}) 
        owner = owner_res.mappings().first()
        
        print("[DEBUG] Got owner:", owner)
        
        # 2. Update tables FIRST (so even if PDF/email fails, status is updated)
        # Update legal notice request
        await db.execute(text("""
            UPDATE legal_notice_requests
            SET status='MASTER_APPROVED', master_notes=:notes, master_approved_by=:email, master_approved_at=NOW(), updated_at=NOW()
            WHERE id=:id
        """), {"id": legal_request_id, "notes": notes, "email": user.email})

        # Update purchase order
        await db.execute(text("""
            UPDATE purchase_orders
            SET legal_support_status='NOTICE_SENT', legal_notice_sent_at=NOW(), legal_notice_status='SENT'
            WHERE id=:po_id
        """), {"po_id": req['po_id']})

        # Update workflow item if exists
        await db.execute(text("""
            UPDATE workflow_items 
            SET status='APPROVED', approved_by_email=:email, approval_notes=:notes, approved_at=NOW(), current_handler_role='COMPLETED', updated_at=NOW()
            WHERE entity_id=:po_id AND type='LEGAL_NOTICE'
        """), {"po_id": req['po_id'], "email": user.email, "notes": notes})

        await db.commit()
        
        print("[DEBUG] Tables updated, committing")

        # 3. Generate and send legal notice (continue even if this fails)
        try:
            from app.services.legal_notice_service import generate_legal_notice_pdf 
            from app.services.email_service import send_email_with_attachment 
            import uuid
            from app.utils.uploads import get_upload_subdir

            temp_dir = get_upload_subdir("temp")
            pdf_path = str(temp_dir / f"Notice_{po['po_number']}_{uuid.uuid4().hex[:8]}.pdf")

            po_data = { 
                "vendor": po['vendor'], 
                "po_number": po['po_number'], 
                "amount": po['amount'], 
                "due_date": str(po['due_date']), 
                "company_name": owner['company_name'] if owner else "CreditDataWatch Client" 
            }
            
            print("[DEBUG] Generating PDF with data:", po_data)
            generate_legal_notice_pdf(po_data, pdf_path)
            print("[DEBUG] PDF generated at:", pdf_path)
            
            if po['vendor_email']: 
                print("[DEBUG] Sending email to:", po['vendor_email'])
                await send_email_with_attachment( 
                    to_email=po['vendor_email'], 
                    subject=f"LEGAL NOTICE: Outstanding Payment for PO {po['po_number']}", 
                    body=f"Please find the attached legal notice regarding outstanding payment for PO {po['po_number']}.", 
                    attachment_path=pdf_path, 
                    attachment_name=f"Legal_Notice_{po['po_number']}.pdf" 
                )
                print("[DEBUG] Email sent")
            
            if os.path.exists(pdf_path): 
                os.remove(pdf_path)
                print("[DEBUG] PDF deleted")
        except Exception as e:
            print(f"[ERROR] PDF/email generation failed: {str(e)}")
            traceback.print_exc()
        
        # 4. Send notification to requester (continue even if this fails)
        try:
            from app.services.notification_service import NotificationService
            await NotificationService.send( 
                db, req['requested_by_email'], 
                title="Legal Notice Approved", 
                message=f"Your legal notice request for PO {po['po_number']} has been approved and sent to the vendor.", 
                ntype="SUCCESS" 
            )
            print("[DEBUG] Notification sent to requester")
        except Exception as e:
            print(f"[ERROR] Notification failed: {str(e)}")
            traceback.print_exc()

        return {"success": True, "message": "Legal notice approved! Sent to vendor."}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] master-approve-legal failed: {str(e)}")
        traceback.print_exc()
        raise HTTPException(500, f"Internal server error: {str(e)}")


@router.post("/legal/reject/{legal_request_id}")
@router.post("/reject-legal/{legal_request_id}")
async def reject_legal_notice(legal_request_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    req_res = await db.execute(text("SELECT * FROM legal_notice_requests WHERE id=:id"), {"id": legal_request_id})
    req = req_res.mappings().first()
    if not req:
        raise HTTPException(404, "Legal notice request not found")

    try:
        body = await request.json()
        reason = body.get('reason', 'Rejected')
    except Exception:
        reason = 'Rejected'

    await db.execute(text("""
        UPDATE legal_notice_requests
        SET status='REJECTED', master_notes=:reason, updated_at=NOW()
        WHERE id=:id
    """), {"id": legal_request_id, "reason": reason})

    # Update purchase order
    await db.execute(text("""
        UPDATE purchase_orders
        SET legal_support_status='REJECTED'
        WHERE id=:po_id
    """), {"po_id": req['po_id']})

    # Update workflow item
    await db.execute(text("""
        UPDATE workflow_items 
        SET status='REJECTED', rejected_by_email=:email, rejection_notes=:reason, rejected_at=NOW(), updated_at=NOW()
        WHERE entity_id=:po_id AND type='LEGAL_NOTICE'
    """), {"po_id": req['po_id'], "email": user.email, "reason": reason})

    await db.commit()
    
    # Send notification to requester
    from app.services.notification_service import NotificationService
    await NotificationService.send( 
        db, req['requested_by_email'], 
        title="Legal Notice Rejected", 
        message=f"Your legal notice request for PO {req['po_number']} has been rejected. Reason: {reason}", 
        ntype="ERROR" 
    )

    return {"success": True, "message": "Legal notice request rejected."}


# ─── LEGAL ACTIONS (compat) ───
@router.post("/legal/process-notice/{po_id}")
async def process_legal_notice_compat(po_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    if role not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION', 'LEGAL']:
        raise HTTPException(403, "Operations team, Legal team, or Master Admin only")

    po_res = await db.execute(text("SELECT * FROM purchase_orders WHERE id=:id"), {"id": po_id})
    po = po_res.mappings().first()
    if not po:
        raise HTTPException(404, "Purchase Order not found")

    try:
        body = await request.json()
        notes = body.get('notes', 'Processed by team')
    except Exception:
        notes = 'Processed by team'

    wf_res = await db.execute(text("""
        SELECT id FROM workflow_items WHERE entity_id = :po_id AND type = 'LEGAL_NOTICE'
    """), {"po_id": po_id})
    wf = wf_res.fetchone()

    if not wf:
        await db.execute(text("""
            INSERT INTO workflow_items (
                id, type, status, entity_id, entity_type,
                submitted_by_email, assigned_to_role, current_handler_role,
                title, description, created_at, updated_at
            ) VALUES (
                :id, 'LEGAL_NOTICE', 'PENDING_LEGAL', :po_id, 'PURCHASE_ORDER',
                :email, 'LEGAL', 'LEGAL',
                :title, :description, NOW(), NOW()
            )
        """), {
            "id": str(uuid.uuid4()),
            "po_id": po_id,
            "email": user.email,
            "title": f"Legal Notice Request: {po['po_number']}",
            "description": notes
        })
        await db.commit()
        return {"success": True, "message": "Legal notice request created! Sent to Legal team."}
    else:
        return {"success": True, "message": "Legal notice request already exists."}


# ─── LEGAL NOTICE ACTIONS (compat) ───
@router.post("/legal-notice/{wf_id}/legal-review-complete")
async def legal_review_complete(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    role = str(user.role).split('.')[-1] if '.' in str(user.role) else str(user.role)
    if role not in ['MASTER_ADMIN', 'LEGAL']:
        raise HTTPException(403, "Legal team only")
    body = await request.json()
    await WorkflowService.legal_review_complete(
        db, wf_id, user.email, body.get('notes', 'Legal review completed'))
    return {"success": True, "message": "Legal review completed! Sent to Master Admin for final approval."}


@router.post("/legal-notice/{wf_id}/master-approve")
async def master_approve_legal_notice_final(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    if user.role != 'MASTER_ADMIN':
        raise HTTPException(403, "Master Admin only")
    body = await request.json()
    await WorkflowService.master_approve_legal_notice(
        db, wf_id, user.email, body.get('notes', 'Final approval granted'))
    return {"success": True, "message": "Legal notice approved and sent to vendor!"}


@router.post("/legal-notice/{wf_id}/reject")
async def reject_legal_notice_final(wf_id: str, request: Request,
    db: Annotated[any, Depends(get_db)], user: Annotated[any, Depends(get_current_user)]):
    if user.role != 'MASTER_ADMIN':
        raise HTTPException(403, "Master Admin only")
    body = await request.json()
    await WorkflowService.master_reject_legal_notice(
        db, wf_id, user.email, body.get('reason', 'Rejected'))
    return {"success": True, "message": "Legal notice request rejected."}


# ─── NOTIFICATIONS ───
@router.get("/notifications")
async def get_notifs(db=Depends(get_db), user=Depends(get_current_user)):
    notifs = await NotificationService.get_for_user(db, user.email)
    count = await NotificationService.get_unread_count(db, user.email)
    # Convert datetime objects to strings
    for n in notifs:
        if 'created_at' in n and n['created_at']:
            n['created_at'] = str(n['created_at'])
    return {"success": True, "data": notifs, "unread_count": count}


@router.post("/notifications/{nid}/read")
async def mark_read(nid: str, db=Depends(get_db), user=Depends(get_current_user)):
    await NotificationService.mark_read(db, nid, user.email)
    return {"success": True}


@router.post("/notifications/read-all")
async def mark_all_read(db=Depends(get_db), user=Depends(get_current_user)):
    await NotificationService.mark_all_read(db, user.email)
    return {"success": True}


async def is_financial_enabled(db):
    # Wrapped in a SAVEPOINT so a failure here only rolls back this lookup,
    # not the whole outer transaction (which may hold other uncommitted
    # work earlier in the same request). Without this, any statement run
    # after a failed lookup would fail with "current transaction is
    # aborted, commands ignored until end of transaction block".
    try:
        from sqlalchemy import text
        async with db.begin_nested():
            result = await db.execute(text("SELECT value FROM system_settings WHERE key = 'financial_role_enabled'"))
            row = result.fetchone()
            return str(row[0] if row else 'false').lower() == 'true'
    except Exception as e:
        print(f"[SETTINGS] financial_role_enabled error: {e}")
        return False


async def is_legal_enabled(db):
    try:
        from sqlalchemy import text
        async with db.begin_nested():
            result = await db.execute(text("SELECT value FROM system_settings WHERE key = 'legal_role_enabled'"))
            row = result.fetchone()
            return str(row[0] if row else 'false').lower() == 'true'
    except Exception as e:
        print(f"[SETTINGS] legal_role_enabled error: {e}")
        return False