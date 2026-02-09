"""Codex process lifecycle and state management."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import uuid
from collections import OrderedDict
from datetime import datetime, timezone

from codex_listener.models import TaskCreate, TaskStatus

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages Codex CLI subprocess lifecycle and task state."""

    def __init__(
        self,
        max_concurrent: int = 4,
        max_completed: int = 50,
    ) -> None:
        self.max_concurrent = max_concurrent
        self.max_completed = max_completed
        self._tasks: dict[str, TaskStatus] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._completed: OrderedDict[str, TaskStatus] = OrderedDict()
        self._bg_tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def active_count(self) -> int:
        return sum(
            1 for t in self._tasks.values() if t.status in ("pending", "running")
        )

    def _gen_task_id(self) -> str:
        return uuid.uuid4().hex[:8]

    def get_task(self, task_id: str) -> TaskStatus | None:
        return self._tasks.get(task_id) or self._completed.get(task_id)

    def list_tasks(self, status_filter: str | None = None) -> list[TaskStatus]:
        all_tasks = list(self._tasks.values()) + list(self._completed.values())
        if status_filter:
            all_tasks = [t for t in all_tasks if t.status == status_filter]
        return sorted(all_tasks, key=lambda t: t.created_at, reverse=True)

    async def create_task(self, req: TaskCreate) -> TaskStatus:
        """Create and start a new Codex task."""
        if self.active_count >= self.max_concurrent:
            raise RuntimeError(
                f"Max concurrent tasks ({self.max_concurrent}) reached. "
                "Cancel or wait for a task to finish."
            )

        task_id = self._gen_task_id()
        now = datetime.now(timezone.utc)
        task = TaskStatus(
            task_id=task_id,
            status="pending",
            created_at=now,
        )
        self._tasks[task_id] = task

        bg = asyncio.create_task(self._run_task(task_id, req))
        self._bg_tasks[task_id] = bg
        return task

    async def cancel_task(self, task_id: str) -> TaskStatus | None:
        """Cancel a running or pending task."""
        task = self._tasks.get(task_id)
        if task is None:
            return None
        if task.status not in ("pending", "running"):
            return task

        proc = self._processes.get(task_id)
        if proc and proc.returncode is None:
            try:
                proc.send_signal(signal.SIGTERM)
                logger.info("Sent SIGTERM to task %s (pid %d)", task_id, proc.pid)
            except ProcessLookupError:
                pass

        # The _run_task coroutine will handle cleanup when the process exits.
        # But if it was still pending (never started), mark it directly.
        if task.status == "pending":
            task.status = "failed"
            task.error = "Cancelled before starting"
            task.completed_at = datetime.now(timezone.utc)
            self._archive_task(task_id)

        return task

    async def shutdown(self) -> None:
        """Cancel all running tasks and wait for them to finish."""
        for task_id in list(self._tasks):
            await self.cancel_task(task_id)

        # Wait for all background tasks to finish
        bg_tasks = list(self._bg_tasks.values())
        if bg_tasks:
            await asyncio.gather(*bg_tasks, return_exceptions=True)

    async def _run_task(self, task_id: str, req: TaskCreate) -> None:
        """Spawn codex subprocess and monitor its output."""
        task = self._tasks[task_id]
        cmd = self._build_command(req)

        logger.info("Starting task %s: %s", task_id, " ".join(cmd))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=req.cwd,
            )
        except FileNotFoundError:
            task.status = "failed"
            task.error = "codex CLI not found. Is it installed and on PATH?"
            task.completed_at = datetime.now(timezone.utc)
            self._archive_task(task_id)
            await self._notify(task)
            return
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc)
            self._archive_task(task_id)
            await self._notify(task)
            return

        self._processes[task_id] = proc
        task.status = "running"
        task.pid = proc.pid

        # Read JSONL output and extract the final agent message
        output = await self._read_codex_output(proc)

        exit_code = await proc.wait()
        task.exit_code = exit_code
        task.completed_at = datetime.now(timezone.utc)

        if exit_code == 0:
            task.status = "completed"
            task.output = output
        else:
            task.status = "failed"
            stderr_bytes = await proc.stderr.read() if proc.stderr else b""
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            task.error = (
                output or stderr_text or f"Exited with code {exit_code}"
            )

        logger.info(
            "Task %s finished: status=%s exit_code=%s",
            task_id,
            task.status,
            exit_code,
        )

        self._archive_task(task_id)
        self._processes.pop(task_id, None)
        self._bg_tasks.pop(task_id, None)

        await self._notify(task)

    async def _notify(self, task: TaskStatus) -> None:
        """Send Feishu notification with session details after task completion."""
        from codex_listener.config import get_feishu_config
        from codex_listener.feishu import send_feishu_notification
        from codex_listener.session_parser import get_session_summary

        feishu_cfg = get_feishu_config()
        if feishu_cfg is None:
            return

        # Parse the session JSONL to get detailed results
        summary = get_session_summary(task.created_at, task.completed_at)
        logger.info(
            "Notify task %s: summary=%s assistant_msg_len=%s",
            task.task_id,
            summary is not None,
            len(summary.last_assistant_message)
            if summary and summary.last_assistant_message
            else 0,
        )

        assistant_msg = (
            summary.last_assistant_message if summary else task.output
        )
        completed_at = (
            summary.completed_at
            if summary
            else (task.completed_at.isoformat() if task.completed_at else None)
        )

        logger.info("Sending Feishu notification for task %s", task.task_id)
        try:
            await send_feishu_notification(
                config=feishu_cfg,
                task_id=task.task_id,
                status=task.status,
                assistant_message=assistant_msg,
                total_tokens=(
                    summary.total_tokens if summary else None
                ),
                input_tokens=(
                    summary.input_tokens if summary else None
                ),
                output_tokens=(
                    summary.output_tokens if summary else None
                ),
                reasoning_tokens=(
                    summary.reasoning_tokens if summary else None
                ),
                completed_at=completed_at,
            )
        except Exception:
            logger.exception(
                "Feishu notification failed for task %s", task.task_id,
            )

    async def _read_codex_output(
        self, proc: asyncio.subprocess.Process,
    ) -> str | None:
        """Read and drain codex --json stdout, returning last message text."""
        if proc.stdout is None:
            return None

        last_message: str | None = None

        while True:
            line = await proc.stdout.readline()
            if not line:
                break

            text = line.decode(errors="replace").strip()
            if not text:
                continue

            try:
                event = json.loads(text)
            except json.JSONDecodeError:
                logger.debug("Non-JSON line from codex: %s", text[:200])
                continue

            # Extract final message from codex JSONL events.
            # codex --json emits item.completed events with message content.
            if (
                event.get("type") == "item.completed"
                and isinstance(event.get("item"), dict)
                and event["item"].get("type") == "message"
            ):
                content_parts = event["item"].get("content", [])
                texts = [
                    p.get("text", "")
                    for p in content_parts
                    if isinstance(p, dict) and p.get("type") == "output_text"
                ]
                msg = "\n".join(texts).strip()
                if msg:
                    last_message = msg

        return last_message

    def _build_command(self, req: TaskCreate) -> list[str]:
        """Build the codex exec command line."""
        cmd = [
            "codex",
            "exec",
            "--json",
            "--model", req.model,
            "--sandbox", req.sandbox,
            "-c", f"model_reasoning_effort=\"{req.reasoning_effort}\"",
        ]
        if req.full_auto:
            cmd.append("--full-auto")
        cmd.append(req.prompt)
        return cmd

    def _archive_task(self, task_id: str) -> None:
        """Move a finished task from active to completed history."""
        task = self._tasks.pop(task_id, None)
        if task is None:
            return
        self._completed[task_id] = task
        # Evict oldest if over limit
        while len(self._completed) > self.max_completed:
            self._completed.popitem(last=False)
