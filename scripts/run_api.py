#!/usr/bin/env python3
"""Launch the dashboard API (FastAPI + uvicorn).

    python scripts/run_api.py [--port 8000] [--reload]

The frontend dev server (``cd frontend && npm run dev``) proxies ``/api`` here.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Market Advisory dashboard API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable autoreload (requires PYTHONPATH=. so the reloader subprocess "
        "can import the app).",
    )
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "src.advisory.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
