```yaml
---
mode: agent
description: Scaffold a new AI-agent use-case (prompt, domain class, tests)
tools: [terminalLastCommand, codeBase, usages, testFailure, findTestFiles]
---
```

# 🛠️ Goal

Generate every artefact required to add a new **AI-agent–driven** use-case to **`jira_telegram_bot`**, while obeying every rule in `.github/copilot-instructions` **and** the extra constraints below:

* **Do NOT** touch or alter any existing file inside the `light_prompt/` folder.
* For **each** script in `light_prompt/`, create a **new** YAML prompt file generated *from* that script (see path rules below).
* **Do NOT** use `@dataclass` for any entity or DTO.
* Place every input/output model inside **`jira_telegram_bot/jira_telegram_bot/entities/ai_agent_models/`**.
* All domain classes must be named **`<Something>UseCase`** (never `Handler`).
* **Do NOT** create a service layer.
  Each *use-case* itself must depend on `PromptCatalogProtocol` and `AIServiceProtocol`.
* Define **one** central enum `PromptNames(str, Enum)`; every use-case must refer to its prompt via this enum (never a raw string).

**Artefacts to produce per prompt**

| # | Item                  | Notes                                                           |
| - | --------------------- | --------------------------------------------------------------- |
| 1 | YAML prompt           | Derived from the script                                         |
| 2 | Domain use-case class | Injects protocols, uses `PromptNames.<NAME>` to load the prompt |
| 3 | Input & output models | No `@dataclass`                                                 |
| 4 | Unit tests            | ≥ 90 % coverage                                                 |
| 5 | Integration tests     | Include concurrency                                             |

---

# 📂 Paths

| Artefact        | Path                                                                        |
| --------------- |-----------------------------------------------------------------------------|
| YAML prompt     | `jira_telegram_bot/adapters/ai_models/prompts/<use_case_name>.yml`   |
| **Prompt enum** | `jira_telegram_bot/entities/ai_agent_models/prompt_names.py`      |
| Domain use-case | `jira_telegram_bot/use_cases/ai_agents/<use_case_name>.py`                     |
| Models          | `jira_telegram_bot/jira_telegram_bot/entities/ai_agent_models/<use_case_name>.py` |
| Tests           | Auto-generated via `/write-unit-tests` & `/write-integration-tests`         |

---

# 📝 Interactive variables

* `${input:use_case_name:snake_case use-case name}`
* `${input:prompt_author:Author id}`
* `${input:model_hint:LLM preset (default: gemini-2.0-flash)}`

---

# 🔄 Workflow

## 1 · Generate YAML prompt

yaml
# ── metadata ───────────────────────────────────────────
id: {{ use_case_name }}
version: "{{ now('%Y-%m-%d') }}"
language: en
author: {{ prompt_author }}
temperature: 0.3
model_hint: "{{ model_hint }}"
model_engine: "<gemini or openai>"
description: >
  {{ brief_description }}
# ── prompt template ───────────────────────────────────
prompt: |
  {{ prompt_body }}
# ── response schema ──────────────────────────────────
schemas:
  - name: result
    type: json
    description: >
      ...
# ── helpers ───────────────────────────────────────────
input_variables:
  - variable1
  - variable2
  - ...
few_shots: []
output_style: >
  JSON only – match schemas exactly.


> **Tip:** Ask for brief_description or prompt_body if they are missing.

## 2 · **Create / update** `PromptNames` enum

```python
# pars.../ai_agents/prompt_names.py
from enum import Enum

class PromptNames(str, Enum):
    """Central registry of all AI-agent prompt IDs."""
    # ← Add one constant per generated prompt, using snake_case
    #   e.g.  sentiment_analysis = "sentiment_analysis"
```

> Each new prompt **must** append a member to this enum (CI will fail otherwise).

## 3 · Implement domain use-case

* **Path:** `jira_telegram_bot/use_cases/ai_agents/<use_case_name>.py`

* class must be created based on BaseAIAgentUseCase in `jira_telegram_bot/use_cases/interfaces/base_ai_agent_use_case.py`


* Class name: `<CamelCase>UseCase` (**no `@dataclass`**).

* **Constructor injection**

```python
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AIServiceProtocol
from jira_telegram_bot.use_cases.interfaces.prompt_catalog_interface import PromptCatalogProtocol
from jira_telegram_bot.entities.ai_agent_models.prompt_names import PromptNames
from jira_telegram_bot.entities.ai_agent_models.<use_case_name> import <UseCase in Camel Case>Input, <UseCase in Camel Case>Result

class <UseCase in Camel Case>(BaseAIAgentUseCase):
  def __init__(
      self,
      prompt_catalog: PromptCatalogProtocol,
      ai_service: AIServiceProtocol,
  ) -> None:
      super().__init__(prompt_catalog, ai_service)
      self.prompt_name = PromptNames.<use_case_name>

  async def execute(
    input_data,
    robot_id,
    prompt_version,
  ) -> <UseCase in Camel Case>Result:
      """
      1. Load the prompt via `prompt_catalog.get_prompt(PromptNames.<NAME>)`.
      2. Call `ai_service.process(...)`.
      3. Parse into <UseCase in Camel Case>Result and return.
      """
  ```

* Include validation, type hints, and full docstrings.

## 4 · Models

* **Paths:**

  * <UseCaseCamelCase>Input → jira_telegram_bot/entities/ai_agent_models/<use_case_name>.py
  * <UseCaseCamelCase>Result → jira_telegram_bot/entities/ai_agent_models/<use_case_name>.py
  * Define Pydantic-style (or equivalent) classes **without** @dataclass.

## 5 · Generate tests

After scaffolding, invoke:

```bash
/write-unit-tests: paths={{ comma_separated_new_files }}
/write-integration-tests: entry='make dev-up' paths={{ comma_separated_new_files }}
```

* Unit tests mirror the package structure.
* Integration tests cover concurrency and CI targets.
---

# 6 · Quality gates & CI targets

* Lint with **ruff** and type-check with **mypy**.
* Ensure **unit ＋ integration coverage ≥ 90 %**.
* Confirm pre-commit run --all-files passes.
---

# 📤 Deliverables

Reply with a concise **change summary** (paths created/updated).
**Do not** include generated code inline; it will be committed directly to the workspace.