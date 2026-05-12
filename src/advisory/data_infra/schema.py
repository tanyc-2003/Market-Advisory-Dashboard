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
    ):
        for statement in ddl.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(stmt)
