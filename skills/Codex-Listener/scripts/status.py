#!/usr/bin/env python3
"""Check the status of a Codex task.

Usage:
    python scripts/status.py --task-id abc12345
"""

from __future__ import annotations

import argparse

from codex_client import json_out, request


def main() -> None:
    parser = argparse.ArgumentParser(description="Check task status")
    parser.add_argument("--task-id", required=True, help="Task ID")
    args = parser.parse_args()

    result = request("GET", f"/tasks/{args.task_id}")
    json_out(result)


if __name__ == "__main__":
    main()
