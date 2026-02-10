"""Feishu Bot notification via Open API (stdlib only)."""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from functools import partial

from codex_listener.config import FeishuConfig

logger = logging.getLogger(__name__)

_TOKEN_URL = (
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
)
_SEND_MSG_URL = "https://open.feishu.cn/open-apis/im/v1/messages"


def _get_tenant_access_token(app_id: str, app_secret: str) -> str | None:
    """Fetch tenant_access_token from Feishu API."""
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(
        _TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data.get("code") != 0:
            logger.warning("Feishu token error: %s", data.get("msg"))
            return None
        return data.get("tenant_access_token")
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        logger.warning("Feishu token request failed: %s", e)
        return None


def _send_message(token: str, open_id: str, card_json: str) -> bool:
    """Send an interactive card message to a specific user."""
    url = f"{_SEND_MSG_URL}?receive_id_type=open_id"
    body = json.dumps({
        "receive_id": open_id,
        "msg_type": "interactive",
        "content": card_json,
    }).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data.get("code") != 0:
            logger.warning(
                "Feishu send failed to %s: %s", open_id, data.get("msg"),
            )
            return False
        return True
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        logger.warning("Feishu send request failed to %s: %s", open_id, e)
        return False


def _build_card(
    task_id: str,
    status: str,
    assistant_message: str | None,
    total_tokens: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    reasoning_tokens: int | None,
    completed_at: str | None,
) -> str:
    """Build Feishu interactive card JSON string."""
    is_ok = status == "completed"
    template = "green" if is_ok else "red"
    title = f"Codex Task {task_id} — {'Completed' if is_ok else 'Failed'}"

    elements: list[dict] = []

    # Status + time
    meta_lines = [f"**Status:** {status}"]
    if completed_at:
        meta_lines.append(f"**Completed:** {completed_at}")
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "\n".join(meta_lines)},
    })

    elements.append({"tag": "hr"})

    # Assistant message
    if assistant_message:
        truncated = assistant_message[:2000]
        if len(assistant_message) > 2000:
            truncated += "\n..."
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**Codex Response:**\n{truncated}",
            },
        })
    else:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**Codex Response:** (none)"},
        })

    elements.append({"tag": "hr"})

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
        elements.append({
            "tag": "note",
            "elements": [
                {"tag": "lark_md", "content": f"Token usage: {token_text}"},
            ],
        })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": template,
        },
        "elements": elements,
    }
    return json.dumps(card, ensure_ascii=False)


def _do_send(
    config: FeishuConfig,
    task_id: str,
    status: str,
    assistant_message: str | None,
    total_tokens: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    reasoning_tokens: int | None,
    completed_at: str | None,
) -> None:
    """Synchronous: get token and send to all recipients."""
    token = _get_tenant_access_token(config.app_id, config.app_secret)
    if token is None:
        logger.warning("Feishu: could not obtain access token, skipping")
        return

    card_json = _build_card(
        task_id=task_id,
        status=status,
        assistant_message=assistant_message,
        total_tokens=total_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        completed_at=completed_at,
    )

    for open_id in config.allow_from:
        ok = _send_message(token, open_id, card_json)
        if ok:
            logger.info("Feishu notification sent to %s", open_id)


async def send_feishu_notification(
    config: FeishuConfig,
    task_id: str,
    status: str,
    assistant_message: str | None = None,
    total_tokens: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    completed_at: str | None = None,
) -> None:
    """Async wrapper: run Feishu API calls in thread executor to avoid blocking."""
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
