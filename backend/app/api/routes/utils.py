"""Utility routes for health checks and email testing."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from pydantic.networks import EmailStr

from app.api.dependencies import EmailClientDep, check_database_connection, get_current_active_superuser
from app.utils.email import generate_test_email
from app.utils.markdown import render_markdown

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post("/markdown-preview")
async def preview_markdown(body: Annotated[str, Body(embed=True, max_length=20000)]) -> str:
    """Render a bounded Markdown preview using the same sanitization as saved comments."""
    return render_markdown(body)


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def test_email(email_to: EmailStr, email_client: EmailClientDep) -> None:
    """Test emails."""
    email_data = generate_test_email(email_to=email_to)
    email_client.send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )


@router.get(path="/health-check/")
async def health_check(
    db_reachable: Annotated[bool, Depends(check_database_connection)],
) -> bool:
    """Check if the database connection is working."""
    return db_reachable
