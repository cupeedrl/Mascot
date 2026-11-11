import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    UsernameAvailabilityResponse,
    VerifyEmailRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    UserResponse,
    ValidateResetTokenResponse,
)
from app.services.ai_guard import ai_guard, AICooldownError, AIDuplicateRequestError
from app.services.auth import (
    AccountDisabledError,
    AlreadyVerifiedError,
    DuplicateEmailError,
    DuplicateUsernameError,
    EmailNotVerifiedError,
    InvalidResetTokenError,
    InvalidUsernameError,
    VerificationCodeError,
    authenticate_user,
    create_email_verification_code,
    create_password_reset_token,
    normalize_email,
    register_user,
    reset_password_with_token,
    user_needing_verification,
    username_problem,
    validate_reset_token,
    verify_email_code,
)
from app.services.email import send_password_reset_email, send_verification_code_email

RESEND_COOLDOWN_SECONDS = 60
VERIFICATION_MESSAGES = {
    "INVALID_CODE": "Mã xác nhận không đúng.",
    "CODE_EXPIRED": "Mã đã hết hạn. Hãy gửi lại mã mới.",
    "CODE_LOCKED": "Bạn đã nhập sai quá nhiều lần. Hãy gửi lại mã mới.",
}

router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)


def _send_new_code(db: Session, user: User) -> None:
    try:
        code = create_email_verification_code(db, user)
        send_verification_code_email(user.email, code, user.display_name)
    except Exception as exc:  # the learner can request another code
        logger.error("Could not send verification code: %s", exc)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    registration: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RegisterResponse:
    try:
        user = register_user(db, registration)
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc
    except DuplicateUsernameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Tên người dùng này đã có người dùng.", "code": "USERNAME_TAKEN"},
        ) from exc
    except InvalidUsernameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": UsernameAvailabilityResponse(username="", available=False, reason=exc.reason).message,
                "code": "USERNAME_INVALID",
            },
        ) from exc
    verification_required = user.email_verified_at is None
    if verification_required:
        _send_new_code(db, user)
    response = RegisterResponse.model_validate(user)
    response.verification_required = verification_required
    return response


@router.get("/username-available", response_model=UsernameAvailabilityResponse)
def username_available(
    db: Annotated[Session, Depends(get_db)],
    username: Annotated[str, Query(min_length=1, max_length=30)],
) -> UsernameAvailabilityResponse:
    problem = username_problem(db, username)
    return UsernameAvailabilityResponse(
        username=username.strip().lower(), available=problem is None, reason=problem
    )


@router.post("/verify-email", response_model=TokenResponse)
def verify_email(
    payload: VerifyEmailRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Confirm the email with the 6-digit code and sign the learner in."""
    try:
        user = verify_email_code(db, str(payload.email), payload.code)
    except AlreadyVerifiedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Email này đã được xác nhận. Hãy đăng nhập.", "code": "ALREADY_VERIFIED"},
        ) from exc
    except VerificationCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": VERIFICATION_MESSAGES[exc.code],
                "code": exc.code,
                "remaining_attempts": exc.remaining_attempts,
            },
        ) from exc
    access_token, expires_in = create_access_token(user.id, remember_me=payload.remember_me)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/resend-verification", response_model=ResendVerificationResponse)
def resend_verification(
    payload: ResendVerificationRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ResendVerificationResponse:
    """Send a new code. The response is the same whether or not the email exists."""
    import uuid

    email = normalize_email(str(payload.email))
    key = uuid.uuid5(uuid.NAMESPACE_DNS, f"verify:{email}")
    fingerprint = ai_guard.compute_fingerprint(key, "resend_verification", {"email": email})
    try:
        ai_guard.check_and_acquire(
            key, "resend_verification", fingerprint, cooldown_seconds=RESEND_COOLDOWN_SECONDS
        )
    except (AICooldownError, AIDuplicateRequestError):
        return ResendVerificationResponse()
    try:
        user = user_needing_verification(db, email)
        if user is not None:
            _send_new_code(db, user)
        ai_guard.release(key, "resend_verification", fingerprint, mark_success=True)
    except Exception as exc:
        ai_guard.release(key, "resend_verification", fingerprint, mark_success=False)
        logger.error("Error while resending verification code: %s", exc)
    return ResendVerificationResponse()


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    try:
        user = authenticate_user(db, credentials.login_name, credentials.password)
    except EmailNotVerifiedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Bạn cần xác nhận email trước khi đăng nhập.",
                "code": "EMAIL_NOT_VERIFIED",
                "email": exc.user.email,
            },
        ) from exc
    except AccountDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Tài khoản của bạn hiện đang bị hạn chế.",
                "code": "ACCOUNT_DISABLED",
            },
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, expires_in = create_access_token(user.id, remember_me=credentials.remember_me)
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
