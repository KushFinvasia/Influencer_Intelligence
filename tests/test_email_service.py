import pytest
import smtplib
from unittest.mock import patch, MagicMock

from app.services.email_service import EmailService, EmailServiceError

@pytest.fixture
def mock_settings():
    with patch("app.services.email_service.get_settings") as mock_get_settings:
        settings = MagicMock()
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 587
        settings.smtp_user = "test_user"
        settings.smtp_password = "test_password"
        settings.smtp_from_email = "test@example.com"
        settings.smtp_timeout = 10
        mock_get_settings.return_value = settings
        yield settings

@pytest.mark.asyncio
async def test_send_email_success(mock_settings):
    service = EmailService()
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = mock_smtp.return_value.__enter__.return_value
        result = await service.send_creator_email(
            creator_id=123,
            recipient_email="creator@example.com",
            subject="Hello",
            body="World"
        )
        assert result["status"] == "success"
        assert result["recipient"] == "creator@example.com"
        assert "timestamp" in result
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test_user", "test_password")
        mock_server.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_send_email_missing_credentials(mock_settings):
    mock_settings.smtp_user = ""
    service = EmailService()
    with pytest.raises(EmailServiceError, match="SMTP setup is incomplete"):
        await service.send_creator_email(
            creator_id=123,
            recipient_email="creator@example.com",
            subject="Hello",
            body="World"
        )

@pytest.mark.asyncio
async def test_send_email_smtp_error(mock_settings):
    service = EmailService()
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.side_effect = smtplib.SMTPException("Connection refused")
        with pytest.raises(EmailServiceError, match="Failed to send email: Connection refused"):
            await service.send_creator_email(
                creator_id=123,
                recipient_email="creator@example.com",
                subject="Hello",
                body="World"
            )
