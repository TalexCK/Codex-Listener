---
name: codex
description: Delegate coding tasks to OpenAI Codex via codex-listener
allowed-tools: Bash(python3 *)
---

# Codex Skill

Delegate coding tasks to OpenAI Codex CLI through the codex-listener daemon. Codex runs in full-auto mode within a restricted working directory.

## IMPORTANT RULES

1. **Submit only.** After submitting a task, immediately move on to other work. Do NOT poll, wait, or check the task status.
2. **No polling.** Do NOT call `status.py` or `list_tasks.py` after submitting unless the user explicitly asks you to check a task's status.
3. **Notification is automatic.** The daemon will notify the user through the configured messaging channel(s) (Feishu/Telegram) when the task finishes. You will NOT receive the result — just move on.

## Prerequisites

The daemon must be running:

```bash
codex-listener start
```

All scripts are in the `scripts/` directory relative to this skill.

## Workflow

```bash
# 1. Submit a task — returns immediately (reasoning_effort defaults to high)
python3 scripts/submit.py --prompt "fix the type error in auth.py" --cwd /path/to/project
# Returns: {"task_id": "a1b2c3d4", "status": "pending", ...}

# 2. Done. Move on to other work. The user will be notified through their configured channels when codex finishes.
```

## Scripts

### Submit a task

```bash
python3 scripts/submit.py --prompt "fix the bug in auth.py" --cwd /path/to/project
python3 scripts/submit.py --prompt "refactor this module" --model o3-mini --cwd .
python3 scripts/submit.py --prompt "quick fix" --reasoning-effort low --cwd .
```

Options: `--prompt` (required), `--model`, `--cwd`, `--sandbox`, `--reasoning-effort` (high/medium/low, default: high)

### Cancel a task

```bash
python3 scripts/cancel.py --task-id <id>
```

### Health check

```bash
python3 scripts/health.py
```

### Check task status (only when user asks)

```bash
python3 scripts/status.py --task-id <id>
python3 scripts/list_tasks.py
```

## Output Format

All scripts output a single JSON object to stdout. Exit code 0 = success, 1 = error.

Submitted task:
```json
{"task_id": "a1b2c3d4", "status": "pending", ...}
```

Daemon not running:
```json
{"error": "codex-listener is not running. Start it with: codex-listener start"}
```
