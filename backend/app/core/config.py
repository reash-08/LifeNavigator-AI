from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_ISSUER: str = "life-navigator-ai"
    JWT_AUDIENCE: str = "life-navigator-ai-api"
    ADMIN_EMAILS: str = ""
    LLM_PROVIDER: str = "template"
    EMBEDDING_PROVIDER: str = "deterministic"
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    SYNC_INTERVAL_HOURS: int = 24
    RAG_SIMILARITY_THRESHOLD: float = 0.1
    HYBRID_ALPHA: float = 0.6
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    ENVIRONMENT: str = "development"
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REGISTER: str = "3/hour"
    RATE_LIMIT_AGENT: str = "20/minute"
    RATE_LIMIT_ENABLED: bool = True
    TRUSTED_PROXIES: str = ""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return value

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("only HS256 is supported")
        return value

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def validate_token_lifetime(cls, value: int) -> int:
        if not 1 <= value <= 1_440:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440")
        return value

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [item.strip() for item in value.split(",") if item.strip()]
        if not origins:
            raise ValueError("At least one allowed origin must be specified in CORS_ALLOWED_ORIGINS")
        if "*" in origins:
            raise ValueError("Wildcard '*' origin is not permitted when credentials are enabled")
        for origin in origins:
            if not (origin.startswith("http://") or origin.startswith("https://")):
                raise ValueError(f"Invalid CORS origin '{origin}': must start with http:// or https://")
        return value

    @model_validator(mode="after")
    def validate_production_rate_limiting(self) -> "Settings":
        if self.ENVIRONMENT.strip().casefold() == "production" and not self.RATE_LIMIT_ENABLED:
            raise ValueError("RATE_LIMIT_ENABLED cannot be False when ENVIRONMENT is 'production'")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [
            item.strip().rstrip("/")
            for item in self.CORS_ALLOWED_ORIGINS.split(",")
            if item.strip()
        ]

    @property
    def admin_emails(self) -> set[str]:
        return {
            email.strip().casefold()
            for email in self.ADMIN_EMAILS.split(",")
            if email.strip()
        }

    @property
    def trusted_proxies_list(self) -> set[str]:
        return {
            ip.strip()
            for ip in self.TRUSTED_PROXIES.split(",")
            if ip.strip()
        }


settings = Settings()
