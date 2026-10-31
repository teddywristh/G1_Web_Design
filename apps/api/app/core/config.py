"""Application settings loaded from environment variables."""

from functools import lru_cache
import json

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="legal-ai", alias="APP_NAME")
    firebase_project_id: str | None = Field(default=None, alias="FIREBASE_PROJECT_ID")
    firebase_storage_bucket: str | None = Field(default=None, alias="FIREBASE_STORAGE_BUCKET")
    google_application_credentials: str | None = Field(default=None, alias="GOOGLE_APPLICATION_CREDENTIALS")
    firebase_auth_emulator_host: str | None = Field(default=None, alias="FIREBASE_AUTH_EMULATOR_HOST")
    firestore_emulator_host: str | None = Field(default=None, alias="FIRESTORE_EMULATOR_HOST")
    storage_emulator_host: str | None = Field(default=None, alias="STORAGE_EMULATOR_HOST")
    backend_cors_origins: list[str] = Field(default=["http://localhost:3000"], alias="BACKEND_CORS_ORIGINS")
    max_upload_size_bytes: int = Field(default=20 * 1024 * 1024, alias="MAX_UPLOAD_SIZE_BYTES")

    @classmethod
    def parse_env_var(cls, field_name: str, raw_val: str):
        if field_name == "backend_cors_origins":
            return json.loads(raw_val)
        return raw_val


@lru_cache
def get_settings() -> Settings:
    return Settings()
