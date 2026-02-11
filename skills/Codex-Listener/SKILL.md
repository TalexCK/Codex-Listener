---
name: codex
description: Delegate coding tasks to OpenAI Codex via codex-listener
allowed-tools: Bash(python3 *)
---

# Codex Skill

Delegate coding tasks to OpenAI Codex CLI through the codex-listener daemon.

## IMPORTANT RULES

1. **Submit only.** After submitting a task, immediately move on to other work. Do NOT poll, wait, or check the task status.
2. **No polling.** Do NOT call `status.py` or `list_tasks.py` after submitting unless the user explicitly asks you to check a task's status.
3. **Notification is automatic.** The daemon will notify the user through the configured messaging channel(s) (Feishu/Telegram) when the task finishes. You will NOT receive the result — just move on.
4. **Use official submit path only.** Always use `scripts/submit.py` (or `POST /tasks` for manual HTTP). Do NOT use `/submit` or any other unofficial endpoint.
5. **Status source of truth.** Task status must come only from `/tasks` APIs via `scripts/status.py` or `scripts/list_tasks.py`.
6. **No inferred excuses.** If status query fails, report the raw JSON error and stop guessing. Do NOT claim "权限受限/系统拦截" unless the tool output explicitly says so.
7. **No shell fallbacks for status.** Do NOT append `2>/dev/null`, `|| echo`, or pipes that change script output.
8. **Do not use artifacts as status proxy.** Do NOT inspect `.codex/sessions` or output files to infer task state unless the user explicitly asks to verify deliverables.
9. **Current default sandbox is privileged.** Server default is `danger-full-access`. If lower privilege is needed, explicitly pass `--sandbox workspace-write`.
10. **System tasks must include acceptance checks in the same prompt.** For installs/services/users/permissions, require "execute + verify + report verification output".
11. **Complex tasks must enter PlanMode first.** Trigger PlanMode if any of: write/delete files >=2, any delete/overwrite/batch replace, estimated steps >=5, or system-level changes (packages/services/permissions/env).
12. **Use Plan Bridge for multi-turn planning.** Submit stage-A with `--workflow-mode plan_bridge`; if result is `bridge_stage=needs_input`, collect user answers and continue with `--resume-session` (stage-B). Do not execute implementation until plan is ready.

## Prerequisites

The daemon must be running:

```bash
codex-listener start
```

All scripts are in the `scripts/` directory relative to this skill.

## Workflow

```bash
# 1. Submit a task (canonical path: POST /tasks via submit.py)
python3 scripts/submit.py --prompt "fix the type error in auth.py" --cwd /path/to/project
# Returns: {"task_id": "a1b2c3d4", "status": "pending", ...}

# 2. Done. Move on to other work. The user will be notified through their configured channels when codex finishes.
```

Plan Bridge (two-stage):

```bash
# Stage A: ask planning questions only
python3 scripts/submit.py \
  --workflow-mode plan_bridge \
  --prompt "Complex task: ask only clarifying questions first, then emit planmode.v1 JSON with stage=needs_input." \
  --cwd /home/Hera/.nanobot/workspace

# Stage B: continue same session after user answers
python3 scripts/submit.py \
  --workflow-mode plan_bridge \
  --resume-session <session_id> \
  --parent-task-id <task_id> \
  --prompt "User answers: ... Continue planning and emit planmode.v1 JSON." \
  --cwd /home/Hera/.nanobot/workspace
```

System-task prompt template (required):

```text
Install tmux on Debian/Ubuntu, then verify with:
1) tmux -V
2) dpkg -l tmux
Return the exact verification output in your final response.
```

## Scripts

### Submit a task

```bash
python3 scripts/submit.py --prompt "fix the bug in auth.py" --cwd /path/to/project
python3 scripts/submit.py --prompt "refactor this module" --model o3-mini --cwd .
python3 scripts/submit.py --prompt "quick fix" --reasoning-effort low --cwd .
python3 scripts/submit.py --prompt "install tmux and verify with tmux -V + dpkg -l tmux" --cwd /home/Hera/.nanobot/workspace
python3 scripts/submit.py --prompt "code-only task" --sandbox workspace-write --cwd /home/Hera/.nanobot/workspace
python3 scripts/submit.py --workflow-mode plan_bridge --prompt "ask questions first" --cwd /home/Hera/.nanobot/workspace
python3 scripts/submit.py --workflow-mode plan_bridge --resume-session <session_id> --parent-task-id <task_id> --prompt "answers: ..." --cwd /home/Hera/.nanobot/workspace
```

The script above sends requests to `POST /tasks`. Do not hand-write `/submit`.

Options: `--prompt` (required), `--model`, `--cwd`, `--sandbox`, `--reasoning-effort` (high/medium/low, default: high), `--workflow-mode`, `--resume-session`, `--parent-task-id`

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

Status handling:
- If success: report `status` directly from JSON.
- If error: copy the `error` field verbatim, then run `python3 scripts/health.py` once and report result.
- Do not switch to guessed narratives.

Plan Bridge handling:
- If `bridge_stage=needs_input`: ask user for answers. Preferred reply format is `/plan-reply <task_id> <answer>`.
- Natural-language reply is allowed only when there is exactly one pending `needs_input` task; otherwise require explicit `/plan-reply`.
- Continue by resubmitting with `--resume-session <session_id>` and `--parent-task-id <task_id>`.
- Telegram button semantics:
  - `✍️ 回复问题`: only pre-fills `/plan-reply <task_id> `, user must still send the final answer text.
  - `✅ 执行计划`: requires second confirmation before creating execution task.
  - `📝 继续修改`: route back to `/plan-reply <task_id> ...`.
  - `❌ 取消`: cancel current execution intent and do not auto-submit implementation.

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
