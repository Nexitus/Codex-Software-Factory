#!/usr/bin/env python3
"""Start the local factory dashboard on loopback."""
from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from app.server import create_app


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local software factory dashboard")
    parser.add_argument("--demo", action="store_true", help="Use an isolated SQLite demo with no model calls")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, help="Optional SQLite event database")
    parser.add_argument("--projects", type=Path, help="Optional projects allowlist JSON")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    app = create_app(db_path=args.db, projects_path=args.projects, demo=args.demo, port=args.port)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
