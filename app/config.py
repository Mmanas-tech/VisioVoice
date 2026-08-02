"""Application configuration management."""

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    APP_NAME: str = "Lip-Reading AI Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/lipread_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 60

    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: str = "lipread-videos"
    AWS_REGION: str = "us-east-1"

    STORAGE_TYPE: str = "local"
    LOCAL_STORAGE_PATH: str = "./storage"

    MODEL_PATH: str = "./models/lip_reading_model.pth"
    MODEL_DEVICE: str = "cpu"
    MODEL_BACKEND: str = "auto"  # "custom", "av_hubert", or "auto"

    AV_HUBERT_CHECKPOINT: str = "./models/av_hubert.pt"
    AV_HUBERT_BEAM_SIZE: int = 50
    AV_HUBERT_LEN_PENALTY: float = 1.0
    AV_HUBERT_MAX_LEN_A: float = 1.0
    AV_HUBERT_MAX_LEN_B: int = 0

    MAX_UPLOAD_SIZE_MB: int = 2048
    ALLOWED_VIDEO_TYPES: List[str] = [".mp4", ".mov", ".avi", ".mkv"]

    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_FAILED_LOGIN: int = 5

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "lipread_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    @property
    def sync_database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def async_database_url(self) -> str:
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    def validate_production_settings(self):
        """Validate critical settings for production environment."""
        import os
        if self.ENVIRONMENT == "production":
            if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY == "":
                self.JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
            if not self.JWT_SECRET_KEY:
                raise ValueError(
                    "JWT_SECRET_KEY must be set in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
