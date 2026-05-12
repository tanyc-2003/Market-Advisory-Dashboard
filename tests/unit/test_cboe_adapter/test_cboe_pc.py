"""V7_lite Phase 2: CBOE put/call ratio adapter (no network)."""
from __future__ import annotations

from datetime import date

import duckdb
import pytest

from src.advisory.data_infra.cboe_adapter import CBOEAdapter
from src.advisory.data_infra.schema import bootstrap_schema


@pytest.fixture
def adapter():
    conn = duckdb.connect(":memory:")
    bootstrap_schema(conn)
    return CBOEAdapter(conn)


def test_returns_cached_ratio(adapter):
    adapter.write_rows([(date(2024, 6, 3), 0.85)])
    assert adapter.fetch_put_call_ratio(date(2024, 6, 3)) == pytest.approx(0.85)


def test_returns_none_for_missing_date(adapter):
    assert adapter.fetch_put_call_ratio(date(2024, 6, 4)) is None


def test_write_rows_idempotent(adapter):
    n1 = adapter.write_rows([(date(2024, 6, 3), 0.85), (date(2024, 6, 4), 0.90)])
    n2 = adapter.write_rows([(date(2024, 6, 3), 0.87)])  # overwrite same date
    total = adapter.conn.execute("SELECT COUNT(*) FROM cboe_pc_ratio").fetchone()[0]
    assert n1 == 2
    assert n2 == 1
    assert total == 2
    assert adapter.fetch_put_call_ratio(date(2024, 6, 3)) == pytest.approx(0.87)
