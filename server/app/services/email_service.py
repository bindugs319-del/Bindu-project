import base64
import logging
from email.utils import formataddr, parseaddr

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class EmailService:
    """
    Sends email via Resend's HTTPS API (https://resend.com).

    We switched away from raw SMTP because most PaaS hosts — including
    Render's free/starter plans — block outbound SMTP ports (25/465/587)
    to prevent spam abuse. That connection attempt fails with something
    like `[Errno 101] Network is unreachable`, even though the SMTP
    credentials themselves are correct. Resend (and similar providers)
    send over normal HTTPS, which is never blocked.

    Function names/signatures are kept the same as before so nothing
    else in the codebase (otp_service, invitations, etc.) needs to change.
    """

    def __init__(self):
        self.api_key = settings.RESEND_API_KEY
        self.sender_email = (
            settings.RESEND_FROM_EMAIL
            or settings.SENDER_EMAIL
            or settings.GOOGLE_SMTP_USER
        )
        self.sender_name = getattr(settings, "SENDER_NAME", "CreditDataWatch")
        # Build a unified, explicit From header (Name <email@domain>)
        _, addr_only = parseaddr(self.sender_email or "")
        base_addr = addr_only or self.sender_email
        self.from_header = formataddr((self.sender_name, base_addr))
        self.timeout = getattr(settings, "SMTP_TIMEOUT", 30)

    def _looks_like_placeholder(self) -> bool:
        """Detect obviously-unconfigured/placeholder Resend credentials."""
        placeholder_keys = {"", "your_resend_api_key", "re_xxxxxxxx"}
        key = (self.api_key or "").strip()
        return key.lower() in placeholder_keys

    async def _post_to_resend(self, payload: dict) -> bool:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(RESEND_API_URL, headers=headers, json=payload)
        if resp.status_code >= 400:
            logger.error(f"[RESEND ERROR] {resp.status_code}: {resp.text}")
            raise RuntimeError(f"Resend API error {resp.status_code}: {resp.text}")
        logger.info(f"[RESEND] Sent OK -> {payload.get('to')}")
        return True

    async def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send a plain-text email. Returns True if actually sent, False if
        mock-skipped (no real Resend API key configured). Raises on a genuine
        send failure so callers can tell "not configured" apart from
        "tried and failed"."""
        if self._looks_like_placeholder():
            logger.warning("RESEND_API_KEY not configured, skipping email (mock).")
            print(f"[MOCK EMAIL] To: {to_email} | Subject: {subject} | Body: {body[:50]}...")
            return False

        payload = {
            "from": self.from_header,
            "to": [to_email],
            "subject": subject,
            "text": body,
        }
        try:
            return await self._post_to_resend(payload)
        except Exception as e:
            logger.error(f"Email FAILED: {e}")
            raise

    async def send_email_html(self, to_email: str, subject: str, html: str, text_fallback: str | None = None):
        """Send an HTML email with optional text fallback."""
        if self._looks_like_placeholder():
            logger.warning("RESEND_API_KEY not configured, skipping email (mock).")
            print(f"[MOCK HTML EMAIL] To: {to_email} | Subject: {subject}")
            return False

        payload = {
            "from": self.from_header,
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        if text_fallback:
            payload["text"] = text_fallback
        try:
            return await self._post_to_resend(payload)
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

    svc = EmailService()

    if svc._looks_like_placeholder():
        print(f"[MOCK ATTACHMENT EMAIL] To: {to_email} | Subject: {subject} | Attachment: {attachment_name}")
        return True

    payload = {
        "from": svc.from_header,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            file_bytes = f.read()
        payload["attachments"] = [{
            "filename": attachment_name,
            "content": base64.b64encode(file_bytes).decode("ascii"),
        }]
        print(f"[EMAIL] Attaching PDF: {attachment_name}")
    else:
        print(f"[EMAIL] No attachment found at: {attachment_path}")

    try:
        return await svc._post_to_resend(payload)
    except Exception as e:
        print(f"[EMAIL] Failed to send email with attachment: {str(e)}")
        return False
