from __future__ import annotations

from html import escape

from murmur_space_bot.adapters.telegram.common.user_links import user_link
from murmur_space_bot.models.user import User


def format_user(user: User) -> str:
    username = user_link(user) if user.username else "—"
    return "\n".join(
        (
            f"🐈 <b>{escape(user.display_name)}</b>",
            f"Telegram ID · <code>{user.telegram_id}</code>",
            f"Username · {username}",
            f"Community tier · <b>{user.tier.value}</b>",
        )
    )
