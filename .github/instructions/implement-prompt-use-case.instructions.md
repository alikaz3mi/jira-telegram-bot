---
mode: agent
description: Scaffold a new AI-agent use-case (prompt, service, domain class, tests)
tools: [terminalLastCommand, codeBase, usages, testFailure, findTestFiles]
---

# 🛠️ Goal  
Generate all artefacts required to add a new AI-agent–driven use-case to **jira_telegram_bot**, while obeying every rule in `.github/copilot-instructions`:

1. **Prompt template** → `jira_telegram_bot/adapters/ai_models/ai_agents/prompts/<use_case_name>.yml`
2. **Service layer** → `jira_telegram_bot/adapters/ai_models/ai_agents/<use_case_name>_service.py`
3. **Domain use-case** → `jira_telegram_bot/use_cases/ai_agents/<use_case_name>.py`
4. **Unit tests** (≥ 90 % coverage) via `/write-unit-tests`
5. **Integration tests** (incl. concurrency) via `/write-integration-tests`

# 📝 Interactive variables  
* `${input:use_case_name:snake_case use-case name (e.g. story_decomposition)}`  
* `${input:prompt_author:Author id}`  
* `${input:model_hint:LLM preset (default: gemini-2.0-flash)}`

# 🔄 Workflow  

## 1 Generate prompt template  
Create a YAML file modelled on the **create_subtasks** example:

```yaml
# ── metadata ───────────────────────────────────────────
id: {{ use_case_name }}
version: "{{ now('%Y-%m-%d') }}"
language: en
author: {{ prompt_author }}
temperature: 0.3
model_hint: "{{ model_hint }}"
model_engine: "gemini"
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
input_variables: [...]
few_shots: []
output_style: >
  JSON only – match schemas exactly.
```

Ask the user for `brief_description` and `prompt_body` if not supplied.

## 2 Implement service class  
* Path: `jira_telegram_bot/adapters/ai_models/ai_agents/{{ use_case_name }}_service.py`
* Implement an async class `<CamelCase>Service` that **fulfils** the supplied Protocol.  
* Inject `PromptCatalogProtocol` & `AiServiceProtocol` via `__init__`.  
* Method `async def run(**kwargs) -> Dict[str, Any]` that:  
  1. Loads the prompt from the catalog,  
  2. Calls the AI service,  
  3. Returns parsed JSON (use `StructuredOutputParser`).  
* Add docstrings & type hints.

## 3 Domain use-case layer  
* Path: `jira_telegram_bot/use_cases/ai_agents/{{ use_case_name }}.py`  
* Expose a `@dataclass` command / handler (e.g. `{{ CamelCase }}UseCase`) that:  
  * Validates inputs,  
  * Delegates to the service,  
  * Transforms/returns domain DTOs.

## 4 Generate tests  
After code is scaffolded, **invoke**:

```
/write-unit-tests: paths={{ comma_separated_new_files }}
/write-integration-tests: entry='make dev-up' paths={{ comma_separated_new_files }}
```

The unit-test prompt will mirror package structure under `tests/`, while the integration-test prompt will add concurrency scenarios and CI targets.

## 5 Quality gates  
* Lint with `ruff` & type-check with `mypy`.  
* Ensure unit + integration coverage ≥ 90 %.  
* Confirm `pre-commit run --all-files` passes.

# 📤 Deliverables  
Reply with a **change summary** (paths created/updated).  
Do **not** include the generated code inline; it will be committed directly in the workspace.
