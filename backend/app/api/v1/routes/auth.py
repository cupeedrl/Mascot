import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    UserResponse,
    ValidateResetTokenResponse,
)
from app.services.ai_guard import ai_guard, AICooldownError, AIDuplicateRequestError
from app.services.auth import (
    DuplicateEmailError,
    InvalidResetTokenError,
    authenticate_user,
    create_password_reset_token,
    normalize_email,
    register_user,
    reset_password_with_token,
    validate_reset_token,
)
from app.services.email import send_password_reset_email

router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    registration: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        return register_user(db, registration)
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = authenticate_user(db, str(credentials.email), credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, expires_in = create_access_token(user.id)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/logout", response_model=LogoutResponse)
def logout(_current_user: Annotated[User, Depends(get_current_user)]) -> LogoutResponse:
    return LogoutResponse()


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ForgotPasswordResponse:
    email = str(payload.email).strip()
    # Rate limit password reset requests (60s cooldown per email)
    # Use deterministic namespace UUID for email-based rate limiting
    import uuid
    email_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"reset:{normalize_email(email)}")
    fingerprint = ai_guard.compute_fingerprint(email_uuid, "forgot_password", {"email": normalize_email(email)})

    try:
        ai_guard.check_and_acquire(email_uuid, "forgot_password", fingerprint, cooldown_seconds=60)
        is_throttled = False
    except (AICooldownError, AIDuplicateRequestError):
        # Even when throttled, we return the exact same generic success message to prevent timing and enumeration attacks
        is_throttled = True
        logger.info("Password reset request throttled for email hash namespace: %s", email_uuid)

    if not is_throttled:
        try:
            raw_token = create_password_reset_token(db, email)
            if raw_token:
                send_password_reset_email(email, raw_token)
            ai_guard.release(email_uuid, "forgot_password", fingerprint, mark_success=True)
        except Exception as exc:
            ai_guard.release(email_uuid, "forgot_password", fingerprint, mark_success=False)
            logger.error("Error during password reset token creation: %s", exc)

    return ForgotPasswordResponse()


@router.get("/reset-password/validate", response_model=ValidateResetTokenResponse)
def validate_password_reset_token(
    token: str,
    db: Annotated[Session, Depends(get_db)],
) -> ValidateResetTokenResponse:
    is_valid = validate_reset_token(db, token)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đường dẫn đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.",
        )
    return ValidateResetTokenResponse(valid=True)


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ResetPasswordResponse:
    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu xác nhận không khớp.",
        )

    try:
        reset_password_with_token(db, payload.token, payload.new_password)
    except InvalidResetTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ResetPasswordResponse()
