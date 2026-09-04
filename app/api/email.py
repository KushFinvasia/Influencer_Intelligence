"""Email integration endpoints."""

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.services.creator_service import CreatorService
from app.services.email_service import EmailService, EmailServiceError

router = APIRouter(prefix="/api/creators", tags=["Email"])

class SendEmailRequest(BaseModel):
    subject: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)

@router.post("/{creator_id}/email")
async def send_email_to_creator(
    creator_id: int,
    request: SendEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send an email to a creator via SMTP."""
    # 1. Fetch creator
    creator_service = CreatorService(db)
    creator = await creator_service.get_creator(creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    # 2. Validate email
    if not creator.email:
        raise HTTPException(status_code=400, detail="Creator does not have a valid email address")

    # 3. Send email
    email_service = EmailService()
    try:
        result = await email_service.send_creator_email(
            creator_id=creator_id,
            recipient_email=creator.email,
            subject=request.subject,
            body=request.message
        )
        return result
    except EmailServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred while sending email.")
