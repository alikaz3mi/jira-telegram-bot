---
paths: ["jira_telegram_bot/use_cases/assistant/**/*.py"]
---
# Task assistant rules

A LangGraph agent that answers questions about a person's Jira work. It reads;
it does not write.

## Identity is not the model's business

`AssistantContext` is built by the handler from the verified Telegram user and
passed to `AssistantTools` when the tool set is constructed. **No tool takes a
parameter that redirects it at another user.** Tools resolve a spoken name,
then call `context.may_read()` and refuse in Python.

Roles: `MEMBER` reads only their own work, `LEAD` and `CTO` read others'.
An unrecognised role reads as `MEMBER` — unknown input never widens access.

## Tools

Each tool returns text ready to send. Keep formatting in the tool, not the
prompt: a rendering rule stated once in Python holds, the same rule stated in
a prompt holds most of the time.

- Issue keys render as `<a href>` links built from the Jira base URL.
- Sub-tasks nest under their parent. A flat list of forty sub-task keys is
  unreadable; the parent is what a person recognises.
- A sub-task whose parent is absent still appears, grouped under its parent
  key. Dropping it makes the rendered list disagree with the count.

## Names

People and projects are resolved through `EntityAliasRepository`, never
guessed. «آواخرد» is `FOLLOWUP`; no amount of reasoning derives that.

The person aliases in `scripts/seed_entity_aliases.py` are hardcoded, so a new
joiner is invisible until the file is edited. When a name will not resolve,
check that list before assuming the person has no work — eleven of nineteen
active assignees were missing once, including the two carrying the most tasks.

## Memory

`ConversationMemory` holds the last six turns per chat. It is passed to the
classifier, the parser and the agent — all three, or a follow-up reads as a
new topic and the reply repeats what was just said.
