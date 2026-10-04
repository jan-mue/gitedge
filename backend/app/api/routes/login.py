"""Login and authentication routes."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse

from app.api.dependencies import (
    CrudServiceDep,
    CurrentUser,
    EmailClientDep,
    UserStoreDep,
    get_current_active_superuser,
)
from app.config import settings
from app.schemas.token import NewPassword, Token
from app.schemas.users import UserPublic
from app.utils.email import (
    generate_password_reset_token,
    generate_reset_password_email,
    verify_password_reset_token,
)
from app.utils.security import create_access_token, get_password_hash

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
async def login_access_token(
    crud_service: CrudServiceDep,
    username: Annotated[str, Form()],
    password: Annotated[str, Form(json_schema_extra={"format": "password"})],
) -> Token:
    """OAuth2 compatible token login, get an access token for future requests.

    Uses Form parameters directly instead of OAuth2PasswordRequestForm
    to avoid threading issues.
    """
    user = await crud_service.authenticate(email=username, password=password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(access_token=create_access_token(user.id, expires_delta=access_token_expires))


@router.post("/login/test-token")
async def test_token(current_user: CurrentUser) -> UserPublic:
    """Test access token."""
    return UserPublic.model_validate(current_user)


@router.post("/password-recovery/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def recover_password(email: str, crud_service: CrudServiceDep, email_client: EmailClientDep) -> None:
    """Password Recovery."""
    user = await crud_service.get_user_by_email(email=email)

    # Always return the same response to prevent email enumeration attacks
    # Only send email if user actually exists
    if user:
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(email_to=user.email, email=email, token=password_reset_token)
        email_client.send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )


@router.post("/reset-password/", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(user_store: UserStoreDep, body: NewPassword) -> None:
    """Reset password."""
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await user_store.get_by_email(email=email)
    if not user:
        # Don't reveal that the user doesn't exist - use same error as invalid token
        raise HTTPException(status_code=400, detail="Invalid token")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = get_password_hash(password=body.new_password)
    user.hashed_password = hashed_password
    await user_store.update(user)


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
)
async def recover_password_html_content(email: str, crud_service: CrudServiceDep) -> HTMLResponse:
    """HTML Content for Password Recovery."""
    user = await crud_service.get_user_by_email(email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(email_to=user.email, email=email, token=password_reset_token)

    return HTMLResponse(content=email_data.html_content, headers={"subject:": email_data.subject})
