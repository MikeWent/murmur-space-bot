from __future__ import annotations

from html import escape
from urllib.parse import quote

from murmur_space_bot.models.user import User


def user_link(user: User) -> str:
    """Render a profile link without creating an @username mention."""
    if user.username:
        url = f"https://t.me/{quote(user.username, safe='')}"
        return f'<a href="{url}">{escape(user.display_name)}</a>'
    return escape(user.display_name)

