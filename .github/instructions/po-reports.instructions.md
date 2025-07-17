---
mode: agent
description: Scaffold the complete metrics‑tracking feature set (Daily Scoreboard, Developer Metrics Matrix, Web‑hook ingestion) inside **`jira_telegram_bot`**, fully aligned with the Clean‑Architecture rules and Copilot Custom Instructions.
tools: [terminalLastCommand, codeBase, usages, testFailure, findTestFiles]
---

# 🛠️ Goal
Generate every artefact required to satisfy **Epics 1–3** in the user story:

1. **Daily Scoreboard** (sheet #1) – real‑time, idempotent, per‑dev daily metrics with creating sheet per Persian calendar month.   ![image1](docs/sheet1.png)
2. **Developer Metrics Matrix** (sheet #2) – cumulative sprint metrics with creating sheet per sprint.   ![image2](docs/sheet2.png)
3. **Web‑hook ingestion** – Jira & GitLab events → idempotent sheet
3. **Integration & Infrastructure** – FastAPI web‑hook endpoints, resilient Google‑Sheets adapter, retry logic, 90 %+ test coverage.

_All code must obey the Clean‑Architecture directory boundaries, the coding conventions in Copilot Custom Instructions, and achieve `ruff --fix`, `mypy --strict`, `pytest --cov ≥ 90 %`, passing CI._

---

# 📂 Paths
| Artefact | Path |
| ----------------------------------------------------- | --------------------------------------------------------------- |
| **Domain entities** (pure Pydantic models) | `jira_telegram_bot/entities/metrics/*.py` |
| **Use‑cases** (business logic) | `jira_telegram_bot/use_cases/metrics/*.py` |
| **Interfaces** (contracts) | `jira_telegram_bot/use_cases/interfaces/metrics/*.py` |
| **Adapters** (Google‑Sheets / Jira / GitLab) | `jira_telegram_bot/adapters/*/*.py` |
| **Frameworks** (FastAPI web‑hooks) | `jira_telegram_bot/frameworks/fast_api/webhooks/*.py` |
| **Retry utilities & constants** | `jira_telegram_bot/utils/*` |
| **Unit tests** | `tests/use_cases/metrics/*` |
| **Integration tests** | `tests/integration/metrics/*` |
| **Docs** | `docs/metrics/*.md` |

---

# 🔄 Workflow
## 1 · Domain design
* Create immutable Pydantic entities representing **MetricEvent**, **DailyMetricRow**, **SprintMetricRow**, etc.
* Define **MetricType(Enum)** and **SheetName(Enum)** in `entities/constants.py`.

## 2 · Interfaces
* `SpreadsheetGatewayInterface` with `append_rows()` and `update_cells()` (async).  
* `UserSettingConfigurationRepositoryInterface` for Jira⇄GitLab⇄Sheet row resolution.  
* `MetricsProcessorInterface` responsible for idempotent event → sheet mutations.

## 3 · Use‑cases
### a. `ProcessJiraEventUseCase`
* Maps Jira web‑hook payloads to `MetricEvent` instances for Epics 1 & 2 metrics. (Currently implemented in jira_telegram_bot/use_cases/webhooks/jira_webhook_use_case.py)

### b. `ProcessGitlabEventUseCase`
* Same for GitLab events (MR opened/merged/closed, commits).

### c. `UpdateSheetUseCase`
* Consumes `MetricEvent`, fetches row/column from repository, performs atomic update through `SpreadsheetGatewayInterface` with exponential back‑off (max 5 retries).

*All use‑cases live in `jira_telegram_bot/use_cases/metrics/` and are injected via **Lagom**.*

## 4 · Adapters
* **GoogleSheetsGateway** – authenticates with service‑account JSON (from settings), implements the gateway interface, guarantees atomicity with batch updates.
* **JiraEventAdapter** & **GitlabEventAdapter** – translate native payloads to `MetricEvent`.  

## 5 · Frameworks
* `/webhooks/jira` & `/webhooks/gitlab` FastAPI routes in `jira_telegram_bot/frameworks/fast_api/webhooks/`.  (some of them are implemented in `jira_telegram_bot/frameworks/fast_api/webhooks/`)
  * Token‑auth, enqueue event to background task (anyio queue) → decouples HTTP from processing.

## 6 · Retry & Idempotency
* Decorator `@retry_async(exceptions=(TransientGoogleError,), tries=5, backoff=2)`.  
* `IdempotencyRepository` (in‑memory Redis placeholder) stores `<event_id, metric_key>` pairs for 24 h.

## 7 · Tests
* **Unit tests**: ≥ 90 % coverage of mapping & idempotency logic (happy & sad paths).  
* **Integration tests**: POST 20 concurrent web‑hooks -> assert exactly one consistent sheet update.

## 8 · Documentation
* One markdown per use‑case in `docs/metrics/` containing data‑flow diagram (ASCII‑SVG or Mermaid) and settings matrix.

---

# 📝 Interactive variables
* `${input:sprint_sheet_id:Google‑Sheet ID for sprint matrix}`
* `${input:daily_sheet_id:Google‑Sheet ID for daily scoreboard}`

---

# 🏁 Post‑generation commands
After scaffolding code & docs, run:

/write-unit-tests: paths=ALL_NEW_PY_FILES
/write-integration-tests: entry='make ci-test' paths=ALL_NEW_PY_FILES
/generate-docs-instruction

yaml
Copy
Edit

These commands will generate the concrete test suites and documentation skeletons.

---

# ✅ Definition of Done checklist
- [ ] Clean‑Architecture boundaries respected (entities → use_cases → adapters → frameworks).
- [ ] Google‑Sheets IDs & service‑account path injected via settings classes.
- [ ] `ruff --fix`, `mypy --strict`, `pytest --cov` ≥ 90 %, CI green.
- [ ] Sprint reset logic proven by tests.
- [ ] Docs in `docs/metrics/` thoroughly describe each use‑case and data‑flow.
