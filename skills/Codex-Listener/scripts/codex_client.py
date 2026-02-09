"""HTTP client for communicating with the codex-listener daemon.

Shared by all skill scripts. Uses only stdlib (urllib.request).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:19823"

# Bypass macOS system proxy for localhost connections.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(method: str, path: str, body: dict | None = None) -> dict | list:
    """Make an HTTP request to the daemon. Returns parsed JSON."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with _opener.open(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode())
        except Exception:
            detail = {"detail": e.reason}
        json_err(detail.get("detail", str(detail)))
    except urllib.error.URLError:
        json_err(
            "codex-listener is not running. Start it with: codex-listener start"
        )
    return {}  # unreachable


def json_out(data: dict | list) -> None:
    """Print JSON to stdout and exit 0."""
    print(json.dumps(data, default=str))
    sys.exit(0)


def json_err(message: str) -> None:
    """Print JSON error to stdout and exit 1."""
    print(json.dumps({"error": message}))
    sys.exit(1)
