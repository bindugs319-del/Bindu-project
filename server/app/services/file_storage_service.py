"""
Single entry point every upload endpoint should use to save an uploaded
file. Tries Google Drive first (via a service account — no per-user login
needed), and only falls back to local disk if Drive isn't configured.

Why this exists: local disk on Render (and most PaaS free/starter tiers)
is ephemeral — anything written to it is wiped on the next deploy or
restart. Files uploaded to Drive instead persist regardless of how often
the app redeploys. Local disk remains the fallback so nothing breaks in a
dev environment where Drive credentials haven't been set up.
"""
import io
import logging
from typing import Optional

from app.services.drive_service import DriveService
from app.exceptions import DriveAccessDenied
from app.config import settings

logger = logging.getLogger(__name__)


def drive_storage_available() -> bool:
    try:
        DriveService.get_service_account_credentials()
        return True
    except DriveAccessDenied:
        return False
    except Exception:
        return False


async def store_uploaded_file(file_bytes: bytes, filename: str, mime_type: str, subfolder: str) -> dict:
    """
    Saves an uploaded file and returns {"url": ..., "storage": "drive" | "local"}.

    - "drive": `url` is a public (anyone-with-the-link) Google Drive view
      link. Persists across redeploys.
    - "local": `url` is the existing `/uploads/<subfolder>/<filename>`
      relative path served by the app's own StaticFiles mount. Does NOT
      persist across a Render redeploy without a Persistent Disk — this
      path only exists so local development keeps working without any
      Drive setup.
    """
    try:
        credentials = DriveService.get_service_account_credentials()
        file_obj = io.BytesIO(file_bytes)
        # Group uploads by type in Drive too, mirroring the local
        # subfolder structure, so the app's Drive account doesn't end up
        # with hundreds of unsorted files in one place.
        folder_id = await _get_or_create_subfolder(credentials, subfolder)
        result = await DriveService.upload_file(
            file_obj=file_obj,
            filename=filename,
            mime_type=mime_type or "application/octet-stream",
            credentials=credentials,
            folder_id=folder_id,
        )
        file_id = result.get("id")
        await DriveService.make_public(credentials, file_id)
        url = result.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"
        return {"url": url, "storage": "drive"}
    except Exception as e:
        logger.warning(f"Drive upload failed or not configured, falling back to local disk: {e}")

    # Fallback: local disk (existing behavior, unchanged)
    import asyncio
    from app.utils.uploads import get_upload_subdir
    upload_dir = get_upload_subdir(subfolder)
    filepath = upload_dir / filename

    # Plain (blocking) open()/write() here would stall the whole event
    # loop while waiting on disk I/O — asyncio.to_thread() runs it on a
    # worker thread instead, same fix as applied to email_service.py.
    def _write_file_bytes(path, data: bytes) -> None:
        with open(path, "wb") as f:
            f.write(data)

    await asyncio.to_thread(_write_file_bytes, filepath, file_bytes)
    return {"url": f"/uploads/{subfolder}/{filename}", "storage": "local"}


# Cache subfolder IDs for the lifetime of the process so we don't call
# Drive's API to look up/create the same folder on every single upload.
_subfolder_cache: dict = {}


async def _get_or_create_subfolder(credentials, subfolder: str) -> Optional[str]:
    if subfolder in _subfolder_cache:
        return _subfolder_cache[subfolder]

    from googleapiclient.discovery import build
    service = build("drive", "v3", credentials=credentials)
    parent = settings.GOOGLE_FOLDER_ID or None

    query = f"name = '{subfolder}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent:
        query += f" and '{parent}' in parents"

    results = service.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
    existing = results.get("files", [])
    if existing:
        folder_id = existing[0]["id"]
    else:
        metadata = {"name": subfolder, "mimeType": "application/vnd.google-apps.folder"}
        if parent:
            metadata["parents"] = [parent]
        folder = service.files().create(body=metadata, fields="id").execute()
        folder_id = folder.get("id")

    _subfolder_cache[subfolder] = folder_id
    return folder_id
