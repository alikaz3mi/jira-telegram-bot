## Task assistant agent bypasses the prompt catalogue and the dependency rule

**Status:** open
**Raised:** 2026-08-31
**Severity:** architectural — no user-visible symptom yet
**Files:** `jira_telegram_bot/use_cases/assistant/task_assistant_agent.py`,
`jira_telegram_bot/config_dependency_injection.py`

### Problem

`TaskAssistantAgent` is the only LLM caller in the codebase that does not go
through the prompt catalogue or the AI-service port. It holds its prompt as a
Python string, imports LangChain directly from the use-case ring, and has its
model pinned at the dependency-injection site.

Nothing is broken for users today. It is listed here because each deviation
removes a guarantee the rest of the system relies on, and the cost lands later
— on whoever next tries to tune this prompt, swap its model, or reason about
what the assistant is actually instructed to do.

### Violations

#### 1. Prompt text lives in Python

`SYSTEM_PROMPT` at `task_assistant_agent.py:30` is a ~25-line triple-quoted
string.

`.claude/rules/prompts.md` requires every prompt to be a YAML file in
`adapters/ai_models/prompts/` with `id`, `version`, `language`, `temperature`,
`model_hint`, `model_engine`, `description`, `prompt`, `schemas` and
`input_variables`. The other 11 prompts comply.

What is lost:

- **No `version`.** The other prompts carry a dated version; this one cannot
  be diffed against a previous behaviour.
- **No `temperature`.** Every other prompt states it. This one inherits
  whatever the model object was built with.
- **No hot reload.** Catalogue prompts are read at call time, so an edit
  reaches a running bot without a restart. Editing this one requires a
  container restart, which is a different operational contract for no stated
  reason.

#### 2. A use case imports framework code

`task_assistant_agent.py:14-17` imports `langchain.agents.create_agent` and
three symbols from `langchain_core`.

The dependency rule in `.claude/CLAUDE.md` is that `use_cases` imports only
from `entities` and `use_cases/interfaces/`. Every other LLM use case reaches
the model through `AIServiceProtocol` and `PromptCatalogProtocol`.

**This file is not the only offender.** `use_cases/telegram_commands/board_summarizer.py`,
`use_cases/ai_agents/parse_jira_prompt_usecase.py` and
`use_cases/ai_agents/create_ticketing_issue.py` also import LangChain directly.
Any fix should decide whether to address all four or scope to the assistant.

#### 3. Model hardcoded in Python

`config_dependency_injection.py:1103`:

```python
model=c[LLMModelInterface]["openai", "gpt-4o-mini"],
```

`.claude/rules/prompts.md`: *"`model_hint` picks the model per prompt … Never
hardcode a model in Python."* Changing the assistant's model today means
editing wiring code rather than a prompt file.

### Why it happened

LangGraph's `create_agent` needs a live model object and callable tools. That
does not fit the shape the existing ports were built around —
`ai_service.run(prompt, inputs) -> dict` assumes a single structured call in
and parsed JSON out. An agent is a loop, not a call.

That explains the deviation but does not justify it. The alternative was to
extend the ports to cover a tool-using agent, or place the agent in
`adapters/ai_models/ai_agents/` behind a new port, and neither was attempted.

### Suggested fix

1. Move `SYSTEM_PROMPT` to `adapters/ai_models/prompts/task_assistant.yaml`
   with the required keys and a `model_hint`.
2. Add an agent port to `use_cases/interfaces/` — something taking a prompt id
   plus tool definitions and returning the final text — so the use case stops
   importing LangChain.
3. Move the `create_agent` call into an adapter implementing that port.
4. Have DI read the model from the prompt's `model_hint` instead of the
   literal at line 1103.

### Open question

The tool descriptions in `_build_tools` are Persian text the model routes on —
they are prompt content in everything but location. Decide whether they move
into the YAML alongside the system prompt, or stay in Python next to the
callables they describe. Splitting routing instructions across two files has
its own cost.

### Risk

The assistant path (`sprint_board`, `sprint_epics`, `my_briefing`,
`task_details`, `list_tasks`) is the most exercised part of the bot. This
refactor changes how its prompt and model are loaded without changing intended
behaviour, so it needs the live checks re-run afterwards, not only the unit
suite — the unit tests mock the agent and would stay green through a
regression here.
