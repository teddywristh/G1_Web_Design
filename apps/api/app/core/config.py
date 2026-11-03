"""Validated runtime configuration; emulator endpoints never reach production."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
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
    storage_backend: Literal["firebase", "local"] = "firebase"
    local_storage_dir: str = ".data/cloud-demo/storage"
    google_application_credentials: str | None = None
    firebase_auth_emulator_host: str | None = None
    firestore_emulator_host: str | None = None
    storage_emulator_host: str | None = None
    backend_cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8085",
        "http://127.0.0.1:8085",
    ]
    max_upload_size_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    storage_timeout_seconds: int = Field(default=30, ge=1, le=120)
    upload_lease_seconds: int = Field(default=900, ge=300)
    orphan_grace_seconds: int = Field(default=3600, ge=1800)

    auth_session_hours: int = Field(default=168, ge=1, le=336)
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    google_oauth_client_id: str = ""
    firebase_web_api_key: str = ""

    ai_credential_encryption_key: SecretStr = SecretStr("")
    ai_allow_shared_keys: bool = True
    ai_request_timeout_seconds: int = Field(default=30, ge=1, le=120)
    opencode_local_enabled: bool = False
    opencode_chatgpt_local_enabled: bool = False
    opencode_chatgpt_hosted_enabled: bool = False
    opencode_binary: str = ""
    opencode_models_file: str = str(Path.home() / ".cache/opencode/models.json")
    opencode_image: str = "legal-api-backend:verify"
    anthropic_api_key: str = Field(default="", repr=False)
    deepseek_api_key: str = Field(default="", repr=False)
    openrouter_api_key: str = Field(default="", repr=False)
    anthropic_model: str = ""
    anthropic_api_version: str = "2023-06-01"
    ai_max_output_tokens: int = Field(default=2048, ge=128, le=8192)
    openai_api_key: str = Field(default="", repr=False)
    default_llm_model: str = "gpt-4o-mini"
    default_embedding_model: str = "text-embedding-3-small"
    embedding_provider: Literal["openai", "openrouter", "local"] = "openai"
    local_embedding_url: str = "http://127.0.0.1:8010"
    local_embedding_model: str = "nvidia/Nemotron-3.5-Embed-1B-BF16"
    local_embedding_api_key: SecretStr = SecretStr("")
    local_embedding_timeout_seconds: int = Field(default=120, ge=1, le=300)
    local_embedding_profile_version: str = "bf16-sdpa-512-l2-v1"
    openrouter_embedding_model: str = ""
    openrouter_embedding_api_key: SecretStr = SecretStr("")
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_min_retrieval_score: float = Field(default=0.15, ge=0, le=1)

    knowledge_upload_enabled: bool = True
    qa_workflow_enabled: bool = True
    official_web_enabled: bool = False
    brave_search_api_key: SecretStr = SecretStr("")
    example_search_enabled: bool = False
    official_domains: list[str] = ["vbpl.vn", "congbao.chinhphu.vn", "chinhphu.vn"]
    embedding_dimensions: int = Field(default=1536, ge=1)
    max_kbs_per_request: int = Field(default=5, ge=1)
    max_private_kbs: int = Field(default=20, ge=1)
    candidate_k: int = Field(default=40, ge=1, le=200)
    final_evidence_k: int = Field(default=8, ge=1, le=20)
    max_evidence_tokens: int = Field(default=12000, ge=500)
    max_retrieval_passes: int = Field(default=2, ge=1, le=3)
    max_related_provisions: int = Field(default=12, ge=0)
    max_official_searches: int = Field(default=2, ge=0)
    max_fetched_sources: int = Field(default=4, ge=0)
    qa_deadline_seconds: int = Field(default=40, ge=5)
    evidence_run_retention_days: int = Field(default=30, ge=1)
    max_pdf_pages: int = Field(default=300, ge=1)
    max_provision_chars: int = Field(default=2000, ge=200)
    ocr_enabled: bool = False
    job_lease_seconds: int = Field(default=300, ge=30)
    job_max_failures: int = Field(default=5, ge=1)
    job_backoff_seconds: int = Field(default=30, ge=1)
    embedding_batch_size: int = Field(default=64, ge=1, le=256)
    embedding_max_chunks: int = Field(default=0, ge=0, le=20000)

    @model_validator(mode="after")
    def validate_environment(self):
        if self.opencode_local_enabled and self.app_env.lower() not in {"development", "test"}:
            raise ValueError("OpenCode worker is available only in development")
        if self.opencode_chatgpt_local_enabled and (
            not self.opencode_local_enabled or self.app_env.lower() not in {"development", "test"}
        ):
            raise ValueError("ChatGPT OAuth is available only in local development")
        hosts = (
            self.firebase_auth_emulator_host,
            self.firestore_emulator_host,
            self.storage_emulator_host,
        )
        if self.app_env.lower() in {"prod", "production"}:
            if not self.firebase_project_id or (
                self.storage_backend == "firebase" and not self.firebase_storage_bucket
            ):
                raise ValueError("Production project and storage bucket are required")
            if not self.auth_cookie_secure:
                raise ValueError("Production session cookie must use HTTPS")
            if any(hosts):
                raise ValueError("Emulators are forbidden in production")
            if "*" in self.backend_cors_origins:
                raise ValueError("Production CORS requires explicit origins")
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            raise ValueError("SameSite=None requires a Secure cookie")
        if any(hosts) and not all(hosts):
            raise ValueError("Configure all three emulators together")
        if self.firebase_project_id and self.firebase_project_id.startswith("demo-"):
            if not all(hosts):
                raise ValueError("Demo projects require all emulators")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
