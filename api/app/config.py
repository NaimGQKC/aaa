from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Provider: 'local' (offline dev/demo/CI) or 'mistral' (EU-sovereign API)
    dd_provider: str = "local"

    mistral_api_key: str = ""
    mistral_ocr_model: str = "mistral-ocr-latest"
    mistral_llm_model: str = "mistral-large-2512"
    mistral_small_model: str = "ministral-8b-latest"

    database_url: str = f"sqlite:///{REPO_ROOT}/data/dd.sqlite3"

    storage_backend: str = "local"  # 'local' | 's3'
    local_storage_dir: str = str(REPO_ROOT / "data" / "storage")
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "dd"
    s3_secret_key: str = "dd-secret-dd"
    s3_bucket: str = "dd-artifacts"
    s3_region: str = "fr-par"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    # AI Act Article 26(6): 6-month floor, configurable upwards only.
    audit_log_retention_days: int = 183

    # Abstention thresholds by confidence tier
    abstain_below_confidence: float = 0.55
    review_below_confidence: float = 0.80


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.audit_log_retention_days < 183:
        # Article 26(6) floor — never allow shorter retention.
        object.__setattr__(s, "audit_log_retention_days", 183)
    return s
