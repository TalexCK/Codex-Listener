#!/usr/bin/env python3
"""Submit a new Codex task.

Usage:
    python scripts/submit.py --prompt "fix the bug" --cwd /path/to/project
    python scripts/submit.py --prompt "refactor auth" --model o3-mini --cwd .
"""

from __future__ import annotations

import argparse

from codex_client import json_out, request


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit a new Codex task")
    parser.add_argument("--prompt", required=True, help="Task prompt")
    parser.add_argument("--model", default=None, help="Model name")
    parser.add_argument("--cwd", default=None, help="Working directory for Codex")
    parser.add_argument(
        "--sandbox",
        default=None,
        help="Sandbox mode (default follows server-side setting)",
    )
    parser.add_argument(
        "--reasoning-effort", default=None,
        help="Reasoning effort: high, medium, or low (default: high)",
    )
    parser.add_argument(
        "--workflow-mode",
        default=None,
        choices=["normal", "plan_bridge"],
        help="Workflow mode (normal or plan_bridge)",
    )
    parser.add_argument(
        "--resume-session",
        default=None,
        help="Resume an existing Codex session ID",
    )
    parser.add_argument(
        "--parent-task-id",
        default=None,
        help="Parent task id when continuing a plan bridge flow",
    )
    args = parser.parse_args()

    body: dict = {"prompt": args.prompt, "full_auto": True}
    if args.model:
        body["model"] = args.model
    if args.cwd:
        body["cwd"] = args.cwd
    if args.sandbox:
        body["sandbox"] = args.sandbox
    if args.reasoning_effort:
        body["reasoning_effort"] = args.reasoning_effort
    if args.workflow_mode:
        body["workflow_mode"] = args.workflow_mode
    if args.resume_session:
        body["resume_session_id"] = args.resume_session
    if args.parent_task_id:
        body["parent_task_id"] = args.parent_task_id

    result = request("POST", "/tasks", body)
    json_out(result)


if __name__ == "__main__":
    main()
