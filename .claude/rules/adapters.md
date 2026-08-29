---
paths: ["jira_telegram_bot/adapters/**/*.py"]
---
# Adapters layer rules

Adapters implement the ports declared in `use_cases/interfaces/`. They may
import from `entities` and `use_cases`, never from `frameworks`.

## Jira

- All Jira access goes through `TaskManagerRepositoryInterface`.
- Custom field ids for this instance:

  | Field | Id |
  |---|---|
  | Epic Link | `customfield_10100` |
  | Epic Name | `customfield_10102` |
  | Sprint | `customfield_10104` |
  | Story Points | `customfield_10106` |
  | Target start | `customfield_10109` |
  | Target end | `customfield_10110` |
  | Delay Reason | `customfield_10600` |
  | Root Cause | `customfield_10601` |

- **Issue links return stubs.** `issue.fields.issuelinks[*].outwardIssue` has
  no `assignee` and no `description`; re-fetch the issue by key when you need
  them. A measurement built on the stub reports "no assignee" for every link.
- Wrap Jira calls in try/except and log the key. This instance returns 504 on
  slow endpoints often enough that one failure must not abort a batch.

## AI models

- `LangChainAiService` runs prompts from the catalogue and parses structured
  output. LangChain 1.x removed `StructuredOutputParser`; the pieces this repo
  uses live in `adapters/ai_models/structured_output.py`.
- Chains are built as `prompt | llm | parser`. `LLMChain` no longer exists.
- Model choice per prompt lives in the YAML `model_hint`, not in code:
  `gpt-4.1-nano` for cheap classification, `gpt-4o-mini` for parsing and
  answering.
