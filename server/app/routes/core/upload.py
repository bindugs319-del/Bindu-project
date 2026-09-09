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
        from app.services.file_storage_service import store_uploaded_file

        file_ext = file.filename.split(".")[-1]
        file_id = str(uuid.uuid4())
        filename = f"{file_id}.{file_ext}"
        file_bytes = await file.read()
        result = await store_uploaded_file(file_bytes, filename, file.content_type, "evidence")
        url = result["url"] if result["storage"] == "drive" else f"{settings.BASE_URL}{result['url']}"

        return ResponseFormatter.create_success(data={"url": url, "filename": file.filename})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


