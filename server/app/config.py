"""
Environment configuration and settings
"""
from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path
from dotenv import load_dotenv
import os

# Ensure environment variables load correctly regardless of current working directory.
# Prefer server/.env, then fall back to project root .env if present.
_server_env = Path(__file__).resolve().parent.parent / ".env"
if _server_env.exists():
    load_dotenv(dotenv_path=str(_server_env), override=True)
else:
    load_dotenv(override=True)


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # Developer / superuser accounts that bypass normal role checks.
    # SECURITY: keep this out of source code — set via DEVELOPER_EMAILS in .env,
    # comma-separated. Prefer assigning MASTER_ADMIN role in the database instead
    # of relying on this list wherever possible.
    DEVELOPER_EMAILS: List[str] = []
    # SECURITY: set a real, unique password via .env in any shared/production
    # environment. This default only exists so local dev works out of the box.
    DEV_ADMIN_PASSWORD: str = "AdminPass123!"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/creditdatawatch"

    # Redis
    # Default local Redis instance; can be overridden via REDIS_URL in .env
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Cookie settings
    COOKIE_DOMAIN: str | None = None
    COOKIE_PATH: str = "/"
    COOKIE_SECURE: bool = False  # Set to True in production with HTTPS
    COOKIE_HTTPONLY: bool = True
    COOKIE_SAMESITE: str = "lax"

    # Google SMTP (Email) - Using SMTP_SSL on port 465
    GOOGLE_SMTP_HOST: str = "smtp.gmail.com"
    GOOGLE_SMTP_PORT: int = 465  # SMTP_SSL port (NOT 587 for starttls)
    GOOGLE_SMTP_USER: str = ""
    GOOGLE_SMTP_PASSWORD: str = ""  # Gmail App Password (not regular password)
    SENDER_EMAIL: str = "no-reply@creditdatawatch.com"
    SENDER_NAME: str = "CreditDataWatch"

    # Brevo / Sendinblue (HTTPS email API — used instead of raw SMTP
    # because most hosts, including Render's free/starter plans, block
    # outbound SMTP ports to prevent spam abuse. Get a free API key at
    # https://brevo.com, then verify a Sender email address under
    # Settings > Senders, Domains & Dedicated IPs — no custom domain
    # needed for a verified single sender.)
    BREVO_API_KEY: str = ""
    BREVO_FROM_EMAIL: str = ""  # must be the exact email you verified in Brevo; falls back to SENDER_EMAIL if unset

    # Legacy SendGrid/Resend settings — no longer used by email_service.py,
    # kept only so old env vars don't cause a startup validation error.
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = ""
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = ""

    # Main SMTP Config (for general use)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "noreply@creditdata.watch"




    SMTP_TIMEOUT: int = 30  # Connection timeout in seconds

    # Google Drive OAuth2
    GOOGLE_CLIENT_CREDENTIALS_FILE: str = "server/credentials/client-credentials.json"
    GOOGLE_CLIENT_CREDENTIALS_JSON: str = ""  # raw OAuth client JSON content, Render-friendly equivalent of the file above
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "server/credentials/service-account.json"
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""  # raw JSON key content, for platforms (e.g. Render) where writing a secret file to disk isn't reliable
    GOOGLE_OAUTH_TOKEN_JSON: str = ""  # raw personal-account OAuth token JSON, obtained once via GET /api/v1/drive/auth-url — see get_service_account_credentials() for why this is preferred over the service account
    GOOGLE_FOLDER_ID: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/drive/callback"

    # Backblaze B2 (S3-compatible object storage) — preferred over Google
    # Drive for uploaded files. Unlike the Drive OAuth flow above, B2 auth
    # is a static Application Key ID + Application Key, so there's no
    # "Testing mode" OAuth consent screen and no 7-day refresh-token
    # expiry silently breaking already-shared links (see drive_service.py
    # SCOPES comment for the full explanation of that Drive-side issue).
    # The bucket is kept Private (no Backblaze payment method required)
    # and files are served through /api/v1/files/b2/{key}, which mints a
    # fresh presigned URL on every request — see b2_service.py.
    # All four must be set for B2 to be used; file_storage_service.py
    # falls back to Drive, then local disk, if any are missing.
    B2_APPLICATION_KEY_ID: str = ""
    B2_APPLICATION_KEY: str = ""
    B2_BUCKET_NAME: str = ""
    # S3-compatible endpoint for your bucket's region, e.g.
    # "https://s3.us-west-004.backblazeb2.com" — shown on the bucket's
    # page in the B2 dashboard under "Endpoint".
    B2_ENDPOINT_URL: str = ""

    # OTP (Twilio - optional, can use stub)
    OTP_PROVIDER: str = "smtp"  # or "twilio" or "mock"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    OTP_EXPIRY_MINUTES: int = 10

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
        "http://localhost:3002", "http://127.0.0.1:3002",
        "http://localhost:3003", "http://127.0.0.1:3003",
        "http://localhost:3004", "http://127.0.0.1:3004",
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:8080", "http://127.0.0.1:8080",
        "http://localhost:8082", "http://127.0.0.1:8082",
    ]
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "0.0.0.0", "localhost:8000", "127.0.0.1:8000"]

    # Logging
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    # Frontend URL for building links in emails
    FRONTEND_URL: str = "http://localhost:3001"
    BASE_URL: str = "http://localhost:8000"
    # The real UPI ID customers pay subscription fees to — shown on the
    # Membership payment QR code page. Was previously hardcoded as the
    # literal placeholder "YOUR_UPI_ID_HERE" in payment_service.py, so
    # every payment QR code pointed nowhere real until this is set.
    UPI_ID: str = "YOUR_UPI_ID_HERE"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ENABLE_SCHEDULER: bool = True
    # Shared secret required by GET/POST /api/v1/cron/run-daily-tasks —
    # lets an external cron service (e.g. cron-job.org, free) trigger
    # the daily reminder/notification run reliably even if Render's
    # free/starter web service tier has spun the process down from
    # inactivity, since the in-process asyncio scheduler alone stops
    # running whenever the service is asleep. Leave blank to disable
    # this endpoint entirely (it 404s instead of running unauthenticated).
    CRON_SECRET: str = ""
    # When true, ErrorHandlerMiddleware re-raises unhandled exceptions
    # instead of returning a clean JSON 500. That's useful for local
    # debugging (full traceback in the terminal), but dangerous as a
    # production default: a re-raised exception propagates past
    # CORSMiddleware without it getting a chance to attach
    # Access-Control-Allow-Origin headers, so the browser reports a
    # misleading "blocked by CORS policy" error instead of showing the
    # real 500 — turning every future unhandled backend bug into a
    # confusing "CORS is broken" report. Defaulting this to False means
    # production always gets a clean, properly-CORS'd JSON error (full
    # detail is still logged server-side via exc_info=True either way).
    # Set DEBUG_RAW_ERRORS=true in a local .env for verbose local debugging.
    DEBUG_RAW_ERRORS: bool = False

    # Admin Configuration (for seeding initial admin user)
    ADMIN_GSTIN: str = ""
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    ADMIN_COMPANY_NAME: str = ""
    ADMIN_PHONE: str = ""
    
    # Ollama LLM Configuration — kept for local development. On Render
    # (and any host without Ollama installed), the chat route below falls
    # back to the Groq API instead, which needs no local server and has
    # a free tier with no credit card required.
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    GROQ_API_KEY: str = ""

    # Zoho Invoice integration — see docs/zoho-integration-setup.md.
    # Lets an invoice created/updated in Zoho Invoice appear in
    # CreditDataWatch automatically via a webhook, instead of a manual
    # export-then-import step.
    ZOHO_CLIENT_ID: str = ""
    ZOHO_CLIENT_SECRET: str = ""
    ZOHO_REFRESH_TOKEN: str = ""
    ZOHO_ORGANIZATION_ID: str = ""
    # Change to https://accounts.zoho.in, .eu, .com.au etc. to match the
    # Zoho data center your account is in.
    ZOHO_ACCOUNTS_BASE_URL: str = "https://accounts.zoho.com"
    # Change to https://www.zohoapis.in/invoice/v3 etc. to match your DC.
    ZOHO_API_BASE_URL: str = "https://www.zohoapis.com/invoice/v3"
    # A random string you choose — put the same value in the webhook URL
    # you configure in Zoho, as ?secret=... . Stops random callers from
    # hitting the webhook endpoint.
    ZOHO_WEBHOOK_SECRET: str = ""
    # The CreditDataWatch account email that Zoho-synced invoices get
    # filed under.
    ZOHO_TARGET_USER_EMAIL: str = ""
    # How often (seconds) the background poller checks Zoho for new/
    # changed invoices. Used because Zoho's free plan has no webhooks —
    # see app/services/zoho_poll_service.py. Default: 15 minutes.
    ZOHO_POLL_INTERVAL_SECONDS: int = 900

    class Config:
        # Retain default for environments that run from server/ directory
        env_file = ".env"
        case_sensitive = True
        # IMPORTANT: without this, ANY unrecognized key in .env (e.g.
        # ALEMBIC_DATABASE_URL, which is only read by Alembic via alembic.ini,
        # not by this Settings class) crashes app startup entirely with a
        # pydantic "extra_forbidden" ValidationError. "ignore" makes Settings
        # tolerate — not silently misuse — variables meant for other tools.
        extra = "ignore"


settings = Settings()
