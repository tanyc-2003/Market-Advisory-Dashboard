"""Single source of truth for all DuckDB DDL.

No ``CREATE TABLE`` statements exist anywhere else in the codebase.
"""
from __future__ import annotations

import duckdb

FEATURES_PIT_DDL = """
CREATE TABLE IF NOT EXISTS features_pit (
    ticker          VARCHAR  NOT NULL,
    effective_date  DATE     NOT NULL,
    knowledge_date  DATE     NOT NULL,
    feature_name    VARCHAR  NOT NULL,
    feature_value   DOUBLE,
    feature_version VARCHAR  NOT NULL,
    source          VARCHAR,
    pit_verified    BOOLEAN  DEFAULT FALSE,
    PRIMARY KEY (ticker, effective_date, knowledge_date,
                 feature_name, feature_version)
);
"""

DELISTED_TICKERS_DDL = """
CREATE TABLE IF NOT EXISTS delisted_tickers (
    ticker             VARCHAR  NOT NULL,
    termination_date   DATE     NOT NULL,
    termination_reason VARCHAR  CHECK (termination_reason IN
                        ('merger', 'bankruptcy', 'acquisition', 'voluntary', 'unknown')),
    terminal_return    DOUBLE,
    PRIMARY KEY (ticker, termination_date)
);
"""

PAPER_TRADE_DDL = """
CREATE TABLE IF NOT EXISTS paper_trade_performance (
    trade_id              BIGINT PRIMARY KEY,
    layer_attributed_to   VARCHAR  NOT NULL,
    entry_date            DATE     NOT NULL,
    exit_date             DATE,
    entry_fill_price      DOUBLE   NOT NULL,
    exit_fill_price       DOUBLE,
    pnl_pct               DOUBLE,
    market_state_at_entry INTEGER,
    friction_z_at_entry   DOUBLE,
    slippage_bps          DOUBLE,
    signal_hit            BOOLEAN
);
"""

BACKTEST_EXEC_DDL = """
CREATE SEQUENCE IF NOT EXISTS exec_id_seq START 1;
CREATE TABLE IF NOT EXISTS backtest_executions (
    execution_id    BIGINT PRIMARY KEY DEFAULT nextval('exec_id_seq'),
    layer_name      VARCHAR  NOT NULL,
    function_name   VARCHAR  NOT NULL,
    executed_at     TIMESTAMP NOT NULL DEFAULT now(),
    git_sha         VARCHAR,
    hyperparameters JSON
);
"""

VALIDATION_REPORTS_DDL = """
CREATE TABLE IF NOT EXISTS validation_reports (
    report_id        VARCHAR PRIMARY KEY,
    layer_name       VARCHAR NOT NULL,
    as_of            DATE    NOT NULL,
    status           VARCHAR NOT NULL,
    production_ready BOOLEAN NOT NULL,
    payload          JSON
);
"""

LLM_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS llm_cache (
    prompt_hash   VARCHAR PRIMARY KEY,
    model_id      VARCHAR NOT NULL,
    as_of_date    DATE    NOT NULL,
    prompt        TEXT    NOT NULL,
    response      TEXT    NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);
"""

JOURNAL_ENTRIES_DDL = """
CREATE TABLE IF NOT EXISTS journal_entries (
    entry_id          VARCHAR  PRIMARY KEY,
    ticker            VARCHAR  NOT NULL,
    entry_date        DATE     NOT NULL,
    direction         VARCHAR  NOT NULL,
    thesis            TEXT     NOT NULL,
    primary_catalyst  VARCHAR  NOT NULL,
    invalidation      TEXT     NOT NULL,
    expected_horizon  INTEGER  NOT NULL,
    confidence_self   INTEGER  NOT NULL,
    market_state_id   INTEGER,
    analog_hit_rate   DOUBLE,
    analog_n          INTEGER,
    contradictions    JSON,
    unknowns_present  BOOLEAN,
    exit_date         DATE,
    pnl_pct           DOUBLE,
    thesis_validated  BOOLEAN,
    exit_reason       VARCHAR
);
"""

PIT_QUERY = """
    SELECT feature_value
    FROM   features_pit
    WHERE  ticker        = ?
      AND  feature_name  = ?
      AND  knowledge_date < ?
      AND  effective_date <= ?
    ORDER BY knowledge_date DESC, effective_date DESC
    LIMIT 1
"""


# ------------------------------------------------------------------ #
# V7_lite extensions — additive only
# ------------------------------------------------------------------ #

HMM_MODEL_REGISTRY_DDL = """
CREATE TABLE IF NOT EXISTS hmm_model_registry (
    model_id               VARCHAR PRIMARY KEY,
    app_mode               VARCHAR NOT NULL,
    trained_at             TIMESTAMP NOT NULL,
    training_window_start  DATE,
    training_window_end    DATE,
    n_dimensions           INTEGER,
    k_selected             INTEGER,
    oos_log_likelihood     DOUBLE,
    validation_status      VARCHAR,
    walk_forward_sharpe    DOUBLE,
    deflated_sharpe        DOUBLE,
    retired_at             TIMESTAMP,
    retired_reason         VARCHAR,
    artifact_path          VARCHAR
);
"""

YFINANCE_FETCH_AUDIT_DDL = """
CREATE SEQUENCE IF NOT EXISTS yfinance_fetch_id_seq START 1;
CREATE TABLE IF NOT EXISTS yfinance_fetch_audit (
    fetch_id       BIGINT PRIMARY KEY DEFAULT nextval('yfinance_fetch_id_seq'),
    fetched_at     TIMESTAMP NOT NULL DEFAULT now(),
    ticker         VARCHAR   NOT NULL,
    fetch_date     DATE,
    status         VARCHAR   NOT NULL,
    n_rows         INTEGER,
    n_bad_rows     INTEGER   DEFAULT 0,
    n_consec_gaps  INTEGER   DEFAULT 0,
    note           VARCHAR,
    app_mode       VARCHAR   DEFAULT 'v7_lite'
);
"""

CBOE_PC_RATIO_DDL = """
CREATE TABLE IF NOT EXISTS cboe_pc_ratio (
    pc_date  DATE    PRIMARY KEY,
    ratio    DOUBLE  NOT NULL
);
"""


def _add_app_mode_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add the V7_lite ``app_mode`` column to the three audit tables.

    DuckDB doesn't support ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS``
    in every release, so we check the schema first and add the column
    only if it's missing.
    """
    for table in ("backtest_executions", "paper_trade_performance", "llm_cache"):
        rows = conn.execute(
            f"PRAGMA table_info('{table}')"
        ).fetchall()
        if not rows:
            continue  # table not yet created
        columns = {r[1] for r in rows}
        if "app_mode" not in columns:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN app_mode VARCHAR DEFAULT 'v7_institutional'"
            )


def bootstrap_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create every table.  Safe to re-run on an existing database."""
    # Note: BACKTEST_EXEC_DDL contains a sequence + table; split & run each.
    for ddl in (
        FEATURES_PIT_DDL,
        DELISTED_TICKERS_DDL,
        PAPER_TRADE_DDL,
        BACKTEST_EXEC_DDL,
        VALIDATION_REPORTS_DDL,
        JOURNAL_ENTRIES_DDL,
        LLM_CACHE_DDL,
        HMM_MODEL_REGISTRY_DDL,
        YFINANCE_FETCH_AUDIT_DDL,
        CBOE_PC_RATIO_DDL,
    ):
        for statement in ddl.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(stmt)
    # Apply the app_mode column to the V7-era audit tables.
    _add_app_mode_columns(conn)
