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

    # ------------------------------------------------------------------ #
    # V7_lite extension fields — additive only
    # ------------------------------------------------------------------ #
    #
    # APP_MODE controls which data tier the system runs in:
    #
    #   "v7_lite"          → yfinance + FRED + CBOE free data, lite layers
    #   "v7_institutional" → Polygon + Sharadar paid data, full layers
    #
    # When APP_MODE = "v7_institutional" but no Polygon/Sharadar keys are
    # set, the system falls back to synthetic data and surfaces a
    # "Developer Mode" badge on the dashboard.
    app_mode: str = "v7_lite"

    # HMM model paths (one artifact per mode).
    hmm_model_path_institutional: Path = Path("models/hmm_v7_institutional.pkl")
    hmm_model_path_lite: Path = Path("models/hmm_v7_lite.pkl")

    # Kronos probabilistic forecaster — canonical (promoted) artifact path.
    # Validated-only: the dashboard shows Kronos forecasts only when this exists.
    kronos_model_path_lite: Path = Path("models/kronos_v7_lite.pkl")

    # V7_lite validation thresholds.
    divergence_threshold_lite: float = 0.40
    max_missing_bar_fraction: float = 0.02
    max_stale_cross_ticker_fraction: float = 0.20

    # V7_lite survivorship bias estimates from the literature.
    # Used by the Survivorship Bias Panel; values mirror Elton & Gruber (1996)
    # and subsequent literature.
    survivorship_sharpe_inflation_low: float = 0.10
    survivorship_sharpe_inflation_high: float = 0.30
    survivorship_return_inflation_low_pct: float = 1.0
    survivorship_return_inflation_high_pct: float = 3.0
    survivorship_win_rate_inflation_low_pp: int = 3
    survivorship_win_rate_inflation_high_pp: int = 8
    survivorship_bias_source: str = "Elton & Gruber (1996) + subsequent literature"

    # V7_lite binomial wipeout injection parameters (Layer 10).
    annual_impairment_rate: float = 0.02
    synthetic_wipeout_return: float = -0.60

    # --- Derived helpers (computed properties) ---------------------------

    @property
    def institutional_data_available(self) -> bool:
        """True when paid keys are configured for v7_institutional mode."""
        return bool(self.polygon_api_key) and bool(self.sharadar_api_key)

    @property
    def developer_mode(self) -> bool:
        """V7 Institutional mode but missing paid API keys → synthetic-data fallback."""
        return self.app_mode == "v7_institutional" and not self.institutional_data_available

    @property
    def hmm_model_path(self) -> Path:
        return (
            self.hmm_model_path_lite
            if self.app_mode == "v7_lite"
            else self.hmm_model_path_institutional
        )

    def survivorship_bias_estimate(self) -> dict:
        """Snapshot used by the dashboard's permanent disclosure panel."""
        return {
            "annualized_return_inflation_low_pct": self.survivorship_return_inflation_low_pct,
            "annualized_return_inflation_high_pct": self.survivorship_return_inflation_high_pct,
            "sharpe_inflation_low": self.survivorship_sharpe_inflation_low,
            "sharpe_inflation_high": self.survivorship_sharpe_inflation_high,
            "win_rate_inflation_low_pp": self.survivorship_win_rate_inflation_low_pp,
            "win_rate_inflation_high_pp": self.survivorship_win_rate_inflation_high_pp,
            "source": self.survivorship_bias_source,
        }


settings = Settings()
