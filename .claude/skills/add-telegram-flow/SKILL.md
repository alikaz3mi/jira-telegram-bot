---
name: add-telegram-flow
description: Add a conversational capability to the bot — a new question the assistant can answer, a new prompt-driven flow, or a new tool. Use when asked to make the bot understand or do something new in chat.
---

# Adding a conversational flow

The order below exists because each step fails loudly if the one before it was
skipped. Doing it in another order produces a flow that looks finished and
silently does nothing.

---

## 1. Decide where the logic belongs

| Kind of change | Where |
|---|---|
| A new thing the assistant can look up | a tool in `use_cases/assistant/assistant_tools.py` |
| A new way of interpreting a message | a prompt in `adapters/ai_models/prompts/` + a use case |
| A new button flow | a handler method + callback prefix |

If a model has to choose between existing capabilities, it is a tool. If it
has to interpret free text, it is a prompt.

---

## 2. Write the prompt, if there is one

YAML in `adapters/ai_models/prompts/`. Every `{placeholder}` listed in
`input_variables`.

State the ambiguous case explicitly, enumerate any mapping that matters, and
give the model a described way to return nothing. See `.claude/rules/prompts.md`.

---

## 3. Write the use case

Constructor injection, one `execute()`, validate what comes back. A model's
dates, indices and totals are suggestions — check them in Python.

Failure returns a neutral result and logs. Never raise because a model
misbehaved.

---

## 4. Register in the container

`config_dependency_injection.py`. Then confirm it resolves:

```python
from jira_telegram_bot.app_container import get_container
get_container()[YourUseCase]
```

A missing binding raises here, not at import — it will otherwise surface on a
user's first message.

---

## 5. Wire the handler

- Add the callback prefix to the `CallbackQueryHandler` pattern in
  `__main__.py`. **Skipping this is the single most common mistake**: the
  keyboard renders, the tap does nothing, nothing is logged.
- Pass `self._memory(context)` to anything that reads a message. All three of
  classifier, parser and agent need it, or a follow-up reads as a new topic.
- Persian strings go in `entities/constants/persian_messages.py`.

---

## 6. Test the failure paths

- The model returns `{}`.
- The user is refused (assert the refusal explicitly).
- Jira raises mid-batch.
- Text arrives while another prompt is open — the open prompt must win.

Compare the failing set against baseline; see `.claude/rules/tests.md`.

---

## 7. Try it against live data before saying it works

```bash
docker compose restart telegram-bot
docker compose logs -f telegram-bot
```

Run the real question through the real agent with a real Jira user. Unit tests
pass on mocks that flatter the design — a prompt that reads well can still
answer the wrong question, and only live data shows it.
