"""Configuration management for Codex Listener."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".codex-listener"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS: dict[str, object] = {
    "feishu": {
        "enabled": False,
        "appId": "",
        "appSecret": "",
        "encryptKey": "",
        "verificationToken": "",
        "allowFrom": [],
    },
    "telegram": {
        "enabled": False,
        "token": "",
        "allowFrom": [],
        "proxy": None,
    },
    "qq": {
        "enabled": False,
        "appId": "",
        "secret": "",
        "allowFrom": [],
    },
}


@dataclass
class FeishuConfig:
    """Feishu Bot configuration."""

    enabled: bool
    app_id: str
    app_secret: str
    encrypt_key: str
    verification_token: str
    allow_from: list[str] = field(default_factory=list)


@dataclass
class TelegramConfig:
    """Telegram Bot configuration."""

    enabled: bool
    token: str
    allow_from: list[str] = field(default_factory=list)
    proxy: str | None = None


@dataclass
class QQConfig:
    """QQ Bot configuration."""

    enabled: bool
    app_id: str
    secret: str
    allow_from: list[str] = field(default_factory=list)


def load_config() -> dict[str, object]:
    """Load config from ~/.codex-listener/config.json, creating defaults if missing."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULTS, indent=2) + "\n")
        logger.info("Created default config: %s", CONFIG_FILE)
        return dict(DEFAULTS)

    try:
        data = json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read config (%s), using defaults", e)
        return dict(DEFAULTS)

    # Merge with defaults for any missing keys
    merged = dict(DEFAULTS)
    merged.update(data)
    return merged


def get_feishu_config() -> FeishuConfig | None:
    """Return FeishuConfig if enabled and configured, else None."""
    cfg = load_config()
    feishu = cfg.get("feishu")
    if not isinstance(feishu, dict):
        return None

    if not feishu.get("enabled"):
        return None

    app_id = feishu.get("appId", "")
    app_secret = feishu.get("appSecret", "")
    if not app_id or not app_secret:
        logger.warning("Feishu enabled but appId/appSecret missing")
        return None

    allow_from = feishu.get("allowFrom", [])
    if not allow_from:
        logger.warning("Feishu enabled but allowFrom is empty")
        return None

    return FeishuConfig(
        enabled=True,
        app_id=app_id,
        app_secret=app_secret,
        encrypt_key=feishu.get("encryptKey", ""),
        verification_token=feishu.get("verificationToken", ""),
        allow_from=allow_from,
    )


def get_telegram_config() -> TelegramConfig | None:
    """Return TelegramConfig if enabled and configured, else None."""
    cfg = load_config()
    telegram = cfg.get("telegram")
    if not isinstance(telegram, dict):
        return None

    if not telegram.get("enabled"):
        return None

    token = telegram.get("token", "")
    if not token:
        logger.warning("Telegram enabled but token missing")
        return None

    allow_from = telegram.get("allowFrom", [])
    if not allow_from:
        logger.warning("Telegram enabled but allowFrom is empty")
        return None

    return TelegramConfig(
        enabled=True,
        token=token,
        allow_from=allow_from,
        proxy=telegram.get("proxy"),
    )


def get_qq_config() -> QQConfig | None:
    """Return QQConfig if enabled and configured, else None."""
    cfg = load_config()
    qq = cfg.get("qq")
    if not isinstance(qq, dict):
        return None

    if not qq.get("enabled"):
        return None

    app_id = qq.get("appId", "")
    secret = qq.get("secret", "")
    if not app_id or not secret:
        logger.warning("QQ enabled but appId/secret missing")
        return None

    allow_from = qq.get("allowFrom", [])
    if not allow_from:
        logger.warning("QQ enabled but allowFrom is empty")
        return None

    return QQConfig(
        enabled=True,
        app_id=app_id,
        secret=secret,
        allow_from=allow_from,
    )
