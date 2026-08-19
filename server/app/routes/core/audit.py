"""
Audit log endpoints.
"""
from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text
from datetime import datetime, timezone
from app.database import get_db, engine
from app.models import User, PurchaseOrder, DefaulterCase, CreditReport, Settlement, Company, BusinessRequest, CompanyCredibilityIndex
from app.dependencies import get_current_user, require_role, require_master_admin, is_developer
from app.config import settings

from .common import *  # noqa: F401,F403 (logger + shared constants)

audit_router = APIRouter()

@audit_router.get("/audit-logs") 
async def get_audit_logs( 
    db: Annotated[AsyncSession, Depends(get_db)], 
    current_user: Annotated[User, Depends(get_current_user)], 
    action: str = None, 
    date_from: str = None, 
    search: str = None 
): 
    # Only admin roles can view 
    role = str(current_user.role).split('.')[-1] if '.' in str(current_user.role) else str(current_user.role)
    role = role.upper()
    allowed_roles = ["MASTER_ADMIN", "COMPANY_ADMIN", "ADMIN", "OPERATIONS", "OPERATION", "LEGAL", "FINANCIAL", "FINANCE"] 
    if role not in allowed_roles and not is_developer(current_user): 
        raise HTTPException(status_code=403, detail="Access denied. Admins only.") 
    
    from sqlalchemy import text 
    query = "SELECT * FROM audit_logs WHERE 1=1" 
    params = {} 
    
    if action and action.lower() != "all": 
        query += " AND action = :action" 
        params["action"] = action.upper() 
    
    if date_from: 
        try:
            from datetime import datetime
            # Convert string to datetime object for asyncpg/SQLAlchemy
            dt_val = datetime.fromisoformat(date_from)
            query += " AND created_at >= :date_from" 
            params["date_from"] = dt_val 
        except (ValueError, TypeError):
            pass
    
    if search: 
        # Detect SQLite vs PostgreSQL
        is_sqlite = settings.DATABASE_URL.startswith("sqlite")
        operator = "LIKE" if is_sqlite else "ILIKE"
        query += f" AND (po_number {operator} :search OR vendor_name {operator} :search OR user_email {operator} :search OR reason {operator} :search)" 
        params["search"] = f"%{search}%" 
    
    query += " ORDER BY created_at DESC LIMIT 500" 
    
    result = await db.execute(text(query), params) 
    rows = result.mappings().all() 
    
    logs = [dict(row) for row in rows] 
    # Convert datetime to string 
    for log in logs: 
        if log.get('created_at'): 
            log['created_at'] = str(log['created_at']) 
    
    return {"success": True, "data": logs, "total": len(logs)} 


