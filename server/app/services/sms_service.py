"""
SMS sending service using Twilio.

Mirrors the pattern used by EmailService: if Twilio credentials are not
configured, it logs/mock-sends instead of raising, so local development
still works without a Twilio account.
"""
import logging

from fastapi.concurrency import run_in_threadpool

from app.config import settings

logger = logging.getLogger(__name__)


class SMSService:
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER

    def _is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number)

    async def send_sms(self, to_phone: str, body: str) -> bool:
        """
        Send an SMS via Twilio. Returns True if the message was sent
        (or mock-sent in dev mode), False if sending failed.
        """
        if not self._is_configured():
            logger.warning(
                "Twilio not configured (missing TWILIO_ACCOUNT_SID/AUTH_TOKEN/PHONE_NUMBER), "
                "skipping SMS."
            )
            print(f"[MOCK SMS] To: {to_phone} | Body: {body[:80]}...")
            return False

        def _send():
            # Imported lazily so the app can still start if the twilio
            # package isn't installed in some environments.
            from twilio.rest import Client
            from twilio.base.exceptions import TwilioRestException

            client = Client(self.account_sid, self.auth_token)
            try:
                message = client.messages.create(
                    body=body,
                    from_=self.from_number,
                    to=to_phone,
                )
                logger.info(f"[SMS] Sent to {to_phone}, SID: {message.sid}")
                return True
            except TwilioRestException as e:
                logger.error(f"[SMS ERROR] Twilio failure sending to {to_phone}: {e}")
                raise
            except Exception as e:
                logger.error(f"[SMS ERROR] General failure sending to {to_phone}: {e}")
                raise

        try:
            return await run_in_threadpool(_send)
        except Exception as e:
            logger.error(f"SMS FAILED to {to_phone}: {str(e)}")
            return False
