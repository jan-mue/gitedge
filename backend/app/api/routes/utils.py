from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic.networks import EmailStr

from app.api.dependencies import (
    EmailClientDep,
    check_database_connection,
    get_current_active_superuser,
)
from app.schemas.items import Message
from app.utils.email import generate_test_email

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr, email_client: EmailClientDep) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    email_client.send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get(path="/health-check/")
async def health_check(
    db_reachable: Annotated[bool, Depends(check_database_connection)],
) -> bool:
    return db_reachable
