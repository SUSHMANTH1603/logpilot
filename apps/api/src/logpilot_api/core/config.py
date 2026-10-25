"""Centralized application configuration and environment validation."""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """LogPilot backend runtime settings and environment validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Runtime Environment
    app_env: str = Field(
        default="development",
        description="Runtime environment: development, testing, staging, production",
    )
    app_name: str = Field(default="LogPilot", description="Application service name")
    debug: bool = Field(default=False, description="Debug mode flag")
    log_level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    api_host: str = Field(default="127.0.0.1", description="Binding host for API")
    api_port: int = Field(default=8000, description="Binding port for API")
    secret_key: str = Field(
        default="dev-insecure-secret-key-change-in-production-min-32-chars",
        description="Application secret key for cryptographic operations",
    )
    jwt_secret_key: str | None = Field(
        default=None,
        description=(
            "Dedicated secret key for signing user JWT tokens (never reused from secret_key). "
            "For production deployments, generate a high-entropy key with 'openssl rand -hex 32'."
        ),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="Cryptographic algorithm for JWT signing (fixed HS256 allowlist)",
    )
    access_token_expire_minutes: int = Field(
        default=1440,
        description="Access token validity lifetime in minutes (default: 24 hours / 1440 minutes)",
    )

    # PostgreSQL System of Record (ADR-005)
    database_url: str = Field(
        default="postgresql+asyncpg://logpilot:logpilot_dev_password@127.0.0.1:5432/logpilot",
        description="Async SQLAlchemy database connection string",
    )
    database_sync_url: str = Field(
        default="postgresql+psycopg://logpilot:logpilot_dev_password@127.0.0.1:5432/logpilot",
        description="Sync DB URL for Alembic migrations and synchronous probes",
    )

    # Redis Infrastructure Layer (ADR-005)
    redis_url: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Redis connection URL for queue and ephemeral cache",
    )

    # Qdrant Vector Index (ADR-005)
    qdrant_url: str = Field(
        default="http://127.0.0.1:6333",
        description="Qdrant REST API URL for vector retrieval",
    )
    qdrant_api_key: str = Field(default="", description="Qdrant API key if secured")

    # Local LLM Gateway (ADR-002)
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        description="Base URL for local Ollama inference service",
    )

    # CORS Settings
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173"],
        description="Allowed CORS origin domains",
    )

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        valid_envs = {"development", "testing", "staging", "production"}
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f"app_env must be one of {valid_envs}")
        return v_lower

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    @field_validator("api_port")
    @classmethod
    def validate_api_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("api_port must be between 1 and 65535")
        return v

    @model_validator(mode="after")
    def validate_jwt_configuration(self) -> "Settings":
        if self.jwt_algorithm != "HS256":
            raise ValueError(f"jwt_algorithm must be 'HS256', got '{self.jwt_algorithm}'")

        dev_default = "dev-insecure-jwt-secret-key-change-in-production-min-32-chars"
        if not self.jwt_secret_key or not self.jwt_secret_key.strip():
            if self.is_production:
                raise ValueError("JWT_SECRET_KEY is mandatory and cannot be empty in production.")
            self.jwt_secret_key = dev_default

        if self.jwt_secret_key == self.secret_key:
            raise ValueError(
                "JWT_SECRET_KEY must not reuse or fall back to the generic application secret_key."
            )

        if self.is_production:
            if len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 32 characters long in production. "
                    "Generate a cryptographically secure key using 'openssl rand -hex 32'."
                )
            if self.jwt_secret_key == dev_default:
                raise ValueError("Insecure default JWT_SECRET_KEY cannot be used in production.")

        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_testing(self) -> bool:
        return self.app_env == "testing"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
