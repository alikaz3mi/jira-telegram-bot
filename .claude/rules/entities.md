---
paths: ["jira_telegram_bot/entities/**/*.py"]
---
# Entities layer rules

The innermost ring. Entities import **nothing** from this project.

- Every entity is a Pydantic `BaseModel`. Never `@dataclass`, never a plain
  class.
- Every field carries a `Field(description=...)`. The description is read by
  people and, for anything an LLM fills, by the model too.
- No I/O, no Jira client, no network, no file access.
- Enums subclass `str, Enum` so they serialise cleanly and compare to strings.

## Optional means optional

A field that cannot always be known must be `Optional[...] = None`.

`telegram_user_chat_id` was once a required `int`. A teammate registered from
Jira before anyone had their Telegram id failed validation, and the loader
skipped the whole entry — ten people vanished from a 27-entry config and the
only trace was a log line nobody read. Prefer an optional field and an
explicit check at the point of use.

## Persian text

User-facing Persian lives in `entities/constants/persian_messages.py` as
module-level constants, never inline in a handler. One place to review
wording, and handlers stay readable.
