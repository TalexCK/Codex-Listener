# Codex-Listener

A daemon that lets AI agents (Claude, ChatGPT, etc.) orchestrate [OpenAI Codex CLI](https://github.com/openai/codex) tasks. Submit coding tasks, track progress, and collect results — all through simple shell commands that any AI can call.

## Architecture

```
AI Agent  ──  scripts/*.py (submit)  ──▶  codex-listener daemon (FastAPI)
User     ◀── Feishu Bot card                              │
                                                          │ subprocess
                                                          ▼
                                                  codex exec --json --full-auto
```

AI agents run standalone Python scripts via their shell tool. Each script talks to the daemon over HTTP on localhost and prints structured JSON to stdout. No curl or HTTP knowledge needed in prompts.

## Installation

```bash
# From source
uv pip install -e .

# Verify
codex-listener --version
```

Requires Python 3.10+ and [OpenAI Codex CLI](https://github.com/openai/codex) on PATH.

## Quick Start

```bash
# Start the daemon
uv run codex-listener start

# Submit a task (fire-and-forget — daemon notifies user via Feishu on completion)
python3 skills/Codex-Listener/scripts/submit.py --prompt "fix the bug in auth.py" --cwd /path/to/project

# Stop the daemon
uv run codex-listener stop
```

## Daemon Management

```bash
uv run codex-listener start [--port 19823] [--host 127.0.0.1]   # Start daemon
uv run codex-listener stop                                        # Stop daemon
uv run codex-listener status                                      # Check if running
uv run codex-listener logs [-f] [-n 50]                           # View logs
```

## AI Skill Scripts

Standalone Python scripts in `skills/Codex-Listener/scripts/` for AI agents to submit tasks to the daemon. All output a single JSON object to stdout. Exit code 0 = success, 1 = error. The daemon notifies the user via Feishu Bot on completion.

```bash
python3 skills/Codex-Listener/scripts/submit.py --prompt "..." [--model gpt-5.3-codex] [--cwd .] [--sandbox workspace-write]
python3 skills/Codex-Listener/scripts/status.py --task-id <id>
python3 skills/Codex-Listener/scripts/list_tasks.py [--status running]
python3 skills/Codex-Listener/scripts/cancel.py --task-id <id>
python3 skills/Codex-Listener/scripts/health.py
```

## Configuration

Config file: `~/.codex-listener/config.json` (auto-created on first run).

```json
{
  "feishu": {
    "enabled": true,
    "appId": "cli_xxxx",
    "appSecret": "xxxxx",
    "encryptKey": "",
    "verificationToken": "",
    "allowFrom": ["ou_xxxx"]
  }
}
```

**`feishu`** — Feishu Bot notification settings. When a task completes or fails, the daemon parses the Codex session JSONL (extracting the last assistant message, token usage, and completion time) and sends an interactive card to the configured recipients.

| Field | Description |
|-------|-------------|
| `enabled` | Set to `true` to enable Feishu notifications |
| `appId` | Feishu app ID (from [Feishu Open Platform](https://open.feishu.cn)) |
| `appSecret` | Feishu app secret |
| `encryptKey` | Event encryption key (optional, for webhook verification) |
| `verificationToken` | Event verification token (optional) |
| `allowFrom` | List of Feishu `open_id`s to receive notifications |

## AI Integration

Copy the skill file for your AI tool:

- **Claude Code**: Copy `skills/Codex-Listener/SKILL.md` to your project's `.claude/skills/` directory.

The skill file teaches the AI how to use the Python scripts in `skills/Codex-Listener/scripts/`.

## Testing

See [TEST.md](TEST.md) for manual test procedures covering daemon operations and AI skill commands.

## Project Structure

```
src/codex_listener/
├── __init__.py          # Package version
├── cli.py               # CLI entry point (start/stop/status/logs)
├── daemon.py            # Daemon lifecycle (PID file, background process)
├── server.py            # FastAPI HTTP server
├── task_manager.py      # Codex subprocess lifecycle & state management
├── models.py            # Pydantic models (TaskCreate, TaskStatus, etc.)
├── config.py            # Configuration loading (~/.codex-listener/config.json)
├── session_parser.py    # Parse Codex session JSONL for results & token usage
└── feishu.py            # Feishu Bot API (send card notifications)

skills/Codex-Listener/
├── SKILL.md             # AI skill definition
└── scripts/
    ├── codex_client.py  # Shared HTTP client (stdlib only)
    ├── submit.py        # Submit a task (fire-and-forget)
    ├── status.py        # Check task status (optional)
    ├── list_tasks.py    # List tasks (optional)
    ├── cancel.py        # Cancel a task
    └── health.py        # Daemon health check
```
