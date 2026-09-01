## Caller identity is keyed on the mutable Telegram username

**Status:** open
**Raised:** 2026-08-31
**Severity:** security — privilege escalation, no user-visible symptom
**Files:** `jira_telegram_bot/adapters/user_config.py`,
`jira_telegram_bot/frameworks/telegram/daily_task_tracking_handler.py`,
`jira_telegram_bot/settings/user_config.json`

### Problem

Every caller lookup in the bot resolves a person by `update.effective_user.username`
— the Telegram *@handle*. A Telegram handle is not an identifier. It is a
user-editable display string: its owner can change or clear it at any time, and once
released it becomes available for anyone else to claim.

`user_config.json` is keyed on that string, so the handle is simultaneously the
lookup key and the authorization key. Anyone who acquires a handle that appears in
that file inherits that person's `jira_username` and their `assistant_role`.

Nothing is known to have been exploited. It is filed because the rest of the
identity path is deliberately careful — identity is bound outside the model, and
`_role_of` fails closed — and all of that care rests on a key that does not hold.

### The chain

`adapters/user_config.py:43-49` builds the map keyed on the JSON's top-level key,
which is a Telegram handle:

```python
user_configurations = {}
for username, config_data in raw_data.items():
    user_configurations[username] = UserConfigEntity(**config_data)
```

`adapters/user_config.py:55-56` is the whole lookup:

```python
def get_user_config(self, username: str) -> Optional[UserConfigEntity]:
    return self.user_config.get(username)
```

`frameworks/telegram/daily_task_tracking_handler.py:791-808` turns the result into
the authorization context:

```python
user_config = self.user_config_repository.get_user_config(
    update.effective_user.username,
)
...
context=AssistantContext(
    jira_username=user_config.jira_username,
    telegram_username=update.effective_user.username or "",
    role=self._role_of(user_config),
),
```

`entities/assistant_entities.py` then decides reads from that role —
`UserRole.LEAD` and `UserRole.CTO` return `may_read_others == True`.

The same `get_user_config(query.from_user.username)` pattern appears throughout
`daily_task_tracking_handler.py` (lines 366, 423, 480, 521, 593 among others), so
this is the codebase's single identity convention, not one careless call site.

### Failure scenario

1. A person with `assistant_role: "lead"` or `"cto"` in `user_config.json` changes
   or removes their Telegram handle — a routine thing people do.
2. Telegram releases the old handle to the public pool.
3. Anyone claims it and messages the bot.
4. `get_user_config()` matches on the string, and the claimant is issued an
   `AssistantContext` carrying the original person's `jira_username` and role.
5. With a `lead` or `cto` role, `may_read_others` is `True`, and the assistant will
   answer questions about any employee's tasks.

No prompt injection is involved; the model is never consulted about identity. The
binding is simply wrong before the agent starts, which is precisely the layer the
design intends to be trustworthy.

There is a second, quieter failure: a person who merely *changes* their handle stops
matching and silently becomes unknown to the bot. `_handle_task_question` returns
without a reply when `user_config` is falsy
(`daily_task_tracking_handler.py:795-796`, and again at `895-896`), so they get no
answer and no explanation. A third site (`1124-1126`) at least shows an error
message — the inconsistency is worth settling while fixing this.

### The fix is already half-present in the data

`UserConfigEntity` already carries `telegram_user_chat_id: Optional[int]`
(`entities/user_config.py:21`), and most entries in `data/storage/user_config.json`
have a real value. Telegram's numeric user id is immutable and cannot be
transferred. It is stored but never used for lookup.

### Suggested fix

1. Add `get_user_config_by_telegram_id(telegram_user_id: int)` to
   `UserConfigInterface` and `adapters/user_config.py`, backed by an index built at
   load time. An entry whose `telegram_user_chat_id` is missing or `-1` must not be
   indexed.
2. Change every authorization-path call site to pass `update.effective_user.id`
   instead of `.username`. `daily_task_tracking_handler.py` holds most of them.
3. Keep `telegram_username` on the entity for display and logging only. It must
   stop being an input to any authorization decision.
4. Backfill the entries that have no usable `telegram_user_chat_id`. In
   `data/storage/user_config.json` today, 10 human entries carry no email, 2 carry
   the placeholder `-1`, and 6 rows are bots or service accounts
   (`Parschat_AI`, four `ParschatAI_support*`, `GroupAnonymousBot`). Only 8 distinct
   real people currently have both an email and a usable numeric id.
5. Decide the unknown-caller behaviour explicitly. Today an unmatched user is
   silently ignored; that will read as the bot being broken. A short "I don't
   recognise this account, ask an admin to register you" is both kinder and more
   debuggable.

### Migration note

`user_config.json` is keyed on handles, so the numeric-id index has to be built from
the `telegram_user_chat_id` *values*, not the keys. Note that three entries
(`alikaz3mi`, `ali_kazemi`, `GroupAnonymousBot`) share chat id `100375147`, so the
index must be many-keys-to-one-person rather than assume uniqueness — or those
duplicates should be resolved first.

### Why it happened

The handle is what a person tells you when you ask "what's your Telegram?", so it is
the natural thing to write in a config file a human maintains by hand. It reads as
an identifier and behaves like one right up until someone changes it. The numeric id
was captured later, alongside it, without the lookup being moved over.

### Risk of the fix

Every assistant and daily-task-tracking entry point changes its lookup key at once.
A person whose `telegram_user_chat_id` is absent or stale stops being recognised the
moment this lands — which is the correct behaviour, but it is a visible change for
them and should be paired with the backfill in step 4 rather than shipped alone.

### Related

The Odoo HR Telegram agent being specified in
`plannings/.wayfinder/` (ticket 02) will key identity on the immutable numeric id
for this reason, and will not copy this pattern. That bot handles salary, contracts
and leave, where this failure mode is materially worse.
