"""Streamlit dashboard for the Advisory Market Intelligence system.

The dashboard reads pre-computed results from DuckDB and Parquet
snapshots; it never runs heavy computation in Streamlit callbacks.
Every page checks the relevant layer's :class:`ValidationReport` before
rendering content.
"""
