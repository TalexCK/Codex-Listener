"""Skill CLI subcommands for AI agent integration.

All output is structured JSON to stdout. Uses only stdlib (urllib.request)
to communicate with the codex-listener daemon HTTP API.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

from codex_listener.daemon import DEFAULT_HOST, DEFAULT_PORT

_BASE_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"

# Bypass system proxy for localhost requests (macOS picks up system
# proxy settings which causes 502 errors for localhost connections).
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _json_out(data: dict | list) -> None:
    """Print JSON to stdout and exit 0."""
    print(json.dumps(data, default=str))
    sys.exit(0)


def _json_err(message: str) -> None:
    """Print JSON error to stdout and exit 1."""
    print(json.dumps({"error": message}))
    sys.exit(1)


def _request(
    method: str,
    path: str,
    body: dict | None = None,
) -> dict | list:
    """Make an HTTP request to the daemon API. Returns parsed JSON."""
    url = f"{_BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}

    req = urllib.request.Request(
        url, data=data, headers=headers, method=method,
    )
    try:
        with _opener.open(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode())
        except Exception:
            detail = {"detail": e.reason}
        _json_err(detail.get("detail", str(detail)))
    except urllib.error.URLError:
        _json_err(
            "codex-listener is not running. "
            "Start it with: codex-listener start"
        )
    return {}  # unreachable, _json_err calls sys.exit


# -- Subcommands --------------------------------------------------------------


def _cmd_submit(args: argparse.Namespace) -> None:
    body: dict = {"prompt": args.prompt}
    if args.model:
        body["model"] = args.model
    if args.cwd:
        body["cwd"] = args.cwd
    if args.sandbox:
        body["sandbox"] = args.sandbox
    body["full_auto"] = args.full_auto

    result = _request("POST", "/tasks", body)
    _json_out(result)


def _cmd_status(args: argparse.Namespace) -> None:
    result = _request("GET", f"/tasks/{args.task_id}")
    _json_out(result)


def _cmd_list(args: argparse.Namespace) -> None:
    path = "/tasks"
    if args.status:
        path += f"?status={args.status}"
    tasks = _request("GET", path)
    _json_out({"tasks": tasks})


def _cmd_cancel(args: argparse.Namespace) -> None:
    result = _request("DELETE", f"/tasks/{args.task_id}")
    _json_out(result)


def _cmd_wait(args: argparse.Namespace) -> None:
    deadline = time.monotonic() + args.timeout
    while True:
        result = _request("GET", f"/tasks/{args.task_id}")
        if isinstance(result, dict) and result.get("status") in (
            "completed",
            "failed",
        ):
            _json_out(result)

        if time.monotonic() >= deadline:
            _json_err(
                f"Timed out after {args.timeout}s waiting for "
                f"task {args.task_id}"
            )

        time.sleep(args.poll_interval)


def _cmd_health(_args: argparse.Namespace) -> None:
    result = _request("GET", "/health")
    _json_out(result)


# -- Parser setup (called from cli.py) ----------------------------------------


def add_skill_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the 'skill' subcommand and its sub-subcommands."""
    skill_parser = subparsers.add_parser(
        "skill",
        help="AI agent skill commands (JSON output)",
    )
    skill_sub = skill_parser.add_subparsers(dest="skill_command")

    # submit
    p = skill_sub.add_parser("submit", help="Submit a new task")
    p.add_argument("--prompt", required=True, help="Task prompt")
    p.add_argument("--model", default=None, help="Model name")
    p.add_argument("--cwd", default=None, help="Working directory")
    p.add_argument(
        "--sandbox", default=None, help="Sandbox mode",
    )
    p.add_argument(
        "--full-auto", action="store_true", default=True,
        help="Run in full-auto mode (default: true)",
    )
    p.add_argument(
        "--no-full-auto",
        action="store_false", dest="full_auto",
        help="Disable full-auto mode",
    )
    p.set_defaults(func=_cmd_submit)

    # status
    p = skill_sub.add_parser("status", help="Check task status")
    p.add_argument("--task-id", required=True, help="Task ID")
    p.set_defaults(func=_cmd_status)

    # list
    p = skill_sub.add_parser("list", help="List all tasks")
    p.add_argument(
        "--status", default=None,
        help="Filter by status (pending/running/completed/failed)",
    )
    p.set_defaults(func=_cmd_list)

    # cancel
    p = skill_sub.add_parser("cancel", help="Cancel a task")
    p.add_argument("--task-id", required=True, help="Task ID")
    p.set_defaults(func=_cmd_cancel)

    # wait
    p = skill_sub.add_parser(
        "wait", help="Wait for a task to complete",
    )
    p.add_argument("--task-id", required=True, help="Task ID")
    p.add_argument(
        "--timeout", type=int, default=300,
        help="Timeout in seconds (default: 300)",
    )
    p.add_argument(
        "--poll-interval", type=int, default=5,
        help="Poll interval in seconds (default: 5)",
    )
    p.set_defaults(func=_cmd_wait)

    # health
    p = skill_sub.add_parser("health", help="Check daemon health")
    p.set_defaults(func=_cmd_health)

    skill_parser.set_defaults(
        func=lambda args: skill_parser.print_help() or sys.exit(1),
    )
