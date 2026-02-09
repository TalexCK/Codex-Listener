#!/usr/bin/env python3
"""List all Codex tasks.

Usage:
    python scripts/list_tasks.py
    python scripts/list_tasks.py --status running
"""

from __future__ import annotations

import argparse

from codex_client import json_out, request


def main() -> None:
    parser = argparse.ArgumentParser(description="List all tasks")
    parser.add_argument(
        "--status", default=None,
        help="Filter by status (pending/running/completed/failed)",
    )
    args = parser.parse_args()

    path = "/tasks"
    if args.status:
        path += f"?status={args.status}"
    tasks = request("GET", path)
    json_out({"tasks": tasks})


if __name__ == "__main__":
    main()
