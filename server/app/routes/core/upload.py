"""
Evidence upload endpoints.
"""
from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form
from typing import Annotated
from app.models import User, PurchaseOrder, DefaulterCase, CreditReport, Settlement, Company, BusinessRequest, CompanyCredibilityIndex
from app.utils import ResponseFormatter, format_phone_e164
from app.dependencies import get_current_user, require_role, require_master_admin, is_developer
from app.config import settings
import uuid
import shutil

from .common import *  # noqa: F401,F403 (logger + shared constants)

upload_router = APIRouter(prefix="/upload")

@upload_router.post("/evidence")
async def upload_evidence(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...)
):
    """Upload evidence file for PO edit"""
    try:
        from app.utils.uploads import get_upload_subdir
        upload_dir = get_upload_subdir("evidence")
        file_ext = file.filename.split(".")[-1]
        file_id = str(uuid.uuid4())
        file_path = upload_dir / f"{file_id}.{file_ext}"
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        url = f"{settings.BASE_URL}/uploads/evidence/{file_id}.{file_ext}"
        return ResponseFormatter.create_success(data={"url": url, "filename": file.filename})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


