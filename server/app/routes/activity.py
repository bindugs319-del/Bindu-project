from fastapi import APIRouter, Depends, HTTPException, Request 
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import text 
from app.database import get_db 
from app.dependencies import get_current_user, is_developer
from app.models import User

router = APIRouter() 

async def log_activity( 
    db: AsyncSession, 
    user_email: str, 
    user_id: str, 
    user_role: str, 
    action: str, 
    page: str = '', 
    entity_type: str = '', 
    entity_id: str = '', 
    details: str = '', 
    ip_address: str = '' 
): 
    try: 
        await db.execute(text(""" 
            INSERT INTO user_activity_logs 
            (user_id, user_email, user_role, action, page, entity_type, entity_id, details, ip_address) 
            VALUES (:uid, :email, :role, :action, :page, :etype, :eid, :details, :ip) 
        """), { 
            "uid": str(user_id), 
            "email": user_email, 
            "role": user_role, 
            "action": action, 
            "page": page, 
            "etype": entity_type, 
            "eid": str(entity_id), 
            "details": details, 
            "ip": ip_address 
        }) 
        await db.commit() 
    except Exception as e: 
        print(f"Activity log error: {e}") 

 
@router.post("/log") 
async def log_user_activity( 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request
): 
    try: 
        body = await request.json() 
        ip = request.client.host if request.client else '' 
        role_str = str(current_user.role).split('.')[-1] if '.' in str(current_user.role) else str(current_user.role)
        await log_activity( 
            db=db, 
            user_email=current_user.email, 
            user_id=str(current_user.id), 
            user_role=role_str, 
            action=body.get('action', ''), 
            page=body.get('page', ''), 
            entity_type=body.get('entity_type', ''), 
            entity_id=body.get('entity_id', ''), 
            details=body.get('details', ''), 
            ip_address=ip 
        ) 
        return {"success": True} 
    except Exception as e: 
        return {"success": False, "error": str(e)} 

 
@router.get("/logs") 
async def get_activity_logs( 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 200, 
    user_email: str = '', 
    action: str = '' 
): 
    role_str = str(current_user.role).split('.')[-1] if '.' in str(current_user.role) else str(current_user.role)
    allowed_roles = ['MASTER_ADMIN', 'OPERATION', 'OPERATIONS', 'LEGAL', 'FINANCIAL', 'FINANCE']
    role_str = role_str.upper()
    
    if role_str not in allowed_roles and not is_developer(current_user): 
        raise HTTPException(status_code=403, detail="Access denied") 

    filters = ["1=1"] 
    params = {"limit": limit} 

    if user_email: 
        filters.append("user_email ILIKE :email") 
        params["email"] = f"%{user_email}%" 
    if action: 
        filters.append("action = :action") 
        params["action"] = action 

    where = " AND ".join(filters) 
    try:
        result = await db.execute(text(f""" 
            SELECT * FROM user_activity_logs 
            WHERE {where} 
            ORDER BY timestamp DESC 
            LIMIT :limit 
        """), params) 

        rows = [dict(r._mapping) for r in result.fetchall()] 
        return {"success": True, "data": rows} 
    except Exception as e:
        return {"success": False, "error": str(e)}

 
@router.get("/logs/summary") 
async def get_activity_summary( 
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
): 
    if current_user.role != 'MASTER_ADMIN' and not is_developer(current_user): 
        raise HTTPException(status_code=403, detail="Access denied") 

    result = await db.execute(text(""" 
        SELECT 
            action, 
            COUNT(*) as count, 
            MAX(timestamp) as last_seen 
        FROM user_activity_logs 
        GROUP BY action 
        ORDER BY count DESC 
        LIMIT 20 
    """)) 
    rows = [dict(r._mapping) for r in result.fetchall()] 

    users_result = await db.execute(text(""" 
        SELECT 
            user_email, 
            user_role, 
            COUNT(*) as total_actions, 
            MAX(timestamp) as last_active 
        FROM user_activity_logs 
        GROUP BY user_email, user_role 
        ORDER BY total_actions DESC 
        LIMIT 10 
    """)) 
    users = [dict(r._mapping) for r in users_result.fetchall()]

    return {"success": True, "data": {"by_action": rows, "by_user": users}} 
