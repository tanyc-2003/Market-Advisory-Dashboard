"""Single source of truth for environment-driven config."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database paths
    main_db_path: Path = Path("data/db/main.duckdb")
    audit_db_path: Path = Path("data/db/audit.duckdb")
    cache_dir: Path = Path("data/cache/features")

    # API keys
    polygon_api_key: str = ""
    sharadar_api_key: str = ""
    fred_api_key: str = ""

    # Validation thresholds
    wf_sharpe_floor: float = 0.5
    wf_ece_ceiling: float = 0.05
    cpcv_p30_floor: float = 0.0
    dsr_floor: float = 0.95
    static_trial_floor: int = 2000
    divergence_threshold: float = 0.30

    # Feature engineering
    universe_size: int = 100
    ewma_clip: float = 4.0

    # Kelly cap (architecture invariant)
    kelly_absolute_cap: float = 0.20

    # Optional LLM
    llm_enabled: bool = False
    llm_model: str = "llama3"
    ollama_base_url: str = "http://localhost:11434"


settings = Settings()
