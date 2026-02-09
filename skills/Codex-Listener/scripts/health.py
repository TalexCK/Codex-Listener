#!/usr/bin/env python3
"""Check codex-listener daemon health.

Usage:
    python scripts/health.py
"""

from __future__ import annotations

from codex_client import json_out, request


def main() -> None:
    result = request("GET", "/health")
    json_out(result)


if __name__ == "__main__":
    main()
