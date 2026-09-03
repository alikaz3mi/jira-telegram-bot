# Jira Telegram Bot — Always-On Instructions

A Telegram bot over Jira: task creation, daily tracking, worklogs, sprint
analytics, and a conversational assistant. Persian is the user-facing
language; English is the language of the code.

## Architecture: Clean Architecture (strict)

Rings (inner → outer): `entities/` → `use_cases/` → `adapters/` → `frameworks/`

**Dependency rule:** imports only point **inward**. `entities` imports nothing
from the project. `use_cases` imports only from `entities` and
`use_cases/interfaces/`. `adapters` never import from `frameworks`.

Interfaces (ports) live in `use_cases/interfaces/`, class names end with
`Interface`, files end with `_interface.py`.

Dependency injection is **Lagom**. Bindings live in
`config_dependency_injection.py`; the container is built in `app_container.py`.
Scripts obtain dependencies through `get_container()` — never by direct
instantiation.

---

## Code Style

- **PEP 8** + Clean Code: short, intention-revealing names, small functions.
- All parameters and returns **type-annotated**.
- **No inline comments inside function bodies.** One docstring per
  function/class covering purpose, args, returns and raises.
  A comment above a block is acceptable when it explains *why*, never *what*.
- `pathlib.Path` over raw path strings. `datetime` with an explicit timezone.
- No `print()` — use `LOGGER` from `jira_telegram_bot`.
- No `os.getenv()` in logic — settings are `pydantic_settings.BaseSettings`
  classes in `settings/`, injected through the container.
- Entities are Pydantic `BaseModel`s, never `@dataclass`.

| Style | Usage |
|---|---|
| `snake_case` | variables, functions, modules, filenames |
| `PascalCase` | classes, exceptions |
| `SCREAMING_SNAKE_CASE` | constants, env vars |

---

## Key Rules (never violate)

- **Never let a model choose a Jira issue key.** Give it a numbered candidate
  list and take back an index. A hallucinated key writes real data to the
  wrong issue, and worklogs are painful to unwind.
- **Authorisation is decided in Python, never in a prompt.** The caller's
  identity is bound in `AssistantContext` when the tool set is built; tools
  check `may_read()` themselves. No prompt wording is a security control.
- **Anything that writes to Jira is confirmed by the user first.** Parse,
  show what will be written, then write on an explicit tap.
- **Classification and parsing fail closed.** An unrecognised label, an empty
  message or a failed model call must do nothing. Doing nothing is always
  safer than writing something nobody asked for.
- **Arithmetic and dates are validated in code**, not trusted from a model.
  A worklog dated in the future is always wrong; Jira accepts one silently.
- **Never drop a record silently.** A task filtered out of a list, a config
  entry that fails validation, an issue that errors mid-fetch — log it and
  count it. A short list read as complete is worse than an error.
- **Persian text belongs in `entities/constants/persian_messages.py`**, not
  inline in handlers.
- Telegram HTML: `<a href>`, `<b>`, `<i>` and `<code>` render; most other
  tags are rejected by the API. Any user-supplied text placed inside markup
  — a Jira summary, a release name — must be `html.escape`d first, or one
  `&` in a summary costs the whole message.
- A new dependency goes in `requirements.txt` in the same change that
  imports it.

---

## Testing

- `unittest` only, under `tests/`, mirroring the package structure.
- Files `test_*.py`, classes `Test*`, methods `test_*`.
- Arrange–Act–Assert. Mock external services; never call live Jira or OpenAI
  in a test.
- A bug fix lands with the test that reproduces it.
- The suite has **~80 pre-existing failures** unrelated to current work.
  Compare the failing set before and after a change rather than reading the
  count — a green suite is not the bar; an unchanged failing set is.

---

## Running it

```bash
docker compose up -d --build telegram-bot   # after a requirements change
docker compose restart telegram-bot         # after a code change (. is mounted)
docker compose logs -f telegram-bot
```

The bot resolves `.env` and `data/` **relative to its working directory**.
Running it from anywhere but the repo root fails with a settings validation
error. In Docker `WORKDIR /app` plus the bind mount makes this correct.

Locally: `python -m jira_telegram_bot` from the repo root. Never run a local
instance and the container at once — two pollers on one token conflict.

---

## Changelog

Every release adds `docs/changelog/{version}.md` and bumps `__version__` in
`jira_telegram_bot/__init__.py`. See `.claude/rules/changelog.md`.
