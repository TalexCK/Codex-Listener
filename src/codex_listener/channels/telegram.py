"""Telegram Bot notification via Bot API (stdlib only)."""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from functools import partial

from codex_listener.config import TelegramConfig

logger = logging.getLogger(__name__)


def _build_api_url(token: str, method: str) -> str:
    """Build Telegram Bot API URL."""
    return f"https://api.telegram.org/bot{token}/{method}"


def _send_message(
    token: str,
    chat_id: str,
    text: str,
    proxy: str | None = None,
) -> bool:
    """Send a text message to a specific chat."""
    url = _build_api_url(token, "sendMessage")
    body = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
    }).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    # Set up proxy if provided
    if proxy:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        opener = urllib.request.build_opener(proxy_handler)
        urllib.request.install_opener(opener)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if not data.get("ok"):
            logger.warning(
                "Telegram send failed to %s: %s",
                chat_id,
                data.get("description"),
            )
            return False
        return True
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        logger.warning("Telegram send request failed to %s: %s", chat_id, e)
        return False


def _escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


def _build_message(
    task_id: str,
    status: str,
    assistant_message: str | None,
    total_tokens: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    reasoning_tokens: int | None,
    completed_at: str | None,
) -> str:
    """Build Telegram message with Markdown formatting."""
    is_ok = status == "completed"
    status_emoji = "✅" if is_ok else "❌"
    
    lines = [
        f"{status_emoji} *Codex Task {_escape_markdown_v2(task_id)}*",
        "",
        f"*Status:* {_escape_markdown_v2(status)}",
    ]
    
    if completed_at:
        lines.append(f"*Completed:* {_escape_markdown_v2(completed_at)}")
    
    lines.append("")
    lines.append("─" * 30)
    lines.append("")
    
    # Assistant message
    if assistant_message:
        truncated = assistant_message[:2000]
        if len(assistant_message) > 2000:
            truncated += "\n..."
        lines.append("*Codex Response:*")
        lines.append(f"```\n{truncated}\n```")
    else:
        lines.append("*Codex Response:* \\(none\\)")
    
    lines.append("")
    lines.append("─" * 30)
    lines.append("")
    
    # Token usage
    if total_tokens is not None:
        parts = [f"{total_tokens:,} total"]
        if input_tokens is not None:
            parts.append(f"{input_tokens:,} in")
        if output_tokens is not None:
            parts.append(f"{output_tokens:,} out")
        if reasoning_tokens:
            parts.append(f"{reasoning_tokens:,} reasoning")
        token_text = " / ".join(parts)
        lines.append(f"📊 Token usage: {_escape_markdown_v2(token_text)}")
    
    return "\n".join(lines)


def _do_send(
    config: TelegramConfig,
    task_id: str,
    status: str,
    assistant_message: str | None,
    total_tokens: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    reasoning_tokens: int | None,
    completed_at: str | None,
) -> None:
    """Synchronous: send message to all recipients."""
    message = _build_message(
        task_id=task_id,
        status=status,
        assistant_message=assistant_message,
        total_tokens=total_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        completed_at=completed_at,
    )

    for chat_id in config.allow_from:
        ok = _send_message(config.token, chat_id, message, config.proxy)
        if ok:
            logger.info("Telegram notification sent to %s", chat_id)


async def send_telegram_notification(
    config: TelegramConfig,
    task_id: str,
    status: str,
    assistant_message: str | None = None,
    total_tokens: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    completed_at: str | None = None,
) -> None:
    """Async wrapper: run Telegram API calls in thread executor to avoid blocking."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        partial(
            _do_send,
            config=config,
            task_id=task_id,
            status=status,
            assistant_message=assistant_message,
            total_tokens=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            completed_at=completed_at,
        ),
    )
