# 07 — Dashboard (Phase 12)

## Running it

```powershell
python scripts/run_validation.py            # populate validation_reports first
streamlit run src/advisory/dashboard/app.py
```

Open `http://localhost:8501`. The first page you should see is the **Validation** page — every other page is gated on the Layer 0 sign-off shown there.

> **If every layer shows `no_report`**, you skipped `scripts/run_validation.py`. The dashboard does not invent reports; it reads them from DuckDB. See [05_running.md](05_running.md#populate-validation-reports) for what the script does.

## The eight pages

| # | Page | Layer |
|---|---|---|
| 1 | Validation | Layer 0 — status table for every layer |
| 2 | Market State | Layer 1 — state probabilities, dominant state, transition signal |
| 3 | Watchlist | Layers 2, 3, 7 — analogs, attribution, decision hygiene |
| 4 | Portfolio | Layer 6 — weights, stress scenarios, clusters |
| 5 | Sizing | Layer 10 — tail-aware Kelly, 20% cap displayed prominently |
| 6 | Journal | Layer 8 — entry form, open trades, close trade |
| 7 | Calibration | Layer 9 — reliability diagram, Brier, ECE, thesis drift |
| 8 | Query (LLM) | Layer 9-llm — hidden unless `LLM_ENABLED=true` in `.env` |

## Validation gate behaviour

Every layer page calls `get_validation_report(conn, "layerN")` before rendering content and follows the same pattern:

```python
if report.status == "blocked":
    render_blocked_output(layer_name, rationale)
    return
if report.status == "research_preview":
    render_research_preview_banner(layer_name, rationale)
```

- `production` (🟢) — the layer renders normally.
- `research_preview` (🟡) — a yellow banner appears above the layer's section carrying the headline `"Research preview — not validated for live decision support."` plus the report's rationale.
- `blocked` (🔴) — the layer's section is **hidden entirely** and a red message explains why.
- `no_report` (⚪) — the dashboard renders the page but with an info banner indicating no validation report has been persisted yet. Run `scripts/run_validation.py` (or the per-layer validation scripts when Phase 14 lands) to populate one.

## Session state

All access to `st.session_state` is centralised in [src/advisory/dashboard/state.py](../src/advisory/dashboard/state.py). The default keys are:

| Key | Type | Purpose |
|---|---|---|
| `selected_ticker` | `str \| None` | Asset currently focused on the Watchlist page |
| `portfolio_weights` | `dict[str, float]` | Current portfolio (Portfolio page) |
| `journal_open_trades` | `list` | Open journal entries (Journal page) |
| `as_of_date` | `date` | Snapshot date for staleness banner |
| `llm_enabled` | `bool` | Mirrors `settings.llm_enabled` — synced on every init |
| `active_layer_reports` | `dict[str, ValidationReport]` | Cached ValidationReports |
| `last_market_state` | `StateObservation \| None` | Set by upstream pipeline; consumed by pages 2 + 5 |
| `last_analog_result` | `AnalogResult \| None` | Set by upstream pipeline; consumed by pages 3 + 5 |

Pages never touch `st.session_state["key"]` directly — they always call a helper. This keeps the contract centralised and lets tests plug in a plain dict.

## Reusable components

### `render_validation_badge(report)`
Renders a status pill with the architecture-pinned emoji + label, tooltip showing the rationale. Use it in tables and at the top of layer sections.

### `render_research_preview_banner(layer_name, rationale)`
The full yellow banner with `RESEARCH_PREVIEW_HEADLINE` as the bold line.

### `render_blocked_output(layer_name, rationale)`
The red message with the architecture-pinned `BLOCKED_MESSAGE_TEMPLATE`. The layer's section is otherwise empty.

### `render_analog_return_distribution(global, within_state, label, n_global, n_within)`
Plotly overlay histogram with p5 / p25 / p50 markers. Pass `within_state_returns=None` to render only the global trace.

### `render_disagreement_banner(overlap_pct, note)`
Fires only when `overlap_pct < DISAGREEMENT_OVERLAP_FLOOR` (default 0.70). Uses the exact note string returned by `HistoricalAnalogEngine.find_analogs_with_disagreement`.

### `render_unknowns_section(unknowns)`
Collapsed expander titled `"⚠️ What This System Does Not Know"`. Render at the bottom of every layer section.

## Stale-data banner

The sidebar reads `st.session_state["as_of_date"]` and renders a yellow warning when it is more than 2 trading days behind `date.today()`. The check is in [services.py:is_data_stale](../src/advisory/dashboard/services.py).

## Heavy computation policy

The dashboard never runs CPCV, HMM training, or backtest fitting in a Streamlit callback. Those run in `scripts/` (Phase 14) and persist results to DuckDB / Parquet; the dashboard reads them. Wrap any DB read with `@st.cache_data` to keep page renders snappy.

## Disabling the LLM page

`pages/8_query.py` calls `st.stop()` immediately when `settings.llm_enabled is False` so the page renders only an info banner. To truly remove it from the sidebar navigation, delete the file or move it outside the `pages/` directory — by default Streamlit treats every file in `pages/` as a navigable page.
