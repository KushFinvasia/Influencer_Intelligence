import smtplib
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

class EmailServiceError(Exception):
    pass

class EmailService:
    def __init__(self):
        self.settings = get_settings()

    async def send_creator_email(self, creator_id: int, recipient_email: str, subject: str, body: str) -> dict:
        """
        Sends an email using SMTP and logs only the metadata.
        """
        if not self.settings.smtp_user or not self.settings.smtp_password or not self.settings.smtp_from_email:
            logger.error("SMTP configuration is missing. Cannot send email.")
            raise EmailServiceError("SMTP setup is incomplete. Please configure SMTP credentials.")

        # Log intent
        logger.info(f"Preparing to send email to creator_id={creator_id}, recipient={recipient_email}")

        msg = MIMEMultipart()
        msg['From'] = self.settings.smtp_from_email
        msg['To'] = recipient_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        # Run the blocking SMTP call in a separate thread
        try:
            await asyncio.to_thread(self._send_email_sync, msg)
            
            # Log success metadata ONLY
            logger.info(f"Email sent successfully to creator_id={creator_id}, recipient={recipient_email}, timestamp={datetime.now(timezone.utc).isoformat()}")
            
            return {
                "status": "success",
                "recipient": recipient_email,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            # Log failure metadata ONLY
            logger.error(f"Failed to send email to creator_id={creator_id}, recipient={recipient_email}, error={str(e)}")
            raise EmailServiceError(f"Failed to send email: {str(e)}")

    def _send_email_sync(self, msg: MIMEMultipart):
        """Blocking SMTP send method to be run in a thread."""
        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=self.settings.smtp_timeout) as server:
                server.starttls()
                server.login(self.settings.smtp_user, self.settings.smtp_password)
                server.send_message(msg)
        except smtplib.SMTPException as e:
            logger.error(f"SMTP Protocol Error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"SMTP Connection Error: {str(e)}")
            raise
