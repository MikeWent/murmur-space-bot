from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Load a small, dependency-free subset of dotenv syntax."""
    if not path.is_file():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        os.environ.setdefault(key, value)


def _parse_ids(value: str) -> frozenset[int]:
    if not value.strip():
        return frozenset()
    try:
        return frozenset(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise ValueError("INITIAL_RESIDENT_IDS must contain comma-separated integers") from exc


def _required_int(name: str) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _required_timezone() -> ZoneInfo:
    name = os.getenv("TIMEZONE", "").strip()
    if not name:
        raise ValueError("TIMEZONE is required")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"TIMEZONE is not a valid IANA timezone: {name}") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_bot_token: str
    database_url: str
    initial_resident_ids: frozenset[int]
    recent_done_limit: int
    todo_chat_id: int
    todo_topic_id: int
    timezone: ZoneInfo
    log_level: str

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv()
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        done_limit = int(os.getenv("RECENT_DONE_LIMIT", "5"))
        if done_limit < 0:
            raise ValueError("RECENT_DONE_LIMIT cannot be negative")

        todo_chat_id = _required_int("TODO_CHAT_ID")
        todo_topic_id = _required_int("TODO_TOPIC_ID")
        if todo_chat_id == 0:
            raise ValueError("TODO_CHAT_ID cannot be zero")
        if todo_topic_id < 1:
            raise ValueError("TODO_TOPIC_ID must be positive")

        return cls(
            telegram_bot_token=token,
            database_url=os.getenv(
                "DATABASE_URL", "sqlite+aiosqlite:///./murmur-space-bot.sqlite3"
            ),
            initial_resident_ids=_parse_ids(os.getenv("INITIAL_RESIDENT_IDS", "")),
            recent_done_limit=done_limit,
            todo_chat_id=todo_chat_id,
            todo_topic_id=todo_topic_id,
            timezone=_required_timezone(),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
