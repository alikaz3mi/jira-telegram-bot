---
paths: ["jira_telegram_bot/frameworks/**/*.py"]
---
# Frameworks layer rules

The outermost ring: Telegram handlers, FastAPI endpoints, schedulers. They may
import from every inner ring; nothing imports them.

## Telegram handlers

- A handler orchestrates. Business logic belongs in a use case.
- Every new callback prefix must be added to the `CallbackQueryHandler`
  pattern in `__main__.py`. A prefix missing from the pattern means the
  buttons render and silently do nothing.
- Replies carrying links are sent with `parse_mode="HTML"` and a plain-text
  fallback, because Telegram rejects markup it does not accept — `<br>` among
  it.
- Conversation state lives in `context.user_data`, which is per-user and
  in-process. It does not survive a restart; never keep anything there that
  matters after the conversation ends.
- Free text that is not answering an open prompt is routed by intent, never
  assumed to be one thing. Assuming it was always a worklog answered a
  greeting with "I did not understand how many hours you spent".

## Schedulers

- Use `APSchedulerService`. No `while True` with `asyncio.sleep`.
- A job that messages people states how many it will contact before it starts,
  and caps what any one person receives. A queue of 187 sequential prompts is
  abandoned, not completed.
