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
NOTIFIER_NAME = "Codex-Listener"
MAX_ASSISTANT_ESCAPED_LEN = 2000
MAX_PLAN_PREVIEW_ESCAPED_LEN = 600


def _build_api_url(token: str, method: str) -> str:
    """Build Telegram Bot API URL."""
    return f"https://api.telegram.org/bot{token}/{method}"


def _send_message(
    token: str,
    chat_id: str,
    text: str,
    parse_mode: str | None = None,
    reply_markup: dict[str, object] | None = None,
    proxy: str | None = None,
) -> bool:
    """Send a text message to a specific chat."""
    url = _build_api_url(token, "sendMessage")
    payload: dict[str, object] = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    body = json.dumps(payload).encode()

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
    except urllib.error.HTTPError as e:
        detail = str(e)
        try:
            payload = json.loads(e.read().decode())
            if isinstance(payload, dict):
                detail = payload.get("description", detail)
        except Exception:
            pass
        logger.warning(
            "Telegram send request failed to %s: %s",
            chat_id,
            detail,
        )
        return False
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        logger.warning("Telegram send request failed to %s: %s", chat_id, e)
        return False


def _escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


def _escape_and_truncate_markdown_v2(text: str, max_len: int) -> str:
    """Escape MarkdownV2 text and truncate by escaped length."""
    escaped = _escape_markdown_v2(text)
    if len(escaped) <= max_len:
        return escaped

    suffix = _escape_markdown_v2("\n...")
    if max_len <= len(suffix):
        return suffix[:max_len]

    truncated = escaped[: max_len - len(suffix)]
    while truncated.endswith("\\"):
        truncated = truncated[:-1]
    return truncated + suffix


def _build_reply_markup(task_id: str, bridge_stage: str | None) -> dict[str, object] | None:
    """Build Telegram inline keyboard for Plan Bridge stages."""
    if bridge_stage == "needs_input":
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "✍️ 回复问题",
                        "switch_inline_query_current_chat": f"/plan-reply {task_id} ",
                    }
                ]
            ]
        }

    if bridge_stage == "plan_ready":
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ 执行计划",
                        "callback_data": f"pb1|exec|{task_id}",
                    }
                ],
                [
                    {
                        "text": "📝 继续修改",
                        "switch_inline_query_current_chat": f"/plan-reply {task_id} ",
                    },
                    {
                        "text": "❌ 取消",
                        "callback_data": f"pb1|cancel|{task_id}",
                    },
                ],
            ]
        }

    return None


