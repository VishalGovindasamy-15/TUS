from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "dev"  # dev | staging | prod | test
    DATABASE_URL: str = "postgresql+asyncpg://trustus:trustus@db:5432/trustus"
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"

    JWT_SECRET: str = "CHANGE_ME__set-a-long-random-secret-min-32-chars"
    JWT_ACCESS_TTL_MIN: int = 15
    JWT_REFRESH_TTL_DAYS: int = 30
    OTP_TTL_MIN: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RATE_PER_MIN: int = 5

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    SMS_PROVIDER: str = "dummy"  # dummy | msg91 | twilio
    MSG91_API_KEY: str = ""
    MSG91_SENDER: str = "TRUSTUS"
    TWILIO_SID: str = ""
    TWILIO_TOKEN: str = ""
    TWILIO_FROM: str = ""

    STORAGE_BACKEND: str = "local"  # local | s3
    STORAGE_DIR: str = "./storage"
    S3_BUCKET: str = ""
    S3_REGION: str = ""
    S3_ENDPOINT: str = ""
    PUBLIC_WEB_URL: str = "http://localhost:5173"

    EAGER_DETECTION: bool = False
    IMPOSSIBLE_TRAVEL_KMH_THRESHOLD: float = 150.0
    EXCESSIVE_SCAN_WINDOW_MIN: int = 10
    EXCESSIVE_SCAN_MAX: int = 10
    VERIFY_RATE_PER_MIN: int = 30
    VERIFY_CACHE_TTL_S: int = 30
    MULTI_LOCATION_MIN_CELLS: int = 10
    MULTI_LOCATION_DAYS: int = 7

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    SEED_ADMIN_PHONE: str = "+10000000001"
    SEED_MFG_PHONE: str = "+10000000002"
    SEED_DIST_PHONE: str = "+10000000003"
    SEED_RETAIL_PHONE: str = "+10000000004"
    SEED_TRANSPORT_PHONE: str = "+10000000005"
    SEED_SOCIAL_PHONE: str = "+10000000006"

    @property
    def is_production(self) -> bool:
        return self.ENV == "prod"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def validate_security(self) -> None:
        if self.JWT_SECRET.startswith("CHANGE_ME") or len(self.JWT_SECRET) < 32:
            raise RuntimeError(
                "JWT_SECRET must be set to a strong random value (min 32 chars). Refusing to start."
            )
        if self.is_production and self.cors_origin_list == ["*"]:
            raise RuntimeError("CORS wildcard is not allowed in production. Refusing to start.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
