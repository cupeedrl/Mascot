from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mascot API"
    environment: Literal["development", "production", "test", "staging"] = (
        "development"
    )
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(min_length=1)
    cors_origins: list[str] = Field(default_factory=list)
    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    jwt_issuer: str = Field(default="mascot-api", min_length=1)
    jwt_audience: str = Field(default="mascot-frontend", min_length=1)
    ai_provider: Literal["groq", "openai"] = "groq"
    groq_api_key: SecretStr | None = None
    groq_model: str = Field(
        default="openai/gpt-oss-20b", min_length=1, max_length=100
    )
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1", min_length=1, max_length=500
    )
    openai_api_key: SecretStr | None = None
    openai_model: str = Field(default="gpt-5.4-nano", min_length=1, max_length=100)
    ai_request_timeout_seconds: float = Field(default=20.0, ge=1.0, le=120.0)
    ai_max_output_tokens: int = Field(default=800, ge=200, le=4000)
    ai_exercise_max_output_tokens: int = Field(default=4000, ge=800, le=8000)
    ai_max_tool_rounds: int = Field(default=5, ge=1, le=10)
    ai_chat_max_history_messages: int = Field(default=20, ge=2, le=100)
    ai_chat_max_message_length: int = Field(default=1000, ge=10, le=5000)
    email_provider: Literal["console", "resend", "gmail_smtp", "test"] = "console"
    resend_api_key: SecretStr | None = None
    smtp_host: str = Field(default="smtp.gmail.com", min_length=1, max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_app_password: SecretStr | None = None
    smtp_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    email_from: str = Field(
        default="Mascot <onboarding@resend.dev>", min_length=1, max_length=200
    )
    frontend_base_url: str = Field(
        default="http://localhost:5173", min_length=1, max_length=500
    )
    password_reset_token_expire_minutes: int = Field(default=20, ge=5, le=120)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                import json
                try:
                    return json.loads(stripped)
                except Exception:
                    pass
            return [part.strip() for part in stripped.split(",") if part.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().rstrip("/") for value in values if value.strip()]
        if "*" in normalized:
            raise ValueError("Wildcard CORS origins are not allowed")
        if any(not value.startswith(("http://", "https://")) for value in normalized):
            raise ValueError("CORS origins must use http:// or https://")
        return list(dict.fromkeys(normalized))

    @model_validator(mode="after")
    def validate_email_provider_config(self) -> "Settings":
        if self.email_provider == "gmail_smtp":
            if not self.smtp_username or not self.smtp_app_password:
                raise ValueError(
                    "SMTP_USERNAME and SMTP_APP_PASSWORD are required when EMAIL_PROVIDER is set to gmail_smtp"
                )
        elif self.email_provider == "resend":
            if not self.resend_api_key:
                raise ValueError(
                    "RESEND_API_KEY is required when EMAIL_PROVIDER is set to resend"
                )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
