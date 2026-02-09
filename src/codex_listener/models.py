"""Pydantic models for Codex Listener API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TaskCreate(BaseModel):
    """Request body for creating a new Codex task."""

    prompt: str
    model: str = "gpt-5.3-codex"
    cwd: str = "."
    sandbox: str = "workspace-write"
    full_auto: bool = True
    reasoning_effort: str = "high"


class TaskStatus(BaseModel):
    """Status and result of a Codex task."""

    task_id: str
    status: Literal["pending", "running", "completed", "failed"]
    pid: int | None = None
    exit_code: int | None = None
    output: str | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class HealthResponse(BaseModel):
    """Health check response from the daemon."""

    status: str = "ok"
    pid: int
    active_tasks: int
    uptime_seconds: float
