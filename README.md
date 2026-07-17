# murmur-space-bot

A Telegram bot that keeps a local user directory and a shared todo list.

## Development

Copy `.env.example` to `.env`, set `TELEGRAM_BOT_TOKEN`, the todo and shopping
chat/topic IDs, and set `TIMEZONE` to an IANA timezone such as `Asia/Tbilisi`.
You may also list initial resident IDs in `INITIAL_RESIDENT_IDS`. The bot needs
permission to send, edit, and pin messages in both configured topics.

```shell
uv sync
uv run murmur-space-bot
```

The SQLite schema is created automatically at startup. There are no migrations.
At startup, the bot creates or refreshes a pinned todo dashboard in the configured
topic. Its message ID is stored in SQLite and replaced automatically if the message
is deleted.

The Telegram adapter is organized as vertical feature slices under
`adapters/telegram/{users,todos,shopping}`. Each feature owns its router, views, and
board integration. Shared Telegram-only behavior lives in `common/`, middleware in
`middleware/`, and `app.py` is the composition root.

The shopping topic works the same way. Shopping notifications are mirrored there
when the action happens elsewhere. Buying an item requires two taps by the same
person within 30 seconds, which prevents accidental removal. Pending confirmations
are held only in process memory and disappear when the bot restarts.

## Commands

- `/user` — show your stored user information.
- `/user resident <@username|telegram-id>` — promote a user (residents only).
- Reply with `/user guest` — demote the replied-to user (residents only).
- `/todo <task>` — create a task.
- `/todo` — show pending, in-progress, and recently completed tasks with status buttons.
- `/needs` — show the shopping list with interactive item buttons.
- `/need <item>` — add an item to the shopping list.
