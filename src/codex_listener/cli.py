"""CLI entry point for codex-listener."""

from __future__ import annotations

import argparse
import subprocess
import sys

from codex_listener import __version__
from codex_listener.daemon import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    LOG_FILE,
)
from codex_listener.daemon import start as daemon_start
from codex_listener.daemon import status as daemon_status
from codex_listener.daemon import stop as daemon_stop
from codex_listener.skill import add_skill_parser


def _cmd_start(args: argparse.Namespace) -> None:
    try:
        pid = daemon_start(host=args.host, port=args.port)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"codex-listener started (PID {pid}, port {args.port})")


def _cmd_stop(_args: argparse.Namespace) -> None:
    stopped = daemon_stop()
    if stopped:
        print("codex-listener stopped")
    else:
        print("codex-listener is not running")


def _cmd_status(_args: argparse.Namespace) -> None:
    info = daemon_status()
    if not info["running"]:
        print("codex-listener is not running")
        return
    print(f"codex-listener is running (PID {info['pid']})")
    print(f"  Log file: {info['log_file']}")


def _cmd_logs(args: argparse.Namespace) -> None:
    if not LOG_FILE.exists():
        print("No log file found", file=sys.stderr)
        sys.exit(1)

    if args.follow:
        try:
            subprocess.run(
                ["tail", "-f", str(LOG_FILE)],
                check=False,
            )
        except KeyboardInterrupt:
            pass
    else:
        n = args.lines
        subprocess.run(
            ["tail", "-n", str(n), str(LOG_FILE)],
            check=False,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="codex-listener",
        description="Manage the Codex Listener daemon",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    sub = parser.add_subparsers(dest="command")

    # start
    p_start = sub.add_parser("start", help="Start the daemon")
    p_start.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )
    p_start.add_argument(
        "--host", default=DEFAULT_HOST,
        help=f"Host to bind to (default: {DEFAULT_HOST})",
    )
    p_start.set_defaults(func=_cmd_start)

    # stop
    p_stop = sub.add_parser("stop", help="Stop the daemon")
    p_stop.set_defaults(func=_cmd_stop)

    # status
    p_status = sub.add_parser("status", help="Show daemon status")
    p_status.set_defaults(func=_cmd_status)

    # logs
    p_logs = sub.add_parser("logs", help="View daemon logs")
    p_logs.add_argument(
        "-f", "--follow", action="store_true",
        help="Follow log output in real-time",
    )
    p_logs.add_argument(
        "-n", "--lines", type=int, default=50,
        help="Number of lines to show (default: 50)",
    )
    p_logs.set_defaults(func=_cmd_logs)

    # skill (Phase 4)
    add_skill_parser(sub)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
