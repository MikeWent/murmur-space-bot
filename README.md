# murmur-space-bot

A Telegram bot that keeps a local user directory and a shared todo list.

## Development

Copy `.env.example` to `.env`, set `TELEGRAM_BOT_TOKEN`, `TODO_CHAT_ID`, and
`TODO_TOPIC_ID`, set `TIMEZONE` to an IANA timezone such as `Asia/Tbilisi`, and
optionally list the Telegram IDs of initial residents in `INITIAL_RESIDENT_IDS`.
The bot needs permission to send, edit, and pin messages in the configured topic.

```shell
uv sync
uv run murmur-space-bot
```

The SQLite schema is created automatically at startup. There are no migrations.
At startup, the bot creates or refreshes a pinned todo dashboard in the configured
topic. Its message ID is stored in SQLite and replaced automatically if the message
is deleted.

## Commands

- `/user` — show your stored user information.
- `/user resident <@username|telegram-id>` — promote a user (residents only).
- Reply with `/user guest` — demote the replied-to user (residents only).
- `/todo <task>` — create a task and show its ID.
- `/todo` — show pending, in-progress, and recently completed tasks.
- `/doing <id>` — take a task.
- `/done <id>` — complete a task.
