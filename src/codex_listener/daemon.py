"""Daemon lifecycle management (start/stop/status)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 19823
STATE_DIR = Path.home() / ".codex-listener"
PID_FILE = STATE_DIR / "codex-listener.pid"
LOG_DIR = STATE_DIR / "logs"
LOG_FILE = LOG_DIR / "codex-listener.log"


def _ensure_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _read_pid() -> int | None:
    """Read PID from file, return None if missing or stale."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None
    # Check if process is alive
    try:
        os.kill(pid, 0)
    except OSError:
        # Process not running, clean up stale PID file
        PID_FILE.unlink(missing_ok=True)
        return None
    return pid


def is_running() -> int | None:
    """Return the daemon PID if running, else None."""
    return _read_pid()


def start(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    """Launch the daemon in the background. Returns the PID."""
    existing = _read_pid()
    if existing is not None:
        raise RuntimeError(f"Daemon already running (PID {existing})")

    _ensure_dirs()

    # Launch a new Python process that runs the server module
    log_fh = open(LOG_FILE, "a")  # noqa: SIM115
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "codex_listener.server",
            "--host", host,
            "--port", str(port),
        ],
        stdout=log_fh,
        stderr=log_fh,
        start_new_session=True,
    )

    PID_FILE.write_text(str(proc.pid))

    # Wait briefly to check it didn't crash immediately
    time.sleep(0.5)
    if proc.poll() is not None:
        PID_FILE.unlink(missing_ok=True)
        raise RuntimeError(
            f"Daemon exited immediately (code {proc.returncode}). "
            f"Check logs: {LOG_FILE}"
        )

    return proc.pid


def stop(timeout: float = 5.0) -> bool:
    """Stop the daemon. Returns True if it was stopped, False if wasn't running."""
    pid = _read_pid()
    if pid is None:
        return False

    os.kill(pid, signal.SIGTERM)

    # Wait for process to exit
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(0.1)
    else:
        # Still alive after timeout, force kill
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    PID_FILE.unlink(missing_ok=True)
    return True


def status() -> dict:
    """Return daemon status info."""
    pid = _read_pid()
    if pid is None:
        return {"running": False}
    return {
        "running": True,
        "pid": pid,
        "log_file": str(LOG_FILE),
        "pid_file": str(PID_FILE),
    }
