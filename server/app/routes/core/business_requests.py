"""
Business access request and support request endpoints.
"""
from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text
from datetime import datetime, timezone
from app.database import get_db, engine
from app.models import User, PurchaseOrder, DefaulterCase, CreditReport, Settlement, Company, BusinessRequest, CompanyCredibilityIndex
from app.dependencies import get_current_user, require_role, require_master_admin, is_developer
import os
from app.services.notification_service import NotificationService

from .common import *  # noqa: F401,F403 (logger + shared constants)

business_requests_router = APIRouter()

@business_requests_router.post("/business-requests")
async def create_business_request(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    body = await request.json()
    import uuid as uuid_lib
    from sqlalchemy import text
    
    req_id = str(uuid_lib.uuid4())
    wf_id = str(uuid_lib.uuid4())
    
    await db.execute(text("""
        INSERT INTO business_requests
        (id, user_id, user_email, company_name, gstin, reason, additional_info, status, created_at)
        VALUES (:id, :user_id, :user_email, :company_name, :gstin, :reason, :additional_info, 'PENDING', NOW())
    """), {
        "id": req_id,
        "user_id": str(current_user.id),
        "user_email": current_user.email,
        "company_name": body.get('company_name'),
        "gstin": body.get('gstin'),
        "reason": body.get('reason'),
        "additional_info": body.get('additional_info')
    })
    
    await db.execute(text("""
        INSERT INTO workflow_items
        (id, type, status, title, description, entity_id, entity_type,
         submitted_by_email, assigned_to_role, current_handler_role, created_at)
        VALUES (:id, 'BUSINESS_REQUEST', 'PENDING', :title, :desc,
                :eid, 'business_request', :email, 'OPERATIONS', 'OPERATIONS', NOW())
    """), {
        "id": wf_id,
        "title": f"Business Check Request — {body.get('company_name')}",
        "desc": f"{current_user.email} wants to check {body.get('company_name')} (GSTIN: {body.get('gstin')}). Reason: {body.get('reason', 'Not specified')}",
        "eid": req_id,
        "email": current_user.email
    })
    
    await db.commit()
    
    from app.services.notification_service import NotificationService
    await NotificationService.send_to_role(
        db, "OPERATIONS",
        title=f"🔍 Business Check Request",
        message=f"{current_user.email} wants to check company: {body.get('company_name')} (GSTIN: {body.get('gstin')})\n\nReason: {body.get('reason', 'Not specified')}\n\nPlease review and generate a report.",
        ntype="BUSINESS_REQUEST",
        action_url="http://localhost:3001/dashboard/admin",
        workflow_id=wf_id
    )
    
    # Notify all Master Admins (not just one arbitrary one — see the same
    # fix applied in WorkflowService.notify_all_master_admins)
    await NotificationService.send_to_role(
        db, "MASTER_ADMIN",
        title=f"📋 New Business Check Request",
        message=f"{current_user.email} submitted a business check request for {body.get('company_name')}",
        ntype="INFO",
        workflow_id=wf_id
    )
    
    await NotificationService.send(
        db, current_user.email,
        title="✅ Business Check Request Submitted",
        message=f"Your request to check {body.get('company_name')} has been submitted. Operations team will review and send you a report soon.",
        ntype="SUCCESS"
    )
    
    return {
        "success": True,
        "message": "Request submitted successfully! You will receive a notification when the report is ready.",
        "data": {"request_id": req_id}
    }


@business_requests_router.get("/business-requests/pending")
async def get_pending_business_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION', 'LEGAL', 'FINANCIAL', 'FINANCE']:
        raise HTTPException(status_code=403, detail="Operations/Legal/Financial team only")
    
    from sqlalchemy import text
    requests_result = await db.execute(text("""
        SELECT 
            br.id, 
            br.company_name, 
            br.gstin, 
            br.status, 
            br.risk_score, 
            br.recommendation, 
            br.legal_notes, 
            br.created_at,
            u.email AS requesting_company_email,
            COALESCE(c.company_name, u.company_name) AS requesting_company_name
        FROM business_requests br
        LEFT JOIN users u ON br.user_id = u.id
        LEFT JOIN companies c ON u.company_id = c.id
        WHERE br.status IN ('PENDING', 'ANALYZING')
        ORDER BY br.created_at DESC
    """))
    rows = requests_result.mappings().all()
    return {
        "success": True,
        "data": [{k: str(v) if v else None for k, v in dict(r).items()} for r in rows]
    }


@business_requests_router.get("/business-requests/my")
async def get_my_business_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    from sqlalchemy import text
    requests_result = await db.execute(text("""
        SELECT 
            br.id, 
            br.company_name, 
            br.gstin, 
            br.reason, 
            br.additional_info, 
            br.status, 
            br.verdict, 
            br.report_text, 
            br.report_url, 
            br.reviewed_by_email, 
            br.reviewed_at, 
            br.created_at,
            u.email AS requesting_company_email,
            COALESCE(c.company_name, u.company_name) AS requesting_company_name
        FROM business_requests br
        LEFT JOIN users u ON br.user_id = u.id
        LEFT JOIN companies c ON u.company_id = c.id
        WHERE br.user_id = :user_id
        ORDER BY br.created_at DESC
    """), {"user_id": current_user.id})
    rows = requests_result.mappings().all()
    return {
        "success": True,
        "data": [{k: str(v) if v else None for k, v in dict(r).items()} for r in rows]
    }


@business_requests_router.post("/business-requests/{request_id}/complete")
async def complete_business_request(
    request_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION', 'LEGAL', 'FINANCIAL', 'FINANCE']:
        raise HTTPException(status_code=403)
    
    from sqlalchemy import text
    body = await request.json()
    verdict = body.get('verdict', 'NEUTRAL')
    report_text = body.get('report', '')
    
    req_row = await db.execute(
        text("SELECT * FROM business_requests WHERE id = :id"),
        {"id": request_id}
    )
    req = req_row.fetchone()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    req_data = dict(req._mapping)
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from datetime import datetime
        import os
        from pathlib import Path
        
        uploads_dir = Path(__file__).parent.parent.parent / "uploads" / "reports"
        os.makedirs(uploads_dir, exist_ok=True)
        pdf_path = str(uploads_dir / f"business_report_{request_id}.pdf")
        
        doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                               rightMargin=inch, leftMargin=inch,
                               topMargin=inch, bottomMargin=inch)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Heading1'],
                                    fontSize=18, spaceAfter=20, alignment=1)
        body_style = ParagraphStyle('Body', parent=styles['Normal'],
                                   fontSize=11, spaceAfter=12, leading=18)
        
        verdict_colors = {
            'SAFE': colors.green,
            'RISKY': colors.red,
            'NEUTRAL': colors.orange
        }
        verdict_icons = {
            'SAFE': '✅ SAFE TO DO BUSINESS',
            'RISKY': '❌ HIGH RISK — CAUTION ADVISED',
            'NEUTRAL': '⚠️ PROCEED WITH CAUTION'
        }
        
        story = [
            Paragraph("CreditDataWatch", title_style),
            Paragraph("Business Verification Report", styles['Heading2']),
            Spacer(1, 0.2 * inch),
            Paragraph(f"Company: {req_data.get('company_name')}", body_style),
            Paragraph(f"GSTIN: {req_data.get('gstin')}", body_style),
            Paragraph(f"Requested by: {req_data.get('requested_by_email')}", body_style),
            Paragraph(f"Report Date: {datetime.now().strftime('%d %B %Y')}", body_style),
            Paragraph(f"Reviewed by: {current_user.email}", body_style),
            Spacer(1, 0.3 * inch),
            Paragraph("VERDICT", styles['Heading2']),
            Paragraph(verdict_icons.get(verdict, verdict), body_style),
            Spacer(1, 0.2 * inch),
            Paragraph("DETAILED ANALYSIS", styles['Heading2']),
            Paragraph(report_text or "No detailed analysis provided.", body_style),
            Spacer(1, 0.3 * inch),
            Paragraph("---", body_style),
            Paragraph("This report was generated by CreditDataWatch Operations Team.",
                     styles['Italic']),
            Paragraph(f"Report ID: {request_id}", styles['Italic']),
        ]
        
        doc.build(story)
        report_url = f"http://localhost:8000/uploads/reports/business_report_{request_id}.pdf"
        print(f"[BUSINESS_REQUEST] PDF generated: {pdf_path}")
        
    except Exception as e:
        print(f"[BUSINESS_REQUEST] PDF generation failed: {e}")
        import traceback
        traceback.print_exc()
        report_url = None
    
    await db.execute(text("""
        UPDATE business_requests SET
            status = 'COMPLETED',
            verdict = :verdict,
            report_text = :report,
            report_url = :url,
            reviewed_by_email = :reviewer,
            reviewed_at = NOW()
        WHERE id = :id
    """), {
        "verdict": verdict,
        "report": report_text,
        "url": report_url,
        "reviewer": current_user.email,
        "id": request_id
    })
    await db.commit()
    
    from app.services.notification_service import NotificationService
    
    verdict_msg = {
        'SAFE': '✅ Good news! The company appears safe to do business with.',
        'RISKY': '⚠️ Caution! The company has some risk factors.',
        'NEUTRAL': '📊 The company has a neutral rating. Proceed with standard caution.'
    }
    
    await NotificationService.send(
        db, req_data['requested_by_email'],
        title=f"📊 Business Report Ready — {req_data.get('company_name')}",
        message=f"{verdict_msg.get(verdict, 'Report is ready.')}\n\n{report_text[:200] if report_text else ''}\n\n{'Download report: ' + report_url if report_url else 'Contact operations team for full report.'}",
        ntype="SUCCESS" if verdict == 'SAFE' else "WARNING",
        action_url=report_url or "http://localhost:3001/dashboard"
    )
    
    return {
        "success": True,
        "message": f"Report completed and sent to {req_data['requested_by_email']}",
        "data": {"report_url": report_url, "verdict": verdict}
    }


