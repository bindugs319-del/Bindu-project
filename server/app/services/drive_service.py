"""
Google Drive service for OAuth2 and file management
"""
from typing import Optional
import os
import json
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.config import settings
from app.exceptions import DriveAccessDenied

logger = logging.getLogger(__name__)

# Scopes for Drive access
SCOPES = ["https://www.googleapis.com/auth/drive"]


class DriveService:
    """Google Drive OAuth2 and file management"""

    @staticmethod
    def get_oauth2_flow() -> Flow:
        """
        Create OAuth2 flow for Google Drive using client credentials —
        from a raw JSON env var first (GOOGLE_CLIENT_CREDENTIALS_JSON,
        for Render — see get_service_account_credentials for why),
        falling back to a local file for dev environments where writing
        one is easy.

        Returns:
            OAuth2 Flow object
        """
        if settings.GOOGLE_CLIENT_CREDENTIALS_JSON:
            try:
                info = json.loads(settings.GOOGLE_CLIENT_CREDENTIALS_JSON)
                flow = Flow.from_client_config(info, scopes=SCOPES)
                flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
                return flow
            except Exception as e:
                logger.error(f"Failed to parse GOOGLE_CLIENT_CREDENTIALS_JSON: {e}")

        if not os.path.exists(settings.GOOGLE_CLIENT_CREDENTIALS_FILE):
            raise DriveAccessDenied("Client credentials file not found")
        
        flow = Flow.from_client_secrets_file(
            settings.GOOGLE_CLIENT_CREDENTIALS_FILE,
            scopes=SCOPES,
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        return flow

    @staticmethod
    def get_service_account_credentials() -> Credentials:
        """
        Get credentials from (in priority order): a personal OAuth token
        env var, a raw service-account JSON env var, a service account
        file, or token.json (per-user OAuth from a local file).

        Personal OAuth is checked FIRST because it's the only option with
        real Drive storage quota — a plain Google service account has
        ZERO storage quota of its own (a Google policy, not something
        fixable via folder sharing) and can only write into a Shared
        Drive, which requires paid Google Workspace. For a free personal
        Google account, authorizing as yourself (GOOGLE_OAUTH_TOKEN_JSON,
        obtained via GET /api/v1/drive/auth-url) is what actually makes
        uploads persist.

        The env var checks come first specifically for platforms like
        Render, where a file written to disk at runtime (or even a
        "Secret File" in some configurations) isn't guaranteed to survive
        every deploy — pasting JSON content directly into an environment
        variable sidesteps that entirely.
        """
        from google.oauth2 import service_account
        from google.oauth2.credentials import Credentials as UserCredentials

        # 1. Try a personal OAuth token from an environment variable —
        # see docstring above for why this is checked first.
        if settings.GOOGLE_OAUTH_TOKEN_JSON:
            try:
                info = json.loads(settings.GOOGLE_OAUTH_TOKEN_JSON)
                creds = UserCredentials.from_authorized_user_info(info, SCOPES)
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                return creds
            except Exception as e:
                logger.error(f"Failed to parse/refresh GOOGLE_OAUTH_TOKEN_JSON: {e}")

        # 2. Try raw service-account JSON from an environment variable
        if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            try:
                info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
                return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            except Exception as e:
                logger.error(f"Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON: {e}")

        # 3. Try Service Account file
        if os.path.exists(settings.GOOGLE_SERVICE_ACCOUNT_FILE):
             return service_account.Credentials.from_service_account_file(
                settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
            )
            
        # 4. Try User Token (OAuth) from a local file — dev-environment fallback
        token_path = os.path.join(os.path.dirname(settings.GOOGLE_CLIENT_CREDENTIALS_FILE), 'token.json')
        if os.path.exists(token_path):
            try:
                with open(token_path, 'r') as token:
                    info = json.load(token)
                    return UserCredentials.from_authorized_user_info(info, SCOPES)
            except Exception as e:
                logger.error(f"Failed to load token.json: {e}")
        
        # 5. Fail
        logger.warning(f"No valid credentials found (checked GOOGLE_OAUTH_TOKEN_JSON, GOOGLE_SERVICE_ACCOUNT_JSON, service-account.json, and token.json)")
        raise DriveAccessDenied("Google Drive credentials not configured. Please run 'python authorize_drive.py' or add service-account.json.")

    @staticmethod
    def get_authorization_url() -> str:
        """
        Get OAuth2 authorization URL
        
        Returns:
            Authorization URL
        """
        flow = DriveService.get_oauth2_flow()
        # access_type='offline' is what makes Google issue a refresh_token
        # alongside the short-lived access token — without it, this would
        # stop working again in about an hour. prompt='consent' forces
        # Google to reissue one on every authorization, even for an
        # account that's approved this app before.
        auth_url, _state = flow.authorization_url(access_type="offline", prompt="consent")
        return auth_url

    @staticmethod
    async def get_credentials_from_code(code: str) -> Credentials:
        """
        Exchange authorization code for credentials
        
        Args:
            code: Authorization code from OAuth2 callback
            
        Returns:
            Credentials object
        """
        try:
            flow = DriveService.get_oauth2_flow()
            flow.fetch_token(code=code)
            return flow.credentials
        except Exception as e:
            logger.error(f"Failed to get credentials: {str(e)}")
            raise DriveAccessDenied(str(e))

    @staticmethod
    def save_credentials(credentials: Credentials) -> str:
        """
        Save credentials as JSON string for storage
        
        Args:
            credentials: Credentials object
            
        Returns:
            JSON string of credentials
        """
        return credentials.to_json()

    @staticmethod
    def load_credentials(credentials_json: str) -> Credentials:
        """
        Load credentials from JSON string
        
        Args:
            credentials_json: JSON string of credentials
            
        Returns:
            Credentials object
        """
        return Credentials.from_authorized_user_info(json.loads(credentials_json), SCOPES)

    @staticmethod
    async def list_files(credentials_json: str, folder_id: Optional[str] = None) -> list:
        """
        List files in Drive or specific folder
        
        Args:
            credentials_json: Credentials JSON string (required)
            folder_id: Folder ID (optional)
            
        Returns:
            List of files
        """
        try:
            credentials = DriveService.load_credentials(credentials_json)
            service = build("drive", "v3", credentials=credentials)
            
            query = "'trashed'=false"
            if folder_id:
                query += f" and '{folder_id}' in parents"
            
            results = (
                service.files()
                .list(
                    q=query,
                    pageSize=100,
                    fields="files(id, name, mimeType, createdTime, modifiedTime, size)",
                    orderBy="modifiedTime desc",
                )
                .execute()
            )
            
            return results.get("files", [])
        except HttpError as e:
            logger.error(f"Drive API error: {str(e)}")
            raise DriveAccessDenied(str(e))

    @staticmethod
    async def create_folder(credentials_json: str, folder_name: str) -> str:
        """
        Create folder in Drive
        
        Args:
            credentials_json: Credentials JSON string (required)
            folder_name: Folder name
            
        Returns:
            Folder ID
        """
        try:
            credentials = DriveService.load_credentials(credentials_json)
            service = build("drive", "v3", credentials=credentials)
            
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            
            folder = service.files().create(body=file_metadata, fields="id").execute()
            return folder.get("id")
        except HttpError as e:
            logger.error(f"Failed to create folder: {str(e)}")
            raise DriveAccessDenied(str(e))

    @staticmethod
    async def get_file_download_url(credentials_json: str, file_id: str) -> str:
        """
        Get download URL for a file
        
        Args:
            credentials_json: Credentials JSON string (required)
            file_id: File ID
            
        Returns:
            Download URL
        """
        try:
            credentials = DriveService.load_credentials(credentials_json)
            service = build("drive", "v3", credentials=credentials)

            file = service.files().get(fileId=file_id, fields="webContentLink").execute()
            return file.get("webContentLink")
        except HttpError as e:
            logger.error(f"Failed to get download URL: {str(e)}")
            raise DriveAccessDenied(str(e))

    @staticmethod
    async def make_public(credentials, file_id: str) -> None:
        """
        Grants "anyone with the link can view" access to a file. Needed
        because a freshly uploaded file is private to the uploading
        account by default — without this, the webViewLink/webContentLink
        returned by upload_file() leads to a 403/login-required page for
        anyone else who opens it.
        """
        try:
            service = build("drive", "v3", credentials=credentials)
            service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
            ).execute()
        except HttpError as e:
            logger.error(f"Failed to set public permission on file {file_id}: {str(e)}")
            raise DriveAccessDenied(str(e))

    @staticmethod
    async def upload_file(file_obj, filename: str, mime_type: str, credentials, folder_id: Optional[str] = None) -> dict:
        """
        Upload file to Drive
        
        Args:
            file_obj: File-like object
            filename: Name of the file
            mime_type: MIME type of the file
            credentials: Credentials object
            folder_id: Optional folder ID to upload to
            
        Returns:
             Dict with 'id' and 'webViewLink'
        """
        try:
            from googleapiclient.http import MediaIoBaseUpload
            
            service = build("drive", "v3", credentials=credentials)
            
            file_metadata = {'name': filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]
                
            media = MediaIoBaseUpload(file_obj, mimetype=mime_type, resumable=True)
            
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, webContentLink'
            ).execute()
            
            return file
        except HttpError as e:
            logger.error(f"Failed to upload file: {str(e)}")
            raise DriveAccessDenied(str(e))
