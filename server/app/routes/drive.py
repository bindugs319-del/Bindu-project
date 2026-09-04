"""
Google Drive routes
"""
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services import DriveService
from app.exceptions import DriveAccessDenied
from app.utils import ResponseFormatter
from app.dependencies import get_current_user
from app.models import User
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/auth-url")
async def get_drive_auth_url(http_request: Request = None):
    """Get Google Drive OAuth2 authorization URL"""
    try:
        auth_url = DriveService.get_authorization_url()
        request_id = http_request.state.request_id if http_request else ""
        return ResponseFormatter.create_success(
            data={"auth_url": auth_url},
            message="Authorization URL generated",
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Error getting auth URL: {str(e)}")
        raise


@router.post("/callback")
async def drive_oauth_callback(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)], code: str, state: str, http_request: Request = None):
    """Handle OAuth2 callback from Google Drive"""
    try:

        request_id = http_request.state.request_id if http_request else ""
        return ResponseFormatter.create_success(
            message="Drive connected successfully",
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Error in OAuth callback: {str(e)}")
        raise


@router.get("/status")
async def get_drive_status(current_user: Annotated[User, Depends(get_current_user)], http_request: Request = None):
    """Live diagnostic for whether uploads are actually persisting to
    Drive right now, or silently falling back to Render's non-persistent
    local disk. Deliberately does a real API call rather than just
    checking whether an env var is set — a malformed key, a Drive API
    that hasn't been enabled on the Google Cloud project, or expired
    creds all still "have a value set" but fail at upload time, and
    that's exactly the failure mode this exists to catch without digging
    through server logs."""
    from googleapiclient.discovery import build

    request_id = http_request.state.request_id if http_request else ""
    working = False
    detail = None
    try:
        credentials = DriveService.get_service_account_credentials()
        service = build("drive", "v3", credentials=credentials)
        about = service.about().get(fields="user").execute()
        working = True
        detail = f"Connected as {about.get('user', {}).get('emailAddress', 'the configured service account')}"
    except Exception as e:
        detail = str(e)

    return ResponseFormatter.create_success(
        data={
            "working": working,
            "detail": detail,
            # Surfaced here too since a stale BASE_URL is the other half
            # of "uploads look fine right after but the link 404s later"
            # — this makes both checkable from one request.
            "base_url": settings.BASE_URL,
        },
        request_id=request_id,
    )


@router.get("/files")
async def list_drive_files(current_user: Annotated[User, Depends(get_current_user)], http_request: Request = None):
    """List files from Google Drive"""
    try:
        # Placeholder until Drive credential storage is wired
        files = [
            {"id": "1", "name": "Sample Document 1", "mimeType": "application/pdf", "modifiedTime": "2026-01-04"},
            {"id": "2", "name": "Sample Document 2", "mimeType": "application/pdf", "modifiedTime": "2026-01-03"},
        ]

        request_id = http_request.state.request_id if http_request else ""
        return ResponseFormatter.create_success(
            data={"files": files},
            request_id=request_id
        )
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise


@router.post("/upload")
async def upload_file(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    folder_id: str = Form(None),
    http_request: Request = None
):
    """Upload file to Google Drive (System Account), falling back to local
    storage when Drive credentials aren't configured — keeps features like
    defaulter case filing (Ledger/CA Certificate uploads) working out of
    the box in local/dev setups that haven't run the Drive OAuth setup."""
    try:
        creds = DriveService.get_service_account_credentials()
        target_folder_id = folder_id or settings.GOOGLE_FOLDER_ID
        result = await DriveService.upload_file(
            file_obj=file.file,
            filename=file.filename,
            mime_type=file.content_type,
            credentials=creds,
            folder_id=target_folder_id
        )

        request_id = http_request.state.request_id if http_request else ""
        return ResponseFormatter.create_success(
            data=result,
            message="File uploaded successfully",
            request_id=request_id
        )
    except DriveAccessDenied as e:
        logger.warning(f"Drive not configured ({e}) — falling back to local storage")
        try:
            import uuid
            from app.utils.uploads import get_upload_subdir

            upload_dir = get_upload_subdir("drive_fallback")
            file_ext = (file.filename or "").rsplit(".", 1)[-1] if "." in (file.filename or "") else ""
            file_id = str(uuid.uuid4())
            stored_name = f"{file_id}.{file_ext}" if file_ext else file_id
            file_path = upload_dir / stored_name

            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())

            url = f"{settings.BASE_URL}/uploads/drive_fallback/{stored_name}"
            result = {"id": file_id, "webViewLink": url, "webContentLink": url}

            request_id = http_request.state.request_id if http_request else ""
            return ResponseFormatter.create_success(
                data=result,
                message="File uploaded successfully (stored locally — Google Drive not configured)",
                request_id=request_id
            )
        except Exception as fallback_err:
            logger.error(f"Local storage fallback also failed: {fallback_err}")
            raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise
