import base64
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WEAK_EXAMPLE_KEYS = {
    "dGVzdF9tYXN0ZXJfa2V5XzMyX2J5dGVzX3N0cmluZw==",  # test key allowed only in test/dev
    "example",
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    "///////////////////////////////////////////=",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: Literal["development", "production", "test"] = "development"
    PUBLIC_URL: str = "http://localhost:3000"
    GATEWAY_MASTER_KEY: str = Field(
        default="",
        description="32-byte base64-encoded key used to encrypt provider secrets",
    )
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/llm_gateway"
    REDIS_URL: str = "redis://:redispassword@localhost:6379/0"
    LOG_LEVEL: str = "info"
    MAX_REQUEST_BYTES: int = 4 * 1024 * 1024  # 4 MB
    DEFAULT_RETENTION_DAYS: int = 30
    ALLOW_PRIVATE_PROVIDER_URLS: bool = False
    DEMO_MODE: bool = False
    DOMAIN: str = "localhost"

    @field_validator("GATEWAY_MASTER_KEY")
    @classmethod
    def validate_master_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "GATEWAY_MASTER_KEY is missing. "
                "It must be provided as a 32-byte base64-encoded string."
            )
        clean = v.strip()
        if "example" in clean.lower():
            raise ValueError("GATEWAY_MASTER_KEY cannot use an example value in configuration.")
        try:
            decoded = base64.b64decode(clean, validate=True)
        except Exception as e:
            raise ValueError(f"GATEWAY_MASTER_KEY must be valid base64: {e}") from e

        if len(decoded) != 32:
            raise ValueError(
                f"GATEWAY_MASTER_KEY must decode to exactly 32 bytes (got {len(decoded)} bytes)."
            )

        if len(set(decoded)) <= 1:
            raise ValueError("GATEWAY_MASTER_KEY is too weak (all repeating bytes).")

        return clean


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
