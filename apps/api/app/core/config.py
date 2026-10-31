"""Validated runtime configuration; emulator endpoints never reach production."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
        populate_by_name=True,
    )
    app_env: str = "development"
    app_name: str = "legal-api"
    firebase_project_id: str | None = None
    firebase_storage_bucket: str | None = None
    google_application_credentials: str | None = None
    firebase_auth_emulator_host: str | None = None
    firestore_emulator_host: str | None = None
    storage_emulator_host: str | None = None
    backend_cors_origins: list[str] = ["http://localhost:3000"]
    max_upload_size_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    storage_timeout_seconds: int = Field(default=30, ge=1, le=120)
    upload_lease_seconds: int = Field(default=900, ge=300)
    orphan_grace_seconds: int = Field(default=3600, ge=1800)

    @model_validator(mode="after")
    def validate_environment(self):
        hosts = (
            self.firebase_auth_emulator_host,
            self.firestore_emulator_host,
            self.storage_emulator_host,
        )
        if self.app_env.lower() in {"prod", "production"}:
            if not self.firebase_project_id or not self.firebase_storage_bucket:
                raise ValueError("Production project and storage bucket are required")
            if any(hosts):
                raise ValueError("Emulators are forbidden in production")
            if "*" in self.backend_cors_origins:
                raise ValueError("Production CORS requires explicit origins")
        if any(hosts) and not all(hosts):
            raise ValueError("Configure all three emulators together")
        if self.firebase_project_id and self.firebase_project_id.startswith("demo-"):
            if not all(hosts):
                raise ValueError("Demo projects require all emulators")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
