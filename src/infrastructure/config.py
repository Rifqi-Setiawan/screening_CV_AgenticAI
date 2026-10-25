"""Application settings and configuration loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "production"
    APP_PORT: int = 8110
    APP_HOST: str = "127.0.0.1"

    # Database
    DATABASE_URL: str = ""
    DB_POOL_MIN: int = 2
    DB_POOL_MAX: int = 10

    # JWT Auth
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Storage
    STORAGE_VAULT_PATH: str = "/srv/hermes-control/services/cv-screening/data/cv-vault"
    MAX_UPLOAD_SIZE_MB: int = 10

    # LLM Data Policy
    # 'redacted_dev_router' enables 9Router for development with automated PII pre-flight verification
    # 'paid_or_local_only' disables unmetered dev router and restricts calls to official metered APIs / local models
    LLM_DATA_POLICY: str = "redacted_dev_router"
    LLM_GATEWAY_URL: str = "http://127.0.0.1:20128/v1"
    LLM_GATEWAY_KEY: str = ""
    LLM_MODEL_JD_COMPILER: str = "ag/gemini-3.8-flash-high"
    LLM_MODEL_VERIFIER: str = "ag/gemini-3.8-flash-high"
    LLM_MODEL_PROFILER: str = "ag/gemini-3.8-flash-high"
    LLM_TEMPERATURE: float = 0.0
    VERIFIER_CONCURRENCY: int = 5

    # Eligibility Gate
    ELIGIBILITY_FOUR_EYES: bool = True
    ALLOW_RELIGION_CRITERIA: bool = True
    ALLOW_GENDER_CRITERIA: bool = True

    # Taxonomy & Domain Configuration
    TAXONOMY_DIR: str = "config/taxonomy"

    # Hybrid Retrieval & Scoring Mode (FX-32)
    SCORING_MODE: str = "rules"  # "rules" | "hybrid"
    SEMANTIC_THRESHOLD: float = 0.65

    # System Versions (FX-40)
    EXTRACTOR_VERSION: str = "1.0.0"
    SCORING_VERSION: str = "2.0.0"

    # Embedding
    EMBEDDING_MODEL: str = "microsoft/harrier-oss-v1-270m"
    EMBEDDING_DIM: int = 640

    # CORS
    CORS_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://screening.rifqisetiawan.my.id",
    ]

    # Metrics
    METRICS_TOKEN: str = ""

    # PII Encryption Key (32 bytes hex for pgcrypto)
    PII_ENCRYPTION_KEY: str = ""

    @model_validator(mode="after")
    def validate_security(self) -> Settings:
        if self.APP_ENV != "test":
            if not self.JWT_SECRET or len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production/development")
            lower_jwt = self.JWT_SECRET.lower()
            if any(term in lower_jwt for term in ("insecure", "change", "secret-key")):
                raise ValueError("JWT_SECRET contains insecure default terms")

            if not self.METRICS_TOKEN or len(self.METRICS_TOKEN) < 32:
                raise ValueError("METRICS_TOKEN must be at least 32 characters in production/development")
            lower_metrics = self.METRICS_TOKEN.lower()
            if any(term in lower_metrics for term in ("insecure", "change", "default", "secret-key")):
                raise ValueError("METRICS_TOKEN contains insecure default terms")
        return self


settings = Settings()
