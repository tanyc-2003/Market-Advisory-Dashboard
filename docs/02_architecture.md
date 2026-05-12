# 02 — Architecture

## Data flow

```
                         +----------------------+
                         |  Data sources (stub) |
                         |  Polygon / Sharadar  |
                         |  FRED / CBOE         |
                         +----------+-----------+
                                    |
                                    v
+---------------------+   +------------------+   +-------------------+
| audit.duckdb        |<--+  FeatureStore    +-->| features_pit      |
| backtest_executions |   |  (PIT-safe reads)|   | (bitemporal)      |
+---------------------+   +---------+--------+   +-------------------+
                                    |
        +---------------------------+---------------------------+
        |                           |                           |
        v                           v                           v
+----------------+        +-------------------+        +-----------------+
| Layer 1 HMM    |        | Layer 4 risk      |        | Layer 5 stress  |
| market state   |        | factors+residuals |        | friction z      |
+--------+-------+        +---------+---------+        +--------+--------+
         |                          |                           |
         |  dominant_state_id       | factor exposures          | vol_z
         v                          v                           v
+--------------------+    +-----------------------+    +--------------------+
| Layer 2 analogs    |<---+                       +<---+ feeds Layer 2 cov  |
| Mahalanobis topK   |    |                       |    +--------------------+
+--------+-----------+    |                       |
         |                v                       v
         |        +----------------+    +------------------+
         |        | Layer 6 port-  |    | Layer 3 SHAP     |
         |        | folio diag.    |    | attribution      |
         |        +--------+-------+    +---------+--------+
         |                 |                      |
         v                 v                      v
+-----------------------------------------------------+
|  Layer 7 hygiene: contradictions, FDR-BY, unknowns  |
+--------------------------+--------------------------+
                           |
                           v
        +----------------------------------+
        | Layer 0 ValidationReport gate    |
        +--------------------+-------------+
                             |
        +--------------------+---------------------+
        v                                          v
+-------------------+                    +---------------------+
| Layer 8 journal   |                    | Layer 10 sizing     |
| trade entries     |                    | tail-aware Kelly    |
+---------+---------+                    +----------+----------+
          |                                         |
          v                                         v
+--------------------+                  +-------------------------+
| Layer 9 calibration|                  | Dashboard (Phase 12)    |
| reliability + ECE  |                  | Streamlit pages         |
+--------------------+                  +-------------------------+
```

Every arrow into a downstream layer goes through the Layer 0 gate. The gate is not at the dashboard — it is in the layer's public-method boundary, enforced by `requires_production`.

## Layer dependencies

| Layer | Depends directly on |
|---|---|
| 0 (validation) | nothing |
| 1 (data infra) | 0 (audit log) |
| 1 (market state) | 1 (data) |
| 2 (analogs) | 1 (market state) for `state_filter`, optionally 5 for `vol_z` |
| 3 (attribution) | 1 (data) for features + a calibrated classifier |
| 4 (risk) | 1 (data) for factor proxy returns; 0 (audit log) |
| 5 (stress) | nothing upstream; consumed by 2 + dashboard |
| 6 (portfolio) | 4 (exposures) + 2's covariance fitting style |
| 7 (hygiene) | 1 (data), 2 (disagreement), 3 (redundancy), 5 (friction) |
| 8 (journal) | data_infra (DuckDB) |
| 9 (calibration) | 8 (journal as polars frame) |
| 10 (sizing) | 2 (analog returns), 1 (state_uncertainty), 2 (overlap_pct) |
| dashboard (Phase 12) | DuckDB readers + every layer's persisted `ValidationReport` |
| layer_llm (Phase 13, optional) | dashboard packet builder; gated by `LLM_ENABLED` |

Note the implementation order for phases 6/7 inverts the layer numbering. The architecture (§21) requires Layer 6 to be built first so Layer 5 can be a clean float-only dependency. The Layer 2 engine accepts an optional `friction_monitor` constructor argument and pulls `vol_z` from it via `monitor.get_vol_z(ticker)` — no direct import of Layer 5 from Layer 2.

## Sign-off chain

A typical production sign-off proceeds:

1. Run survivorship audit on the active universe (`SurvivorshipAuditor.audit(...)`)
2. Run walk-forward CV (or CPCV when history allows) with a `signal_fn` that exercises the layer's primary output. Both record to the audit log atomically.
3. Compute Sharpe of the resulting OOS returns; extract skew + kurtosis.
4. Call `deflated_sharpe(sharpe, skew, kurt, n_obs, audit_log)`. The function reads `audit_log.trial_count()` internally — the caller never passes the count.
5. Build a `ValidationReport` populated with the four numbers + survivorship status.
6. Call `validate_layer(report)`. The function mutates `report.production_ready` and `report.rationale`.
7. Persist the report to `validation_reports` in the main DuckDB; cache it for the dashboard.
8. The decorator `requires_production(lambda: report)` wraps the layer's public methods so callers either get evidence or get a `ValidationGateError`.

## Persistent state

Two DuckDB files:

| File | Tables | Purpose |
|---|---|---|
| `data/db/main.duckdb` | `features_pit`, `delisted_tickers`, `paper_trade_performance`, `validation_reports`, `journal_entries`, `llm_cache` | feature store + trader journal + LLM cache |
| `data/db/audit.duckdb` | `backtest_executions` | monotonic trial counter for DSR |

The trial count is the **row count** of `backtest_executions`, not a separate counter column. A half-written insert cannot drift it.

Parquet snapshots at `data/cache/features/` are Snappy-compressed and are write-anywhere read-anywhere (no schema migration concerns).

## Component cross-references

The python package is laid out in [04_layers.md](04_layers.md). The on-disk schema is in [src/advisory/data_infra/schema.py](../src/advisory/data_infra/schema.py) — the single source of truth for DDL. No `CREATE TABLE` exists anywhere else in the codebase; the helper `bootstrap_schema(conn)` is idempotent.
