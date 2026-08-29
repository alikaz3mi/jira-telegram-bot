---
paths: ["jira_telegram_bot/use_cases/**/*.py"]
---
# Use Cases layer rules

- One public entry point per class: `execute()`.
- Depends only on `*Interface` ports from `use_cases/interfaces/` and on
  entities. Never import from `adapters` or `frameworks`.
- All dependencies arrive by constructor injection.
- Inputs and outputs are entities and simple types.

## Use cases that call an LLM

- The prompt is a YAML file in `adapters/ai_models/prompts/`, loaded through
  the prompt catalogue. Never an f-string in the use case.
- The use case validates what comes back. A model returning a date, an hour
  count or an index is a suggestion, not a fact:
  - dates in the future are dropped
  - indices outside the candidate list are dropped
  - totals that do not add up are surfaced, not silently corrected
- Failure returns an empty or neutral result and logs. A use case that raises
  because a model misbehaved turns a bad answer into a dead conversation.

## Filtering a list

When a use case narrows a list, anything discarded is counted and logged.

`_determine_check_status` once returned `OK` for any task with no Target start
date, so undated sprint work disappeared: 8 of 47 issues survived and the
assistant answered "you have no tasks" with confidence. Silence about what was
removed is what made it a bug rather than a limitation.
