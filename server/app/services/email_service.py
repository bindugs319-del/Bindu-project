import base64
import logging
from email.utils import parseaddr

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class EmailService:
    """
    Sends email via Brevo's HTTPS API (https://brevo.com, formerly Sendinblue).

    We use an HTTPS email API rather than raw SMTP because most PaaS
    hosts — including Render's free/starter plans — block outbound SMTP
    ports (25/465/587) to prevent spam abuse; that connection attempt
    fails with `[Errno 101] Network is unreachable`. HTTPS APIs like
    this one are never blocked that way.

    We use Brevo specifically because, like SendGrid, it supports
    verifying a SINGLE sender email address (Settings > Senders) rather
    than requiring a whole custom domain — useful for small projects
    that don't own a domain. We ended up here instead of SendGrid
    because SendGrid's own signup flow was blocking new accounts
    (ERR_USER_FORBIDDEN_ACCESS) for this project's network/region.

    Function names/signatures are kept the same as before so nothing
    else in the codebase (otp_service, invitations, etc.) needs to change.
    """

    def __init__(self):
        self.api_key = settings.BREVO_API_KEY
        self.sender_email = (
            settings.BREVO_FROM_EMAIL
            or settings.SENDER_EMAIL
            or settings.GOOGLE_SMTP_USER
        )
        self.sender_name = getattr(settings, "SENDER_NAME", "CreditDataWatch")
        _, addr_only = parseaddr(self.sender_email or "")
        self.from_addr = addr_only or self.sender_email
        self.timeout = getattr(settings, "SMTP_TIMEOUT", 30)

    def _looks_like_placeholder(self) -> bool:
        """Detect obviously-unconfigured/placeholder Brevo credentials."""
        placeholder_keys = {"", "your_brevo_api_key", "xkeysib-xxxxxxxx"}
        key = (self.api_key or "").strip()
        return key.lower() in placeholder_keys

    async def _post_to_brevo(self, payload: dict) -> bool:
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(BREVO_API_URL, headers=headers, json=payload)
        if resp.status_code >= 400:
            logger.error(f"[BREVO ERROR] {resp.status_code}: {resp.text}")
            raise RuntimeError(f"Brevo API error {resp.status_code}: {resp.text}")
        logger.info(f"[BREVO] Sent OK -> {payload.get('to')}")
        return True

    def _base_payload(self, to_email: str, subject: str) -> dict:
        return {
            "sender": {"name": self.sender_name, "email": self.from_addr},
            "to": [{"email": to_email}],
            "subject": subject,
        }

    async def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send a plain-text email. Returns True if actually sent, False if
        mock-skipped (no real Brevo API key configured). Raises on a
        genuine send failure so callers can tell "not configured" apart
        from "tried and failed"."""
        if self._looks_like_placeholder():
            logger.warning("BREVO_API_KEY not configured, skipping email (mock).")
            print(f"[MOCK EMAIL] To: {to_email} | Subject: {subject} | Body: {body[:50]}...")
            return False

        payload = self._base_payload(to_email, subject)
        payload["textContent"] = body
        try:
            return await self._post_to_brevo(payload)
        except Exception as e:
            logger.error(f"Email FAILED: {e}")
            raise

    async def send_email_html(self, to_email: str, subject: str, html: str, text_fallback: str | None = None):
        """Send an HTML email with optional text fallback."""
        if self._looks_like_placeholder():
            logger.warning("BREVO_API_KEY not configured, skipping email (mock).")
            print(f"[MOCK HTML EMAIL] To: {to_email} | Subject: {subject}")
            return False

        payload = self._base_payload(to_email, subject)
        payload["htmlContent"] = html
        if text_fallback:
            payload["textContent"] = text_fallback
        try:
            return await self._post_to_brevo(payload)
        except Exception as e:
            logger.error(f"Email FAILED: {e}")
            raise

    @staticmethod
    async def send_registration_email(to_email: str, company_name: str, phone: str) -> None:
        """Send welcome email after registration. Does not raise; logs on failure."""
        try:
            subject = "Welcome to CreditDataWatch"
            body = (
                f"Hello,\n\n"
                f"Thank you for registering with CreditDataWatch.\n\n"
                f"Company: {company_name}\n"
                f"Phone: {phone}\n\n"
                f"You can now log in and use the platform.\n\n"
                f"Thank you!"
            )
            svc = EmailService()
            await svc.send_email(to_email, subject, body)
        except Exception as e:
            logger.warning("Registration email failed (registration still succeeds): %s", e)

    @staticmethod
    async def send_invitation_email(to_email: str, company_name: str, role: str, token: str, expires_at: str) -> None:
        """Send invitation email with acceptance link. Does not raise; logs on failure."""
        try:
            frontend_base = getattr(settings, "FRONTEND_URL", "") or "http://localhost:3001"
            invite_link = f"{frontend_base.rstrip('/')}/accept-invite?token={token}"
            subject = f"You're invited to join {company_name}"
            text_fallback = (
                f"You're invited to join {company_name}\n"
                f"Role: {role}\n"
                f"Expires At: {expires_at}\n\n"
                f"Accept Invitation: {invite_link}\n"
                f"If you did not expect this email, please ignore it."
            )
            html = f"""
              <h2>You're Invited!</h2>
              <p>You have been invited to join <b>{company_name}</b>.</p>
              <p><b>Role:</b> {role}</p>
              <p><b>Expires At:</b> {expires_at}</p>
              <br/>
              <a href="{invite_link}"
                 style="padding:10px 16px;background:#2563eb;color:white;text-decoration:none;border-radius:6px;">
                 Accept Invitation
              </a>
              <br/><br/>
              <p>If you did not expect this email, please ignore it.</p>
            """
            svc = EmailService()
            await svc.send_email_html(to_email, subject, html, text_fallback=text_fallback)
        except Exception as e:
            logger.warning("Invitation email failed (invitation still valid): %s", e)


async def send_email(to_email: str, subject: str, body: str):
    """Standalone wrapper for EmailService.send_email"""
    svc = EmailService()
    return await svc.send_email(to_email, subject, body)


async def send_email_with_attachment(
    to_email: str,
    subject: str,
    body: str,
    attachment_path: str = None,
    attachment_name: str = "Legal_Notice.pdf"
):
    import os
    import asyncio

    svc = EmailService()

    if svc._looks_like_placeholder():
        print(f"[MOCK ATTACHMENT EMAIL] To: {to_email} | Subject: {subject} | Attachment: {attachment_name}")
        return False

    payload = svc._base_payload(to_email, subject)
    payload["textContent"] = body

    if attachment_path and os.path.exists(attachment_path):
        # Reading the file with the plain (blocking) open() here would
        # block the whole event loop while it waits on disk I/O, which is
        # a real problem in an async server handling concurrent requests.
        # asyncio.to_thread() runs it on a worker thread instead, keeping
        # this coroutine non-blocking without adding a new dependency
        # (e.g. aiofiles) for what's normally a small, occasional read.
        def _read_file_bytes(path: str) -> bytes:
            with open(path, "rb") as f:
                return f.read()

        file_bytes = await asyncio.to_thread(_read_file_bytes, attachment_path)
        payload["attachment"] = [{
            "name": attachment_name,
            "content": base64.b64encode(file_bytes).decode("ascii"),
        }]
        print(f"[EMAIL] Attaching PDF: {attachment_name}")
    else:
        print(f"[EMAIL] No attachment found at: {attachment_path}")

    try:
        return await svc._post_to_brevo(payload)
    except Exception as e:
        print(f"[EMAIL] Failed to send email with attachment: {str(e)}")
        return False
