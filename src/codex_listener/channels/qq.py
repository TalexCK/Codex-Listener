"""QQ Bot notification via Botpy SDK."""

from __future__ import annotations

import asyncio
import logging
from functools import partial

import botpy

from codex_listener.config import QQConfig

logger = logging.getLogger(__name__)


def _escape_markdown(text: str) -> str:
    """Escape special characters for QQ Markdown."""
    # QQ uses a subset of markdown, escape carefully
    special_chars = ["_", "*", "`", "[", "]"]
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
    """Build QQ message with Markdown formatting."""
    is_ok = status == "completed"
    status_emoji = "✅" if is_ok else "❌"

    lines = [
        f"{status_emoji} **Codex Task {_escape_markdown(task_id)}**",
        "",
        f"**Status:** {_escape_markdown(status)}",
    ]

    if completed_at:
        lines.append(f"**Completed:** {_escape_markdown(completed_at)}")

    lines.append("")
    lines.append("─" * 30)
    lines.append("")

    # Assistant message
    if assistant_message:
        truncated = assistant_message[:2000]
        if len(assistant_message) > 2000:
            truncated += "\n..."
        lines.append("**Codex Response:**")
        lines.append(f"```\n{truncated}\n```")
    else:
        lines.append("**Codex Response:** (none)")

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
        lines.append(f"📊 Token usage: {_escape_markdown(token_text)}")

    return "\n".join(lines)


class _NotificationBot(botpy.Client):
    """Internal bot client for sending notifications."""

    def __init__(self, message: str, recipients: list[str]):
        # Initialize with C2C message intent
        intents = botpy.Intents(c2c_group_at_messages=True)
        super().__init__(intents=intents)
        self.message = message
        self.recipients = recipients
        self._sent = False

    async def on_ready(self) -> None:
        """Called when bot is ready - send messages then disconnect."""
        logger.info("QQ Bot ready, sending to %d recipients", len(self.recipients))

        for open_id in self.recipients:
            try:
                # Use C2C (user-to-user) message API
                await self.api.post_c2c_message(
                    openid=open_id,
                    msg_type=0,  # Text message
                    content=self.message,
                )
                logger.info("QQ notification sent to %s", open_id)
            except Exception as e:
                logger.warning("QQ send failed to %s: %s", open_id, e)

        self._sent = True
        # Close connection after sending
        await self.close()


def _do_send(
    config: QQConfig,
    task_id: str,
    status: str,
    assistant_message: str | None,
    total_tokens: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    reasoning_tokens: int | None,
    completed_at: str | None,
) -> None:
    """Synchronous: send message to all recipients using botpy."""
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

    # Create bot instance and run
    async def _run_bot() -> None:
        bot = _NotificationBot(message, config.allow_from)
        async with bot:
            await bot.start(appid=config.app_id, secret=config.secret)

    # Run the async function
    asyncio.run(_run_bot())


async def send_qq_notification(
    config: QQConfig,
    task_id: str,
    status: str,
    assistant_message: str | None = None,
    total_tokens: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    completed_at: str | None = None,
) -> None:
    """Async wrapper: run QQ API calls in thread executor to avoid blocking."""
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
