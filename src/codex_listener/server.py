"""FastAPI HTTP server for Codex Listener."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import time

import uvicorn
from fastapi import FastAPI, HTTPException, Query

from codex_listener.models import HealthResponse, TaskCreate, TaskStatus
from codex_listener.task_manager import TaskManager

logger = logging.getLogger(__name__)

_start_time: float = time.monotonic()

app = FastAPI(title="Codex Listener", version="0.1.0")
task_manager = TaskManager()


# -- Lifecycle ----------------------------------------------------------------


@app.on_event("startup")
async def _on_startup() -> None:
    global _start_time  # noqa: PLW0603
    _start_time = time.monotonic()
    logger.info("Codex Listener server started (PID %d)", os.getpid())


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    logger.info("Shutting down — cancelling active tasks…")
    await task_manager.shutdown()
    logger.info("Codex Listener server stopped")


# -- Endpoints ----------------------------------------------------------------


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(
        pid=os.getpid(),
        active_tasks=task_manager.active_count,
        uptime_seconds=round(time.monotonic() - _start_time, 2),
    )


@app.post("/tasks", status_code=202)
async def create_task(req: TaskCreate) -> TaskStatus:
    try:
        task = await task_manager.create_task(req)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    return task


@app.get("/tasks")
async def list_tasks(
    status: str | None = Query(default=None),
) -> list[TaskStatus]:
    return task_manager.list_tasks(status_filter=status)


@app.get("/tasks/{task_id}")
async def get_task(task_id: str) -> TaskStatus:
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str) -> TaskStatus:
    task = await task_manager.cancel_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# -- Entrypoint (called by daemon.py via `python -m codex_listener.server`) ---


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _handle_sigterm(
    _signum: int,
    _frame: object,
) -> None:
    raise SystemExit(0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=19823)
    args = parser.parse_args()

    _setup_logging()

    # Allow graceful shutdown on SIGTERM (sent by daemon.stop())
    signal.signal(signal.SIGTERM, _handle_sigterm)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