def _build_message(
    task_id: str,
    status: str,
    assistant_message: str | None,
    total_tokens: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    reasoning_tokens: int | None,
    completed_at: str | None,
    bridge_stage: str | None,
    bridge_questions: list[str] | None,
    bridge_plan: str | None,
) -> str:
    """Build Telegram message with Markdown formatting."""
    is_ok = status == "completed"
    status_emoji = "✅" if is_ok else "❌"
    notifier = _escape_markdown_v2(NOTIFIER_NAME)
    
    lines = [
        f"{status_emoji} *{notifier} Task {_escape_markdown_v2(task_id)}*",
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
        escaped_truncated = _escape_and_truncate_markdown_v2(
            assistant_message,
            MAX_ASSISTANT_ESCAPED_LEN,
        )
        lines.append("*Codex Response:*")
        lines.append(escaped_truncated)
    else:
        lines.append("*Codex Response:* \\(none\\)")

    if bridge_stage in {"needs_input", "plan_ready"}:
        lines.append("")
        lines.append("*Plan Bridge:*")
        lines.append(f"Stage: `{_escape_markdown_v2(bridge_stage)}`")
        if bridge_stage == "needs_input":
            if bridge_questions:
                lines.append("Questions:")
                for i, q in enumerate(bridge_questions, 1):
                    lines.append(
                        f"{i}\\. {_escape_markdown_v2(str(q).strip())}"
                    )
            lines.append(
                f"Reply template: `/plan\\-reply {_escape_markdown_v2(task_id)} <your answer>`"
            )
        elif bridge_stage == "plan_ready" and bridge_plan:
            escaped_plan_preview = _escape_and_truncate_markdown_v2(
                bridge_plan,
                MAX_PLAN_PREVIEW_ESCAPED_LEN,
            )
            lines.append("Plan preview:")
            lines.append(escaped_plan_preview)
    
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


def _build_plain_message(
    task_id: str,
    status: str,
    assistant_message: str | None,
    total_tokens: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    reasoning_tokens: int | None,
    completed_at: str | None,
    bridge_stage: str | None,
    bridge_questions: list[str] | None,
    bridge_plan: str | None,
) -> str:
    """Build plain-text fallback message for Telegram."""
    is_ok = status == "completed"
    status_emoji = "SUCCESS" if is_ok else "FAILED"
    lines = [
        f"{NOTIFIER_NAME} Task {task_id}",
        f"Status: {status_emoji} ({status})",
    ]
    if completed_at:
        lines.append(f"Completed: {completed_at}")

    lines.append("")
    lines.append("Codex Response:")
    if assistant_message:
        truncated = assistant_message[:2800]
        if len(assistant_message) > 2800:
            truncated += "\n..."
        lines.append(truncated)
    else:
        lines.append("(none)")

    if total_tokens is not None:
        parts = [f"{total_tokens:,} total"]
        if input_tokens is not None:
            parts.append(f"{input_tokens:,} in")
        if output_tokens is not None:
            parts.append(f"{output_tokens:,} out")
        if reasoning_tokens:
            parts.append(f"{reasoning_tokens:,} reasoning")
        lines.append("")
        lines.append(f"Token usage: {' / '.join(parts)}")

    if bridge_stage in {"needs_input", "plan_ready"}:
        lines.append("")
        lines.append(f"Plan Bridge Stage: {bridge_stage}")
        if bridge_stage == "needs_input":
            if bridge_questions:
                lines.append("Questions:")
                for i, q in enumerate(bridge_questions, 1):
                    lines.append(f"{i}. {q}")
            lines.append(f"Reply template: /plan-reply {task_id} <your answer>")
        elif bridge_stage == "plan_ready" and bridge_plan:
            plan_preview = bridge_plan[:800]
            if len(bridge_plan) > 800:
                plan_preview += "\n..."
            lines.append("Plan preview:")
            lines.append(plan_preview)

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
    bridge_stage: str | None,
    bridge_questions: list[str] | None,
    bridge_plan: str | None,
) -> None:
    """Synchronous: send message to all recipients."""
    reply_markup = _build_reply_markup(task_id, bridge_stage)

    markdown_message = _build_message(
        task_id=task_id,
        status=status,
        assistant_message=assistant_message,
        total_tokens=total_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        completed_at=completed_at,
        bridge_stage=bridge_stage,
        bridge_questions=bridge_questions,
        bridge_plan=bridge_plan,
    )
    plain_message = _build_plain_message(
        task_id=task_id,
        status=status,
        assistant_message=assistant_message,
        total_tokens=total_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        completed_at=completed_at,
        bridge_stage=bridge_stage,
        bridge_questions=bridge_questions,
        bridge_plan=bridge_plan,
    )

    for chat_id in config.allow_from:
        ok = _send_message(
            config.token,
            chat_id,
            markdown_message,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup,
            proxy=config.proxy,
        )
        if not ok:
            # Fallback to plain text for markdown parse errors or long entities.
            ok = _send_message(
                config.token,
                chat_id,
                plain_message,
                parse_mode=None,
                reply_markup=reply_markup,
                proxy=config.proxy,
            )
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
    bridge_stage: str | None = None,
    bridge_questions: list[str] | None = None,
    bridge_plan: str | None = None,
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
            bridge_stage=bridge_stage,
            bridge_questions=bridge_questions,
            bridge_plan=bridge_plan,
        ),
    )
