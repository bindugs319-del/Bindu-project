"""
Evidence upload endpoints.
"""
from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form
from typing import Annotated
from app.models import User, PurchaseOrder, DefaulterCase, CreditReport, Settlement, Company, BusinessRequest, CompanyCredibilityIndex
from app.utils import ResponseFormatter, format_phone_e164
from app.dependencies import get_current_user, require_role, require_master_admin, is_developer
from app.config import settings
from app.services.file_storage_service import store_uploaded_file
import uuid

from .common import *  # noqa: F401,F403 (logger + shared constants)

upload_router = APIRouter(prefix="/upload")

@upload_router.post("/evidence")
async def upload_evidence(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...)
):
    """Upload evidence file for PO edit"""
    try:
        file_ext = file.filename.split(".")[-1]
        file_id = str(uuid.uuid4())
        stored_name = f"{file_id}.{file_ext}"
        file_bytes = await file.read()

        # store_uploaded_file() tries Google Drive first and only falls
        # back to local disk if Drive isn't configured — local disk on
        # Render is wiped on every deploy/restart, which was silently
        # losing every evidence upload the day after it was uploaded.
        result = await store_uploaded_file(
            file_bytes=file_bytes,
            filename=stored_name,
            mime_type=file.content_type,
            subfolder="evidence",
        )
        url = result["url"]
        if result["storage"] == "local":
            url = f"{settings.BASE_URL}{url}"

        return ResponseFormatter.create_success(data={"url": url, "filename": file.filename})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


