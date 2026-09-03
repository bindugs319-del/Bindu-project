"""
Admin routes - for plan management and system configuration
"""
from fastapi import APIRouter, Depends, Request, HTTPException
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.database import get_db
from app.models import User, Plan, Subscription, Invitation, Company, UserRole
from app.schemas import UpdateProfileRequest, UserProfileResponse, CreateInternalUserRequest, PlanCreate, PlanUpdate, InvitationCreate, InvitationUpdate, UserRoleUpdateRequest, DefaulterVerifyRequest, POReminderConfigUpdate
from app.services import AccessControlService, EmailService
from app.services.notification_service import NotificationService
from app.utils import ResponseFormatter, hash_password
from app.utils.audit import log_audit
from app.dependencies import get_current_user, require_admin, require_master_admin, is_developer
from app.exceptions import UnauthorizedFeature
from datetime import datetime, timezone
import uuid
import json
import logging

logger = logging.getLogger(__name__)

JSON_MEDIA_TYPE = "application/json"
router = APIRouter()


# ============ PLAN MANAGEMENT ============



@router.post("/plans")
async def create_plan(
    req: PlanCreate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new membership plan (admin only)"""
    plan = Plan(
        id=str(uuid.uuid4()),
        name=req.name.lower(),
        display_name=req.display_name,
        description=req.description,
        price=req.price,
        validity_days=req.validity_days,
        follow_up_limit=req.follow_up_limit,
        legal_assistance_limit=req.legal_assistance_limit,
        is_active=True,
    )
    db.add(plan)
    await log_audit(
        db=db,
        user=admin,
        action="PLAN_CREATE",
        entity_obj=plan,
        reason=f"Plan created: {plan.display_name}"
    )
    await db.commit()
    logger.info(f"Plan created: {plan.id} ({plan.name}) by admin {admin.id}")
    return ResponseFormatter.create_success(data={"id": plan.id}, message="Plan created successfully")


@router.put("/plans/{plan_id}")
async def update_plan(
    plan_id: str,
    req: PlanUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update a membership plan (admin only)"""
    stmt = select(Plan).where(Plan.id == plan_id)
    result = await db.execute(stmt)
    plan = result.scalars().first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if req.display_name is not None:
        plan.display_name = req.display_name
    if req.description is not None:
        plan.description = req.description
    if req.price is not None:
        plan.price = req.price
    if req.validity_days is not None:
        plan.validity_days = req.validity_days
    if req.follow_up_limit is not None:
        plan.follow_up_limit = req.follow_up_limit
    if req.legal_assistance_limit is not None:
        plan.legal_assistance_limit = req.legal_assistance_limit
    
    await log_audit(
        db=db,
        user=admin,
        action="PLAN_UPDATE",
        entity_obj=plan,
        reason=f"Plan updated: {plan.display_name}",
        new_data=req.model_dump(exclude_unset=True)
    )
    await db.commit()
    logger.info(f"Plan updated: {plan_id} by admin {admin.id}")
    return ResponseFormatter.create_success(message="Plan updated successfully")


@router.delete("/plans/{plan_id}")
async def deactivate_plan(
    plan_id: str,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Deactivate a membership plan (admin only) - soft delete"""
    stmt = select(Plan).where(Plan.id == plan_id)
    result = await db.execute(stmt)
    plan = result.scalars().first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    plan.is_active = False
    await log_audit(
        db=db,
        user=admin,
        action="PLAN_DEACTIVATE",
        entity_obj=plan,
        reason=f"Plan deactivated: {plan.display_name}"
    )
    await db.commit()
    logger.info(f"Plan deactivated: {plan_id} by admin {admin.id}")
    return ResponseFormatter.create_success(message="Plan deactivated successfully")


@router.get("/plans")
async def list_all_plans(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List all plans including inactive ones (admin only)"""
    stmt = select(Plan).order_by(Plan.price)
    result = await db.execute(stmt)
    plans = result.scalars().all()
    return ResponseFormatter.create_success(data=[{
        "id": p.id,
        "name": p.name,
        "display_name": p.display_name,
        "description": p.description,
        "price": p.price,
        "validity_days": p.validity_days,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None
    } for p in plans])


# ============ USER MANAGEMENT ============

@router.get("/companies")
async def get_all_companies(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all registered companies with stats"""
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val not in ['MASTER_ADMIN', 'OPERATION', 'OPERATIONS', 'FINANCIAL', 'FINANCE', 'LEGAL']:
        raise HTTPException(status_code=403)
        
    from sqlalchemy import text
    result = await db.execute(text("""
        SELECT 
            c.id,
            c.company_name,
            c.gstin,
            c.domain_name,
            c.is_verified,
            c.created_at,
            COUNT(DISTINCT u.id) as user_count,
            COUNT(DISTINCT po.id) as po_count
        FROM companies c
        LEFT JOIN users u ON c.id = u.company_id
        LEFT JOIN purchase_orders po ON c.id = po.company_id
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """))
    companies = []
    for r in result.fetchall():
        comp = dict(r._mapping)
        comp['created_at'] = comp['created_at'].isoformat() if comp['created_at'] else None
        companies.append(comp)
        
    return {"success": True, "data": companies, "total": len(companies)}


@router.get("/users")
async def get_company_users(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    try:
        company_id = getattr(current_user, 'company_id', None)
        if not company_id:
            return {"success": True, "data": []}
        
        result = await db.execute(text("""
            SELECT 
                u.id,
                COALESCE(u.name, u.email) as name,
                u.email,
                u.role,
                COALESCE(u.status, 'ACTIVE') as status,
                u.is_active,
                u.created_at,
                u.company_id
            FROM users u
            WHERE u.company_id = :cid
            ORDER BY u.created_at DESC
        """), {"cid": company_id})
        users = []
        for r in result.fetchall():
            u = dict(r._mapping)
            # Convert role enum to string
            if u.get('role'):
                if hasattr(u['role'], 'value'):
                    u['role'] = u['role'].value
                else:
                    u['role'] = str(u['role'])
            if u.get('created_at'):
                ts = u['created_at']
                u['created_at'] = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
            users.append(u)
        return {"success": True, "data": users, "total": len(users)}
    except Exception as e:
        import traceback
        print("ERROR in /admin/users:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-user")
async def create_internal_user(
    req: CreateInternalUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_master_admin)]
):
    """Create internal users (FINANCIAL, OPERATION, LEGAL) - Master Admin only"""
    name = str(req.name or '').strip()
    email = str(req.email).strip().lower()
    role = str(req.role or 'OPERATION').strip().upper()
    gstin = str(req.gstin or '22AAAAD0000A1Z5').strip()
    password = str(req.password).strip()
    
    if not name or not email or not password:
        raise HTTPException(status_code=422, detail="name, email and password are required")
    
    # Handle UI role variation
    if role == "OPERATIONS":
        role = "OPERATION"
        
    try:
        target_role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid role: {role}")
    
    # Check duplicate
    stmt = select(User).where(User.email == email)
    existing = (await db.execute(stmt)).scalars().first()
    
    user_exists = False
    action_taken = "CREATED"
    
    if existing:
        user_exists = True
        action_taken = "REINVITED"
        
        # Reactivate user if inactive
        existing.is_active = True
        existing.status = 'ACTIVE'
        existing.subscription_bypass = True
        existing.full_access = True
        existing.role = target_role
        
        # Update password
        from app.utils.password import hash_password
        existing.password_hash = hash_password(password)
        
        new_user = existing
        
        await log_audit(
            db=db, 
            user=current_user, 
            action="USER_REINVITED", 
            entity_obj=new_user, 
            reason=f"Reinvited existing {role} user: {email}"
        )
        print(f"[CREATE_USER] Reinvited existing {role} user: {email}")
    else:
        # Hash password
        from app.utils.password import hash_password
        hashed = hash_password(password)
        
        user_id = str(uuid.uuid4())
        new_user = User(
            id=user_id,
            name=name,
            email=email,
            role=target_role,
            gstin=gstin or current_user.gstin,
            company_id=current_user.company_id,
            company_name=current_user.company_name,
            password_hash=hashed,
            is_active=True,
            status='ACTIVE',
            subscription_bypass=True,
            full_access=True,
            phone='N/A'
        )
        db.add(new_user)
        
        # Audit log
        await log_audit(
            db=db, 
            user=current_user, 
            action="USER_CREATED", 
            entity_obj=new_user, 
            reason=f"Created {role} user: {email}"
        )
        
        await db.commit()
        await db.refresh(new_user)
        print(f"[CREATE_USER] Created {role} user: {email}")
    
    # Send welcome email
    login_url = "http://localhost:3001/auth/login"
    role_tasks = {
        'OPERATION': '- Process subscription requests\n- Review business requests\n- Map vendor data',
        'FINANCIAL': '- Review high-value POs\n- Verify payments\n- Track invoices',
        'LEGAL': '- Handle legal notices\n- Review GSTIN reports\n- Process legal requests',
        'COMPANY_ADMIN': '- Manage company POs\n- View credibility index\n- Invite team members'
    }
    
    email_body = f"""Dear {name},

Welcome to CreditDataWatch!

Your account has been created by the Master Admin.

YOUR LOGIN DETAILS:
Email: {email}
Password: {password}
Role: {role}
GSTIN: {gstin}

CLICK TO LOGIN:
{login_url}

YOUR RESPONSIBILITIES:
{role_tasks.get(role, '')}

Please change your password after first login.

Regards,
CreditDataWatch Team
{current_user.email}"""

    try:
        from app.services.email_service import EmailService
        email_svc = EmailService()
        await email_svc.send_email(
            to_email=email,
            subject=f"Welcome to CreditDataWatch - Your Login Details ({role})",
            body=email_body
        )
        logger.info(f"[CREATE_USER] Welcome email sent to {email}")
        print(f"[CREATE_USER] Email sent to {email}")
    except Exception as e:
        logger.error(f"[CREATE_USER] Welcome email failed for {email}: {e}")
        print(f"[CREATE_USER] Email failed (user still created): {e}")
    
    await db.commit()
    await db.refresh(new_user)
    
    message = f"User {name} created successfully. Login email sent to {email}" if not user_exists else f"User already existed. Invite email resent successfully to {email}"
    
    return ResponseFormatter.create_success(
        message=message,
        data={
            "id": new_user.id, 
            "email": email, 
            "role": role, 
            "name": name,
            "temp_password": password,
            "user_exists": user_exists,
            "action": action_taken
        }
    )


@router.post("/invitations")
async def create_invitation(
    payload: InvitationCreate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create employee invitation (admin only)"""
    if not admin.company_id:
        raise HTTPException(status_code=400, detail="Admin must be associated with a company")
    
    email = payload.email.lower()
    role = "USER"
    expiry_hours = payload.expiry_hours
    if expiry_hours < 1 or expiry_hours > 168:
        raise HTTPException(status_code=400, detail="expiry_hours must be between 1 and 168")
    token = str(uuid.uuid4())
    from datetime import timedelta
    # `invitations.expires_at` is TIMESTAMP WITHOUT TIME ZONE. asyncpg (used by
    # the live app, unlike psycopg2 used by Alembic) rejects a tz-aware
    # datetime here with "can't subtract offset-naive and offset-aware
    # datetimes" — so this must stay naive UTC, not datetime.now(timezone.utc).replace(tzinfo=None).
    now = datetime.utcnow().replace(microsecond=0)
    expires_at = now + timedelta(hours=expiry_hours)

    # Verify admin has company
    stmt = select(Company).where(Company.id == admin.company_id)
    res = await db.execute(stmt)
    company = res.scalars().first()
    if not company:
        raise HTTPException(status_code=400, detail="Company not found")

    # Safe domain check — only enforce if company has domain set 
    company_domain = getattr(company, 'domain_name', None) 
    allow_any = getattr(company, 'allow_any_domain', True) 
    
    if not allow_any and company_domain: 
        invited_domain = email.split('@')[1] if '@' in email else '' 
        if invited_domain != company_domain: 
            raise HTTPException( 
                status_code=400, 
                detail=f"Invited email must be from your company domain @{company_domain}. To allow any domain, update your company settings." 
            ) 

    inv = Invitation(
        id=str(uuid.uuid4()),
        company_id=company.id,
        email=email,
        role=role,
        token=token,
        expires_at=expires_at,
        status="PENDING",
    )
    db.add(inv)
    await log_audit(
        db=db,
        user=admin,
        action="INVITATION_CREATE",
        entity_obj=inv,
        reason=f"Invited {email}"
    )
    await db.commit()

    # Send invitation email (after commit)
    try:
        from app.services.email_service import EmailService
        await EmailService.send_invitation_email(
            to_email=email,
            company_name=company.company_name,
            role=role,
            token=token,
            expires_at=expires_at.isoformat(),
        )
    except Exception as e:
        logger.warning(f"Invitation email failed for {email}: {e}")
    
    return ResponseFormatter.create_success(message="Invitation created", data={"token": token, "expires_at": expires_at.isoformat(), "expiry_hours": expiry_hours})

@router.get("/invitations")
async def list_invitations(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 50
):
    """List invitations for admin's company"""
    try:
        print(f"[ADMIN INVITATIONS] Admin: {admin.email}, company_id: {admin.company_id}")
        if not admin.company_id:
            # If no company (like Master Admin), return empty list
            return ResponseFormatter.create_success(data=[])
        
        stmt = select(Invitation).where(Invitation.company_id == admin.company_id).offset(skip).limit(limit).order_by(Invitation.created_at.desc())
        result = await db.execute(stmt)
        invitations = result.scalars().all()
        print(f"[ADMIN INVITATIONS] Found {len(invitations)} invitations")
        
        def safe_attr(obj, attr, default=None):
            val = getattr(obj, attr, default)
            if val is None:
                return default
            return val
        
        def safe_iso(dt):
            if dt is None:
                return None
            try:
                return dt.isoformat()
            except Exception:
                return str(dt)
        
        return ResponseFormatter.create_success(data=[{
            "id": safe_attr(inv, "id"),
            "email": safe_attr(inv, "email"),
            "role": str(safe_attr(inv, "role", "USER")),
            "token": safe_attr(inv, "token"),
            "expires_at": safe_iso(safe_attr(inv, "expires_at")),
            "status": safe_attr(inv, "status", "PENDING"),
            "created_at": safe_iso(safe_attr(inv, "created_at"))
        } for inv in invitations])
    except Exception as e:
        import traceback
        print("ERROR in /admin/invitations:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/invitations/{invitation_id}")
async def update_invitation(
    invitation_id: str,
    payload: InvitationUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update invitation role and/or expiry (hours) - email is immutable"""
    if not admin.company_id:
        raise HTTPException(status_code=400, detail="Admin must be associated with a company")
    
    from datetime import timedelta
    stmt = select(Invitation).where(Invitation.id == invitation_id, Invitation.company_id == admin.company_id)
    result = await db.execute(stmt)
    inv = result.scalars().first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    # Role must remain USER for invitations
    inv.role = "USER"
    if payload.expiry_hours is not None:
        now = datetime.now(timezone.utc).replace(tzinfo=None).replace(microsecond=0)
        inv.expires_at = now + timedelta(hours=payload.expiry_hours)
    
    await log_audit(
        db=db,
        user=admin,
        action="INVITATION_UPDATE",
        entity_obj=inv,
        reason=f"Updated invitation for {inv.email}",
        new_data=payload.model_dump(exclude_unset=True)
    )
    await db.commit()
    return ResponseFormatter.create_success(message="Invitation updated")


@router.delete("/invitations/{invitation_id}")
async def delete_invitation(
    invitation_id: str,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete an invitation"""
    if not admin.company_id:
        raise HTTPException(status_code=400, detail="Admin must be associated with a company")
    
    stmt = select(Invitation).where(Invitation.id == invitation_id, Invitation.company_id == admin.company_id)
    result = await db.execute(stmt)
    inv = result.scalars().first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    await log_audit(
        db=db,
        user=admin,
        action="INVITATION_DELETE",
        entity_obj=inv,
        reason=f"Deleted invitation for {inv.email}"
    )
    await db.delete(inv)
    await db.commit()
    return ResponseFormatter.create_success(message="Invitation deleted")

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user = Depends(get_current_user)
):
    # Handle current_user.role (could be enum)
    current_role = getattr(current_user.role, "value", str(current_user.role))
    if current_role != 'MASTER_ADMIN' and not is_developer(current_user):
        raise HTTPException(status_code=403, detail="Only MASTER_ADMIN can update roles")
    try:
        body = await request.json()
        new_role = body.get('role', '').upper()
        valid_roles = ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION', 'FINANCIAL', 'FINANCE', 'LEGAL', 'USER', 'COMPANY_ADMIN']
        if new_role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")
        # Handle role mapping
        if new_role == 'OPERATIONS':
            new_role = 'OPERATION'
        if new_role == 'FINANCE':
            new_role = 'FINANCIAL'
        result = await db.execute(text("""
            UPDATE users SET role = :role WHERE id = :uid
        """), {"role": new_role, "uid": user_id})
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        return {"success": True, "message": f"Role updated to {new_role}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user = Depends(get_current_user)
):
    # Handle current_user.role (could be enum)
    current_role = getattr(current_user.role, "value", str(current_user.role))
    if current_role != 'MASTER_ADMIN' and not is_developer(current_user):
        raise HTTPException(status_code=403, detail="Only MASTER_ADMIN can delete users")
    if str(current_user.id) == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    try:
        # Check user exists first using ORM
        from app.models import User
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Use ORM delete which should handle cascades properly
        await db.delete(user)
        await db.commit()
        
        return {"success": True, "message": "User deleted successfully"}
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/companies/{company_id}")
async def delete_company(
    company_id: str,
    confirm: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a company and everything tied to it (users, purchase orders,
    sales invoices, ratings) via the ORM's cascade="all, delete-orphan"
    relationships already defined on the Company model.

    Two-step confirm flow, matching the frontend's preview-then-confirm UX:
    - confirm=false (default): just counts what WOULD be deleted, no writes.
    - confirm=true: actually performs the delete.
    """
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val != "MASTER_ADMIN" and not is_developer(current_user):
        raise HTTPException(status_code=403, detail="Only MASTER_ADMIN can delete companies")

    company_result = await db.execute(select(Company).where(Company.id == company_id))
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    users_count = (await db.execute(
        text("SELECT COUNT(*) FROM users WHERE company_id = :cid"), {"cid": company_id}
    )).scalar() or 0
    pos_count = (await db.execute(
        text("SELECT COUNT(*) FROM purchase_orders WHERE company_id = :cid"), {"cid": company_id}
    )).scalar() or 0
    invoices_count = (await db.execute(
        text("SELECT COUNT(*) FROM sales_invoices WHERE company_id = :cid"), {"cid": company_id}
    )).scalar() or 0

    if not confirm:
        return {
            "success": True,
            "will_also_delete": {
                "users": users_count,
                "purchase_orders": pos_count,
                "sales_invoices": invoices_count,
            },
        }

    try:
        await db.delete(company)
        await db.commit()
        return {
            "success": True,
            "message": f"Deleted \"{company.company_name}\" and {users_count} user(s), {pos_count} PO(s), {invoices_count} invoice(s).",
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{company_id}")
async def get_company_details(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get company details including users, POs, and credibility"""
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val not in ['MASTER_ADMIN', 'OPERATION', 'OPERATIONS', 'FINANCIAL', 'FINANCE', 'LEGAL']:
        raise HTTPException(status_code=403)
        
    from sqlalchemy import text
    
    # Get company info
    company_result = await db.execute(text("""
        SELECT * FROM companies WHERE id = :cid LIMIT 1
    """), {"cid": company_id})
    company = company_result.fetchone()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    company_dict = dict(company._mapping)
    company_dict['created_at'] = company_dict['created_at'].isoformat() if company_dict['created_at'] else None
    company_dict['updated_at'] = company_dict['updated_at'].isoformat() if company_dict['updated_at'] else None
    
    # Get users
    users_result = await db.execute(text("""
        SELECT id, name, email, role, status, created_at 
        FROM users WHERE company_id = :cid ORDER BY created_at DESC
    """), {"cid": company_id})
    users = []
    for r in users_result.fetchall():
        u = dict(r._mapping)
        u['role'] = u['role'].value if hasattr(u['role'], 'value') else str(u['role'])
        u['created_at'] = u['created_at'].isoformat() if u['created_at'] else None
        users.append(u)
        
    # Get POs
    pos_result = await db.execute(text("""
        SELECT id, po_number, vendor, amount, due_date, status, created_at
        FROM purchase_orders WHERE company_id = :cid ORDER BY created_at DESC
    """), {"cid": company_id})
    pos = []
    for r in pos_result.fetchall():
        po = dict(r._mapping)
        po['due_date'] = po['due_date'].isoformat() if po['due_date'] else None
        po['created_at'] = po['created_at'].isoformat() if po['created_at'] else None
        pos.append(po)
        
    # Get invoices
    invoices_result = await db.execute(text("""
        SELECT id, invoice_number, counterparty_name, total, payment_due_date, status, created_at
        FROM sales_invoices WHERE company_id = :cid ORDER BY created_at DESC
    """), {"cid": company_id})
    invoices = []
    for r in invoices_result.fetchall():
        inv = dict(r._mapping)
        inv['payment_due_date'] = inv['payment_due_date'].isoformat() if inv['payment_due_date'] else None
        inv['created_at'] = inv['created_at'].isoformat() if inv['created_at'] else None
        invoices.append(inv)

    # Get credibility
    cred_result = await db.execute(text("""
        SELECT * FROM company_credibility_index WHERE company_id = :cid LIMIT 1
    """), {"cid": company_id})
    cred = cred_result.fetchone()
    credibility = None
    if cred:
        credibility = dict(cred._mapping)
        credibility['last_calculated_at'] = credibility['last_calculated_at'].isoformat() if credibility['last_calculated_at'] else None
        
    return {
        "success": True, 
        "data": {
            "company": company_dict, 
            "users": users, 
            "purchase_orders": pos, 
            "invoices": invoices,
            "credibility": credibility
        }
    }

@router.get("/users/{user_id}")
async def get_user_profile(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    """Get full user profile (MASTER_ADMIN, OPERATIONS, OPERATION)"""
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "success": True,
        "data": {
            "id": str(user.id),
            "name": getattr(user, 'name', None),
            "email": user.email,
            "role": user.role,
            "gstin": user.gstin,
            "company_name": getattr(user, 'company_name', None),
            "company_id": str(user.company_id) if user.company_id else None,
            "phone": getattr(user, 'phone', None),
            "status": getattr(user, 'status', None),
            "is_active": user.is_active,
            "subscription_status": getattr(user, 'subscription_status', None),
            "subscription_bypass": getattr(user, 'subscription_bypass', False),
            "created_at": str(user.created_at) if user.created_at else None,
            "updated_at": str(user.updated_at) if user.updated_at else None,
        }
    }


@router.get("/users/{user_id}/pos")
async def get_user_pos(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    """Get user's POs (MASTER_ADMIN, OPERATIONS, OPERATION only)"""
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']:
        raise HTTPException(status_code=403)
    
    from sqlalchemy import text
    pos = await db.execute(text("""
        SELECT id, po_number, vendor, amount, due_date, status,
               created_at, payment_completed_at
        FROM purchase_orders
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        LIMIT 50
    """), {"user_id": user_id})
    
    rows = pos.mappings().all()
    return {
        "success": True,
        "data": [{k: str(v) if v else None for k, v in dict(r).items()} for r in rows]
    }


@router.get("/users/{user_id}/invoices")
async def get_user_invoices(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    """Get user's sales invoices (MASTER_ADMIN, OPERATIONS, OPERATION only)"""
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']:
        raise HTTPException(status_code=403)

    from sqlalchemy import text
    invoices = await db.execute(text("""
        SELECT id, invoice_number, counterparty_name, total, payment_due_date, status,
               created_at, payment_completed_at
        FROM sales_invoices
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        LIMIT 50
    """), {"user_id": user_id})

    rows = invoices.mappings().all()
    return {
        "success": True,
        "data": [{k: str(v) if v else None for k, v in dict(r).items()} for r in rows]
    }


@router.get("/users/{user_id}/credibility")
async def get_user_credibility(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    """Get user's credibility, computed from their invoices (MASTER_ADMIN, OPERATIONS, OPERATION only)"""
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']:
        raise HTTPException(status_code=403)

    from datetime import timedelta
    from app.services.credibility_service import CredibilityService

    user_row = await db.execute(
        text("SELECT company_id, company_name FROM users WHERE id = :id"),
        {"id": user_id}
    )
    user = user_row.fetchone()

    if not user or not user[0]:
        return {"success": True, "data": None}

    company_id, company_name = user[0], user[1]
    if not company_name:
        comp_row = await db.execute(
            text("SELECT company_name FROM companies WHERE id = :id"),
            {"id": company_id}
        )
        comp = comp_row.fetchone()
        company_name = comp[0] if comp else None

    if not company_name:
        return {"success": True, "data": None}

    window_days = await CredibilityService.get_config(db)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=window_days)

    inv_rows = await db.execute(text("""
        SELECT status, payment_due_date, payment_completed_at
        FROM sales_invoices
        WHERE lower(counterparty_name) = lower(:company_name)
          AND created_at >= :cutoff
    """), {"company_name": company_name, "cutoff": cutoff})

    rows = inv_rows.fetchall()
    total = len(rows)
    paid = sum(1 for r in rows if (r[0] or '').lower() == 'paid')
    unpaid = sum(1 for r in rows if (r[0] or '').lower() in ('draft', 'sent', 'overdue'))
    paid_late = max(0, total - paid - unpaid)

    delays = []
    for _status, due_date, completed_at in rows:
        if completed_at and due_date:
            completed_date = completed_at.date() if hasattr(completed_at, 'date') else completed_at
            delays.append((completed_date - due_date).days)
    avg_delay = round(sum(delays) / len(delays), 1) if delays else 0.0

    metrics = {
        "total_pos": total,
        "paid_on_time": paid,
        "paid_late": paid_late,
        "unpaid": unpaid,
        "avg_delay_days": avg_delay,
    }
    scored = await CredibilityService.score_with_ai(metrics)

    data = {
        "score": scored["score"],
        "grade": scored["grade"],
        "risk_level": scored["risk_level"],
        "stars": scored["stars"],
        "total_invoices": total,
        "paid_on_time": paid,
        "unpaid": unpaid,
        "avg_delay_days": avg_delay,
        "ai_summary": scored["ai_summary"].replace("POs", "invoices"),
    }

    return {"success": True, "data": data}


@router.get("/users/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    """Get user's activity log (MASTER_ADMIN, OPERATIONS, OPERATION only)"""
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
    if user_role_val not in ['MASTER_ADMIN', 'OPERATIONS', 'OPERATION']:
        raise HTTPException(status_code=403)
    
    from sqlalchemy import text
    
    user_row = await db.execute(
        text("SELECT email FROM users WHERE id = :id"),
        {"id": user_id}
    )
    user = user_row.fetchone()
    
    if not user:
        return {"success": True, "data": []}
    
    logs = await db.execute(text("""
        SELECT id, action, entity_type, po_number, vendor_name,
               reason, created_at
        FROM audit_logs
        WHERE user_email = :email
        ORDER BY created_at DESC
        LIMIT 100
    """), {"email": user[0]})
    
    rows = logs.mappings().all()
    return {
        "success": True,
        "data": [{k: str(v) if v else None for k, v in dict(r).items()} for r in rows]
    }

# ============ DEFAULTER VERIFICATION ============

@router.get("/defaulters/pending")
async def list_pending_defaulters(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 50
):
    """List pending defaulter cases for verification (admin only)"""
    from app.models import DefaulterCase
    
    stmt = select(DefaulterCase).where(
        DefaulterCase.approval_status == "pending"
    ).offset(skip).limit(limit).order_by(DefaulterCase.created_at.desc())
    
    result = await db.execute(stmt)
    cases = result.scalars().all()
    
    return ResponseFormatter.create_success(data=[{
        "id": c.id,
        "business_name": c.business_name,
        "business_gstin": c.business_gstin,
        "amount": c.amount,
        "status": c.approval_status,
        "created_at": c.created_at.isoformat(),
    } for c in cases])


@router.put("/defaulters/{case_id}/verify")
async def verify_defaulter_case(
    case_id: str,
    req: DefaulterVerifyRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Approve or reject a defaulter case (admin only)"""
    from app.models import DefaulterCase
    
    stmt = select(DefaulterCase).where(DefaulterCase.id == case_id)
    result = await db.execute(stmt)
    case = result.scalars().first()
    
    if not case:
        raise HTTPException(status_code=404, detail="Defaulter case not found")
    
    action = req.action.lower()  # approve, reject
    notes = req.notes
    
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action (must be 'approve' or 'reject')")
    
    case.approval_status = "approved" if action == "approve" else "rejected"
    case.verified_by = admin.id
    case.verification_date = datetime.utcnow()
    case.notes = notes
    
    if action == "approve":
        # Reward the user with 50 points
        from app.services.wallet_service import WalletService
        wallet_service = WalletService(db)
        await wallet_service.add_transaction(
            user_id=case.user_id,
            amount=50.0,
            trans_type="CREDIT",
            reference_type="BONUS",
            reference_id=case.id,
            description=f"Reward for verified defaulter: {case.business_name}"
        )

    await log_audit(
        db=db,
        user=admin,
        action=f"DEFAULTER_{action.upper()}",
        entity_obj=case,
        reason=notes
    )
    await db.commit()
    logger.info(f"Defaulter case {case_id} {action}ed by admin {admin.id}")
    return ResponseFormatter.create_success(message=f"Defaulter case {action}ed")


# ============ ANALYTICS ============

@router.get("/analytics/subscriptions")
async def subscription_analytics(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get subscription analytics (admin only)"""
    stmt = select(Subscription).where(Subscription.is_active == True)
    result = await db.execute(stmt)
    subs = result.scalars().all()
    
    # Group by plan
    by_plan = {}
    for sub in subs:
        plan_name = sub.plan.name if sub.plan else "unknown"
        by_plan[plan_name] = by_plan.get(plan_name, 0) + 1
    
    return ResponseFormatter.create_success(data={
        "total_active": len(subs),
        "by_plan": by_plan,
    })


@router.get("/analytics/defaulters")
async def defaulter_analytics(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get defaulter case analytics (admin only)"""
    from app.models import DefaulterCase
    
    stmt = select(DefaulterCase)
    result = await db.execute(stmt)
    cases = result.scalars().all()
    
    # Group by status
    by_status = {
        "pending": len([c for c in cases if c.approval_status == "pending"]),
        "approved": len([c for c in cases if c.approval_status == "approved"]),
        "rejected": len([c for c in cases if c.approval_status == "rejected"]),
    }
    
    # Total amount
    total_amount = sum(c.amount for c in cases)
    
    return ResponseFormatter.create_success(data={
        "total_cases": len(cases),
        "by_status": by_status,
        "total_amount": total_amount,
    })


@router.get("/settings/alert-message")
async def get_alert_message(
    current_user: Annotated[any, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get the current homepage alert message (Master Admin only)."""
    row = (await db.execute(text("""
        SELECT value, updated_by, updated_at FROM system_settings WHERE key = 'alert_message'
    """))).mappings().first()
    return {"success": True, "data": {
        "message": row["value"] if row else "",
        "updated_by": row["updated_by"] if row else None,
        "updated_at": str(row["updated_at"]) if row and row["updated_at"] else None,
    }}


@router.post("/settings/alert-message")
async def update_alert_message(
    request: Request,
    current_user: Annotated[any, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update the homepage alert message (Master Admin only). An empty
    message hides the alert entirely on the homepage."""
    body = await request.json()
    message = (body.get("message") or "").strip()

    await db.execute(text("""
        INSERT INTO system_settings (id, key, value, description, updated_by, updated_at)
        VALUES (gen_random_uuid(), 'alert_message', :value, 'Homepage alert banner text, shown once per visitor session', :email, NOW())
        ON CONFLICT (key) DO UPDATE SET
            value = :value,
            updated_by = :email,
            updated_at = NOW()
    """), {"value": message, "email": current_user.email})
    await db.commit()
    return {"success": True, "message": "Alert message updated"}


@router.get("/settings/alert-message/public")
async def get_alert_message_public(db: Annotated[AsyncSession, Depends(get_db)]):
    """Public, no-auth endpoint the homepage itself calls to display the
    current alert message. Returns an empty string (no alert shown) if
    nothing has been configured yet, rather than erroring."""
    try:
        row = (await db.execute(text(
            "SELECT value FROM system_settings WHERE key = 'alert_message'"
        ))).mappings().first()
        return {"success": True, "data": {"message": row["value"] if row else ""}}
    except Exception:
        return {"success": True, "data": {"message": ""}}


def _validate_stat_items(items, expected_count, section_name):
    """Shared validation for both trust-ticker and business-stats payloads:
    must be a list of exactly `expected_count` {label, value} objects, both
    non-empty strings. Raises HTTPException(422) with a clear message on
    the first problem found, rather than saving malformed data."""
    if not isinstance(items, list) or len(items) != expected_count:
        raise HTTPException(422, f"{section_name} must have exactly {expected_count} entries")
    for i, item in enumerate(items):
        label = (item.get("label") or "").strip() if isinstance(item, dict) else ""
        value = (item.get("value") or "").strip() if isinstance(item, dict) else ""
        if not label or not value:
            raise HTTPException(422, f"{section_name} entry {i + 1} needs both a label and a value")
    return [{"label": (item.get("label") or "").strip(), "value": (item.get("value") or "").strip()} for item in items]


async def _get_stat_setting(db, key, default_items):
    row = (await db.execute(text(
        "SELECT value, updated_by, updated_at FROM system_settings WHERE key = :key"
    ), {"key": key})).mappings().first()
    try:
        items = json.loads(row["value"]) if row and row["value"] else default_items
    except (json.JSONDecodeError, TypeError):
        items = default_items
    return {
        "items": items,
        "updated_by": row["updated_by"] if row else None,
        "updated_at": str(row["updated_at"]) if row and row["updated_at"] else None,
    }


async def _save_stat_setting(db, key, description, items, email):
    await db.execute(text("""
        INSERT INTO system_settings (id, key, value, description, updated_by, updated_at)
        VALUES (gen_random_uuid(), :key, :value, :description, :email, NOW())
        ON CONFLICT (key) DO UPDATE SET
            value = :value,
            updated_by = :email,
            updated_at = NOW()
    """), {"key": key, "value": json.dumps(items), "description": description, "email": email})
    await db.commit()


DEFAULT_TRUST_TICKER = [
    {"label": "Average Trust Score", "value": "98%"},
    {"label": "Verified Companies", "value": "12,450"},
    {"label": "Secure Transactions", "value": "4,56,780+"},
]

DEFAULT_BUSINESS_STATS = [
    {"label": "Highest No. of Defaulters by a Single Customer", "value": "668+"},
    {"label": "Total Number of MSMEs Connected", "value": "39+ Lakhs"},
    {"label": "Average Percentage of Settlements", "value": "59%"},
    {"label": "Total amount reported defaulter", "value": "4578+ Crores"},
]


@router.get("/settings/trust-ticker")
async def get_trust_ticker(
    current_user: Annotated[any, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get the homepage trust ticker's 3 stats (Master Admin only)."""
    return {"success": True, "data": await _get_stat_setting(db, "trust_ticker_stats", DEFAULT_TRUST_TICKER)}


@router.post("/settings/trust-ticker")
async def update_trust_ticker(
    request: Request,
    current_user: Annotated[any, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update the homepage trust ticker's 3 stats (Master Admin only)."""
    body = await request.json()
    items = _validate_stat_items(body.get("items"), 3, "Trust ticker")
    await _save_stat_setting(db, "trust_ticker_stats", "Homepage trust ticker stats (3 items)", items, current_user.email)
    return {"success": True, "message": "Trust ticker updated"}


@router.get("/settings/trust-ticker/public")
async def get_trust_ticker_public(db: Annotated[AsyncSession, Depends(get_db)]):
    """Public, no-auth endpoint the homepage calls to display the trust ticker."""
    try:
        data = await _get_stat_setting(db, "trust_ticker_stats", DEFAULT_TRUST_TICKER)
        return {"success": True, "data": {"items": data["items"]}}
    except Exception:
        return {"success": True, "data": {"items": DEFAULT_TRUST_TICKER}}


@router.get("/settings/business-stats")
async def get_business_stats(
    current_user: Annotated[any, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get the homepage 'Trusted by Thousands of Businesses' 4 stats (Master Admin only)."""
    return {"success": True, "data": await _get_stat_setting(db, "business_impact_stats", DEFAULT_BUSINESS_STATS)}


@router.post("/settings/business-stats")
async def update_business_stats(
    request: Request,
    current_user: Annotated[any, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update the homepage 'Trusted by Thousands of Businesses' 4 stats (Master Admin only)."""
    body = await request.json()
    items = _validate_stat_items(body.get("items"), 4, "Business impact stats")
    await _save_stat_setting(db, "business_impact_stats", "Homepage business impact stats (4 items)", items, current_user.email)
    return {"success": True, "message": "Business impact stats updated"}


@router.get("/settings/business-stats/public")
async def get_business_stats_public(db: Annotated[AsyncSession, Depends(get_db)]):
    """Public, no-auth endpoint the homepage calls to display these stats."""
    try:
        data = await _get_stat_setting(db, "business_impact_stats", DEFAULT_BUSINESS_STATS)
        return {"success": True, "data": {"items": data["items"]}}
    except Exception:
        return {"success": True, "data": {"items": DEFAULT_BUSINESS_STATS}}


@router.get("/role-settings")
@router.get("/settings/roles")
async def get_role_settings(
    current_user: Annotated[any, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get current role enable/disable settings from system_settings table (matches frontend format)"""
    from sqlalchemy import text
    settings_result = await db.execute(text("""
        SELECT key, value, description, updated_by, updated_at
        FROM system_settings
        WHERE key IN ('financial_role_enabled', 'legal_role_enabled')
    """))
    rows = settings_result.mappings().all()
    data = {}
    for row in rows:
        data[row['key']] = {
            "enabled": row['value'] == 'true',
            "description": row['description'],
            "updated_by": row['updated_by'],
            "updated_at": str(row['updated_at']) if row['updated_at'] else None
        }
    return {"success": True, "data": data}


@router.post("/role-settings")
async def update_role_setting(
    payload: dict,
    current_user: Annotated[any, Depends(require_master_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update role enable/disable setting in role_settings table"""
    role_name = payload.get("role_name")
    is_enabled = payload.get("is_enabled")
    
    if not role_name or role_name not in ["FINANCIAL", "LEGAL"]:
        raise HTTPException(status_code=400, detail="Invalid role_name")
    
    await db.execute(text("""
        INSERT INTO role_settings (role_name, is_enabled, updated_by, updated_at)
        VALUES (:role_name, :is_enabled, :updated_by, NOW())
        ON CONFLICT (role_name) DO UPDATE SET
            is_enabled = :is_enabled,
            updated_by = :updated_by,
            updated_at = NOW()
    """), {
        "role_name": role_name,
        "is_enabled": is_enabled,
        "updated_by": current_user.email
    })
    
    await db.commit()
    return {"success": True, "message": f"{role_name} role updated"}


@router.get("/settings/roles-system")
async def get_system_role_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    """Get current role enable/disable settings (backward compatible)"""
    from sqlalchemy import text
    settings_result = await db.execute(text("""
        SELECT key, value, description, updated_by, updated_at
        FROM system_settings
        WHERE key IN ('financial_role_enabled', 'legal_role_enabled')
    """))
    rows = settings_result.mappings().all()
    data = {}
    for row in rows:
        data[row['key']] = {
            "enabled": row['value'] == 'true',
            "description": row['description'],
            "updated_by": row['updated_by'],
            "updated_at": str(row['updated_at']) if row['updated_at'] else None
        }
    return {"success": True, "data": data}


@router.post("/settings/roles/{role_key}/toggle")
async def toggle_role(
    role_key: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[any, Depends(get_current_user)]
):
    """Enable or disable a role (backward compatible)"""
    if current_user.role != 'MASTER_ADMIN':
        raise HTTPException(403, "Master Admin only")
    
    if role_key not in ['financial_role_enabled', 'legal_role_enabled']:
        raise HTTPException(400, "Invalid role key")
    
    try:
        from sqlalchemy import text
        body = await request.json()
        new_value = 'true' if body.get('enabled') else 'false'
        
        await db.execute(text("""
            UPDATE system_settings
            SET value = :value, updated_by = :email, updated_at = NOW()
            WHERE key = :key
        """), {"value": new_value, "email": current_user.email, "key": role_key})
        
        # Also update role_settings table
        role_name = "FINANCIAL" if "financial" in role_key else "LEGAL"
        await db.execute(text("""
            INSERT INTO role_settings (role_name, is_enabled, updated_by, updated_at)
            VALUES (:role_name, :is_enabled, :updated_by, NOW())
            ON CONFLICT (role_name) DO UPDATE SET
                is_enabled = :is_enabled,
                updated_by = :updated_by,
                updated_at = NOW()
        """), {
            "role_name": role_name,
            "is_enabled": body.get('enabled'),
            "updated_by": current_user.email
        })
        
        await db.commit()
        
        role_display_name = "Financial" if "financial" in role_key else "Legal"
        status = "enabled" if new_value == 'true' else "disabled"
        
        return {
            "success": True,
            "message": f"{role_display_name} role {status} successfully"
        }
    except Exception as e:
        import traceback
        import datetime
        try:
            with open("last_error.txt", "a", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write(f"Time: {datetime.datetime.now()}\n")
                f.write(f"Endpoint: toggle_role (role_key={role_key})\n")
                f.write("-" * 80 + "\n")
                f.write(traceback.format_exc())
                f.write("\n\n")
        except Exception as log_err:
            logger.warning(f"[ADMIN] Failed to write last_error.txt debug log: {log_err}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle role: {str(e)}")


@router.get("/analytics/internal")
async def internal_workflow_analytics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get internal workflow analytics for different roles"""
    # Define roles that can access this
    ALLOWED_BASE_ROLES = ["MASTER_ADMIN", "OPERATION", "OPERATIONS", "COMPANY_ADMIN"]
    
    user_role_val = getattr(current_user.role, "value", str(current_user.role)).upper()
    # Handle enum names like 'UserRole.MASTER_ADMIN' -> 'MASTER_ADMIN'
    if "." in user_role_val:
        user_role_val = user_role_val.split(".")[-1]
        
    if user_role_val not in ALLOWED_BASE_ROLES and not is_developer(current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    from app.models import Subscription, PurchaseOrder, BusinessRequest, CreditReport
    from sqlalchemy import func

    # Subscriptions counts by status
    sub_stmt = select(Subscription.status, func.count(Subscription.id)).group_by(Subscription.status)
    sub_res = await db.execute(sub_stmt)
    sub_counts = {status: count for status, count in sub_res.all()}

    # PO counts by status
    po_stmt = select(PurchaseOrder.status, func.count(PurchaseOrder.id)).group_by(PurchaseOrder.status)
    po_res = await db.execute(po_stmt)
    po_counts = {status: count for status, count in po_res.all()}

    # Legal: Business Requests by status
    br_stmt = select(BusinessRequest.status, func.count(BusinessRequest.id)).group_by(BusinessRequest.status)
    br_res = await db.execute(br_stmt)
    br_counts = {status: count for status, count in br_res.all()}

    # Legal: GSTIN Reports (CreditReport) by status
    gr_stmt = select(CreditReport.status, func.count(CreditReport.id)).group_by(CreditReport.status)
    gr_res = await db.execute(gr_stmt)
    gr_counts = {status: count for status, count in gr_res.all()}

    return ResponseFormatter.create_success(data={
        "subscriptions": {
            "pending_verification": sub_counts.get("PENDING", 0),
            "pending_processing": sub_counts.get("VERIFIED", 0),
            "pending_approval": sub_counts.get("PROCESSED", 0),
            "total_active": sub_counts.get("APPROVED", 0),
        },
        "purchase_orders": {
            "pending_approval": po_counts.get("PENDING_APPROVAL", 0),
            "total_verified": po_counts.get("VERIFIED", 0),
        },
        "legal": {
            "pending_business_requests": br_counts.get("PENDING", 0),
            "completed_business_requests": br_counts.get("COMPLETED", 0),
            "pending_gstin_reports": gr_counts.get("Requested", 0),
            "completed_gstin_reports": gr_counts.get("Ready", 0),
        }
    })


# ============ ACTIVITY LOGS ============
@router.get("/activity-logs")
async def get_activity_logs(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    try:
        company_id = str(getattr(current_user, 'company_id', ''))
        # Try user_activity_logs first, then activity_logs, then audit_logs
        try:
            result = await db.execute(text("""
                SELECT 
                    al.id,
                    al.user_id,
                    COALESCE(u.name, u.email, 'Unknown') as user_name,
                    u.email as user_email,
                    u.role as user_role,
                    al.action,
                    al.details as description,
                    al.created_at,
                    al.ip_address
                FROM user_activity_logs al
                LEFT JOIN users u ON u.id = al.user_id
                WHERE u.company_id = :cid
                ORDER BY al.created_at DESC
                LIMIT 100
            """), {"cid": company_id})
        except Exception:
            try:
                result = await db.execute(text("""
                    SELECT 
                        al.id,
                        al.user_id,
                        COALESCE(u.name, u.email, 'Unknown') as user_name,
                        u.email as user_email,
                        u.role as user_role,
                        al.action,
                        al.description,
                        al.created_at
                    FROM activity_logs al
                    LEFT JOIN users u ON u.id = al.user_id
                    WHERE u.company_id = :cid
                    ORDER BY al.created_at DESC
                    LIMIT 100
                """), {"cid": company_id})
            except Exception:
                # Fallback to audit_logs which has po_number and vendor_name
                result = await db.execute(text("""
                    SELECT 
                        al.id,
                        al.user_id,
                        COALESCE(u.name, u.email, 'Unknown') as user_name,
                        u.email as user_email,
                        u.role as user_role,
                        al.action,
                        al.reason as description,
                        al.po_number,
                        al.vendor_name,
                        al.created_at
                    FROM audit_logs al
                    LEFT JOIN users u ON u.id = al.user_id
                    WHERE u.company_id = :cid
                    ORDER BY al.created_at DESC
                    LIMIT 100
                """), {"cid": company_id})
        logs = []
        for r in result.fetchall():
            log = dict(r._mapping)
            if log.get('created_at'):
                ts = log['created_at']
                log['created_at'] = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
            logs.append(log)
        return {"success": True, "data": logs, "total": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ PO REMINDER CONFIG ============

@router.get("/po-reminders")
async def get_po_reminder_config(
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get PO reminder configuration (admin only)"""
    from app.models import POReminderConfig
    stmt = select(POReminderConfig)
    result = await db.execute(stmt)
    config = result.scalars().first()
    if not config:
        config = POReminderConfig(
            id=str(uuid.uuid4()),
            before_days=[7, 3, 1],
            after_due_daily_enabled=True
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
    return ResponseFormatter.create_success(data={
        "id": config.id,
        "before_days": config.before_days,
        "after_due_daily_enabled": config.after_due_daily_enabled,
        "reminder_subject": config.reminder_subject or "Payment Reminder: PO {po_number} - {vendor_name}",
        "reminder_body": config.reminder_body or "Dear {vendor_name},\n\nThis is a reminder that PO {po_number} for the amount of ₹{amount} is due on {due_date}.\n\nPlease ensure payment is processed on time.\n\nRegards,\nTeam CreditWatch"
    })


@router.put("/po-reminders")
async def update_po_reminder_config(
    req: POReminderConfigUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update PO reminder configuration (admin only)"""
    from app.models import POReminderConfig
    stmt = select(POReminderConfig)
    result = await db.execute(stmt)
    config = result.scalars().first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    if req.before_days is not None:
        config.before_days = req.before_days
    if req.after_due_daily_enabled is not None:
        config.after_due_daily_enabled = req.after_due_daily_enabled
    if req.reminder_subject is not None:
        config.reminder_subject = req.reminder_subject
    if req.reminder_body is not None:
        config.reminder_body = req.reminder_body
    
    await log_audit(db, admin, "PO_REMINDER_CONFIG_UPDATE", reason="Updated PO reminder configuration", new_data=req.model_dump(exclude_unset=True))
    await db.commit()
    return ResponseFormatter.create_success(message="PO reminder config updated")