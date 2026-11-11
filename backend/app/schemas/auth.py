from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator, model_validator


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=12, max_length=128)
    # Required by the web sign-up form; optional in the API for older clients.
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    username: str | None = Field(default=None, min_length=3, max_length=30)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("display name must not be blank")
        return cleaned


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Sign in with an email (``email``) or with an email or username (``identifier``).
    email: EmailStr | None = Field(default=None, max_length=320)
    identifier: str | None = Field(default=None, min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)
    # Keep the learner signed in for days instead of minutes.
    remember_me: bool = False

    @model_validator(mode="after")
    def require_identifier(self) -> "LoginRequest":
        if not self.email and not (self.identifier and self.identifier.strip()):
            raise ValueError("email or identifier is required")
        return self

    @property
    def login_name(self) -> str:
        return str(self.email) if self.email else (self.identifier or "").strip()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    username: str | None = None
    display_name: str | None = None
    email_verified_at: datetime | None = None
    role: Literal["user", "admin"] = "user"
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RegisterResponse(UserResponse):
    verification_required: bool = False


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=320)
    code: str = Field(pattern=r"^\d{6}$")
    remember_me: bool = False


class ResendVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=320)


class ResendVerificationResponse(BaseModel):
    message: str = "Nếu tài khoản cần xác nhận, Mascot đã gửi một mã mới tới email này."
    resend_after_seconds: int = 60


class UsernameAvailabilityResponse(BaseModel):
    username: str
    available: bool
    reason: Literal["invalid", "reserved", "taken"] | None = None

    @computed_field
    @property
    def message(self) -> str | None:
        return {
            "invalid": "Tên người dùng gồm 3–30 ký tự: chữ thường không dấu, số, dấu chấm hoặc gạch dưới, bắt đầu bằng chữ.",
            "reserved": "Tên này đã được hệ thống giữ lại.",
            "taken": "Tên này đã có người dùng.",
        }.get(self.reason or "")


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class LogoutResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=320)


class ForgotPasswordResponse(BaseModel):
    message: str = "Nếu email này đã được đăng ký, Mascot sẽ gửi hướng dẫn đặt lại mật khẩu."


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(min_length=12, max_length=128)


class ResetPasswordResponse(BaseModel):
    message: str = "Mật khẩu đã được cập nhật thành công."


class ValidateResetTokenResponse(BaseModel):
    valid: bool = True


