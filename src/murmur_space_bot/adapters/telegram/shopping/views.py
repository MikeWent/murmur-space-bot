from __future__ import annotations

import re
from datetime import datetime
from html import escape
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from murmur_space_bot.adapters.telegram.common.time import format_local_time
from murmur_space_bot.adapters.telegram.common.user_links import user_link
from murmur_space_bot.models.shopping import ShoppingItem

CALLBACK_PREFIX = "need:"
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
URL_TRAILING_PUNCTUATION = ".,!?;:"
LONG_URL_LABEL_THRESHOLD = 80
BUTTON_TEXT_LIMIT = 64


def format_shopping_list(
    items: list[ShoppingItem],
    *,
    updated_at: datetime | None = None,
    local_timezone: ZoneInfo | None = None,
) -> str:
    lines = [
        "🌸 <b>Shopping list</b>"
    ]
    if items:
        lines.append("")
        lines.extend(
            f"• {_linkify(item.name)} — by {user_link(item.added_by)}"
            for item in items
        )
        lines.extend((
            "",
            "<i>Tap an item <b>twice</b> if you've bought it 🐾</i>",
        ))
    else:
        lines.extend(("", "The list is empty ♡"))
    return "\n".join(lines)


def shopping_keyboard(items: list[ShoppingItem]) -> InlineKeyboardMarkup | None:
    if not items:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_button_text(item),
                    callback_data=f"{CALLBACK_PREFIX}{item.id}",
                )
            ]
            for item in items
        ]
    )


def format_item_added(item: ShoppingItem) -> str:
    return (
        f"🛒 <b>{_linkify(item.name)}</b> added to the shopping list "
        f"by {user_link(item.added_by)}!"
    )


def format_item_bought(item: ShoppingItem) -> str:
    buyer = user_link(item.bought_by) if item.bought_by else "a mystery kitty"
    return f"✅ <b>{_linkify(item.name)}</b> has been purchased — thanks {buyer}!"


def _button_text(item: ShoppingItem) -> str:
    has_link = URL_PATTERN.search(item.name) is not None
    label = " ".join(URL_PATTERN.sub("", item.name).split())
    if not label:
        label = "Shopping link" if has_link else item.name

    suffix = " 🔗" if has_link else ""
    available = BUTTON_TEXT_LIMIT - len(suffix)
    if len(label) > available:
        label = f"{label[: available - 1].rstrip()}…"
    return f"{label}{suffix}"


def _linkify(text: str) -> str:
    """Escape item text and turn HTTP(S) URLs into Telegram HTML links."""
    parts: list[str] = []
    cursor = 0
    for match in URL_PATTERN.finditer(text):
        parts.append(escape(text[cursor : match.start()]))
        matched_url = match.group()
        url = matched_url.rstrip(URL_TRAILING_PUNCTUATION)
        suffix = matched_url[len(url) :]
        escaped_url = escape(url, quote=True)
        parts.append(f'<a href="{escaped_url}">{escape(_url_label(url))}</a>')
        parts.append(escape(suffix))
        cursor = match.end()
    parts.append(escape(text[cursor:]))
    return "".join(parts)


def _url_label(url: str) -> str:
    if len(url) <= LONG_URL_LABEL_THRESHOLD:
        return url
    hostname = urlsplit(url).hostname
    return f"{hostname or 'open link'}/…"