@business_requests_router.post("/support-requests")
async def create_support_request(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    body = await request.json()
    import uuid as uuid_lib
    from sqlalchemy import text
    from app.models import Company
    
    # Get user's company name
    company_name = None
    if current_user.company_id:
        company_stmt = select(Company).where(Company.id == current_user.company_id)
        company_res = await db.execute(company_stmt)
        company = company_res.scalars().first()
        if company:
            company_name = company.company_name
    if not company_name:
        company_name = current_user.company_name
    
    req_id = str(uuid_lib.uuid4())
    
    await db.execute(text("""
        INSERT INTO support_requests
        (id, user_id, user_name, user_email, company_name, request_type, request_details, status, created_at)
        VALUES (:id, :user_id, :user_name, :user_email, :company_name, :request_type, :request_details, 'PENDING', NOW())
    """), {
        "id": req_id,
        "user_id": str(current_user.id),
        "user_name": current_user.name or current_user.email.split('@')[0],
        "user_email": current_user.email,
        "company_name": company_name,
        "request_type": body.get('request_type', 'General'),
        "request_details": body.get('request_details', '')
    })
    await db.commit()
    
    from app.services.notification_service import NotificationService
    
    # Notify Master Admin, Operations, and Legal roles
    for role in ["MASTER_ADMIN", "OPERATIONS", "OPERATION", "LEGAL"]:
        await NotificationService.send_to_role(
            db, role,
            title=f"📋 New Support Request",
            message=f"New support request from {current_user.email} ({company_name})\n\nType: {body.get('request_type', 'General')}\nDetails: {body.get('request_details', '')[:200]}",
            ntype="SUPPORT_REQUEST",
            action_url="http://localhost:3001/dashboard/admin"
        )
    
    return {
        "success": True,
        "message": "Support request submitted successfully!",
        "data": {"request_id": req_id}
    }


@business_requests_router.get("/support-requests")
async def list_support_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION', 'LEGAL', 'FINANCIAL']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    from sqlalchemy import text
    requests_result = await db.execute(text("""
        SELECT id, user_name, user_email, company_name, request_type, request_details, status, admin_response, created_at, updated_at
        FROM support_requests
        ORDER BY created_at DESC
    """))
    rows = requests_result.mappings().all()
    return {
        "success": True,
        "data": [{k: str(v) if v else None for k, v in dict(r).items()} for r in rows]
    }


@business_requests_router.get("/support-requests/my")
async def get_my_support_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    from sqlalchemy import text
    requests_result = await db.execute(text("""
        SELECT id, user_name, user_email, company_name, request_type, request_details, status, admin_response, created_at, updated_at
        FROM support_requests
        WHERE user_id = :user_id
        ORDER BY created_at DESC
    """), {"user_id": current_user.id})
    rows = requests_result.mappings().all()
    return {
        "success": True,
        "data": [{k: str(v) if v else None for k, v in dict(r).items()} for r in rows]
    }


@business_requests_router.post("/support-requests/{request_id}/resolve")
async def resolve_support_request(
    request_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION', 'LEGAL', 'FINANCIAL']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    body = await request.json()
    from sqlalchemy import text
    
    # Get the request first
    req_result = await db.execute(text("""
        SELECT user_email FROM support_requests WHERE id = :id
    """), {"id": request_id})
    req_row = req_result.fetchone()
    if not req_row:
        raise HTTPException(status_code=404, detail="Support request not found")
    
    await db.execute(text("""
        UPDATE support_requests
        SET status = 'RESOLVED',
            admin_response = :response,
            resolved_by = :resolved_by,
            resolved_at = NOW(),
            updated_at = NOW()
        WHERE id = :id
    """), {
        "response": body.get('response', ''),
        "resolved_by": current_user.id,
        "id": request_id
    })
    await db.commit()
    
    from app.services.notification_service import NotificationService
    await NotificationService.send(
        db, req_row[0],
        title="✅ Your Support Request Has Been Resolved",
        message=f"Your support request has been resolved.\n\nAdmin Response:\n{body.get('response', 'No response provided')}",
        ntype="SUCCESS"
    )
    
    return {
        "success": True,
        "message": "Support request resolved successfully!"
    }


