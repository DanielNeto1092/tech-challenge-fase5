from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _resolve_backend_path(path: Path) -> Path:
    return path if path.is_absolute() else BACKEND_ROOT / path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", ".env"),
        env_prefix="GUARDIA_",
        extra="ignore",
    )

    app_name: str = "Guardiã AI"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    database_path: Path = Path("data/audit/guardia_ai.db")
    model_artifact_path: Path = Path("artifacts/maternal_risk_model_v1.0.0.joblib")
    model_metrics_path: Path = Path("artifacts/training_report_v1.0.0.json")
    knowledge_base_path: Path = Path("data/knowledge_base")

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.6-luna"
    llm_timeout_seconds: float = 45.0
    allow_llm_fallback: bool = True
    rag_top_k: int = 4
    max_history_records: int = 100

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_database_path(self) -> Path:
        return _resolve_backend_path(self.database_path)

    @property
    def resolved_model_artifact_path(self) -> Path:
        return _resolve_backend_path(self.model_artifact_path)

    @property
    def resolved_model_metrics_path(self) -> Path:
        return _resolve_backend_path(self.model_metrics_path)

    @property
    def resolved_knowledge_base_path(self) -> Path:
        return _resolve_backend_path(self.knowledge_base_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
