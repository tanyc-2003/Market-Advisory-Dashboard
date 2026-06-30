"""HTTP API for the React dashboard.

A thin FastAPI layer that serves the dashboard's data as JSON. It wires
genuinely-real backend signals where they exist (run mode/settings, Kelly
cap, survivorship coverage, DSR audit trial count, and a persistent trade
journal) and serves the remaining layer outputs from :mod:`presentation`
— a single server-side source of truth that each layer can be swapped to
live compute against, one endpoint at a time.

The React app (``frontend/``) consumes ``GET /api/dashboard`` on load and
``POST /api/journal`` from the new-entry form.
"""
