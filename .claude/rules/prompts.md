---
paths: ["jira_telegram_bot/adapters/ai_models/prompts/**/*.yaml"]
---
# Prompt rules

Every prompt is a YAML file here, loaded through the prompt catalogue. No
prompt text lives in Python.

## Required keys

`id`, `version`, `language`, `temperature`, `model_hint`, `model_engine`,
`description`, `prompt`, `schemas`, `input_variables`.

- `model_hint` picks the model per prompt: `gpt-4.1-nano` for classification,
  `gpt-4o-mini` for parsing and answering. Never hardcode a model in Python.
- `temperature` is `0.0` for classification. Routing must be reproducible.
- Every `{placeholder}` in `prompt` appears in `input_variables`. A mismatch
  raises at call time, not at load — the failure surfaces in production.

## Writing the prompt

- Say what to do with the ambiguous case, not only the clear one. "When the
  message names no day, leave the field null" prevents a guess.
- Enumerate rather than describe when a mapping matters. "«پارسچت» means
  PARSCHAT, PCT or PCD" works; "the ParsChat projects" produced an empty
  answer because the model excluded what it was unsure about.
- Give the model an explicit way to say *I could not tell*. Returning nothing
  must be a valid, described outcome, or it will invent something.
- Never ask for a Jira key. Ask for an index into a list you supplied.
- Constrain the output format precisely. "`<a href>` is the only tag Telegram
  accepts — never `<br>`" was learned from a broken reply.

## Changing a prompt

Prompts are read at call time, so an edit reaches a running bot without a
restart — but the Python that supplies its variables does not. Adding an
input variable requires both, or the running process raises
`missing variables` on every call.
