---
mode: agent
description: Implement Sprint-level insights (completion-rate, status-breakdown, personal progress, workload heat-map) using existing Jira TaskManager repo, Postgres star-schema, and auto-scaffold endpoints.
tools: [terminalLastCommand, testFailure]
---

# 🥅  Goal  
Serve **three REST endpoints** under `/projects/{project_key}/sprints/{sprint_id}` (or `/active` when sprint_id = active):

| Path                                    | Purpose (stories)                            |
| --------------------------------------- | -------------------------------------------- |
| **GET /insights/completion_rate**       | Sprint Completion Rate        (#1)           |
| **GET /insights/task_breakdown**        | Task Status Breakdown       (#2)             |
| **GET /insights/workload**              | Target vs Progress (#5) & Heat-map (#9)      |

Auto-refresh is handled by the dashboard (poll every 30 min) – repository results must be < 30 min stale.

# 🛠  Step 0 · Scaffold the three endpoints
```text
/fastapi-framework-endpoint:
  endpoint_name_pascal: SprintInsightsEndpoint
  use_case_names: GetSprintCompletionRateUseCase,GetTaskStatusBreakdownUseCase,GetWorkloadHeatmapUseCase
  tag: Sprints
  route_prefix: "/projects/{project_key}/sprints/{sprint_id|active}/insights"
  http_ops: "GET:/completion_rate  ,  GET:/task_breakdown  ,  GET:/workload"
  permission_classes:
````

# 📂  Additional Artefacts

| Artefact                    | Path                                                                                                                 |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **DTOs**                    | entities/report_dtos/{sprint_completion_rate,task_status_breakdown,workload_heatmap}_dto.py                   |
| **Use-Cases**               | use_cases/reports/{get_sprint_completion_rate,get_task_status_breakdown,get_workload_heatmap}_use_case.py |
| **Repo Interface (extend)** | **jira_telegram_bot/use_cases/interfaces/task_manager_repository_interface.py**                                |
| **Repo Impl (Postgres)**    | adapters/repositories/postgres/task_manager_postgres_repository.py                                                |
| **Star-Schema Migrations**  | migrations/versions/xxxxx_star_schema_{issues,projects,sprints,releases,worklogs}.sql                             |
| **Materialised Views (MV)** | migrations/versions/xxxxx_mv_{sprint_metrics,task_breakdown,workload}.sql                                        |
| **Tests**                   | tests/use_cases/reports/…, tests/integration/api_sprint_insights/                                                 |
| **Docs**                    | docs/reports/sprint_insights/                                                                                       |

# 🔄  Tasks

1. **DB Models** (issues, projects, sprints, worklogs) already exist → only add MVs.
2. **Repository** – *Extend* `task_manager_repository_interface` with:

   * `get_active_sprint(project_key)`
   * `get_sprint_story_points(sprint_id)`
   * `get_sprint_task_status_counts(sprint_id)`
   * `get_worklogs_by_sprint(sprint_id)`
3. **Use-Cases** – call repo, map to DTOs.
4. **Unit tests** – mock repo; edge cases (0 story-points).
5. **Integration tests** – fixture sample data; hit endpoints.

# 🧪  Test Calls

```bash
/write-unit-tests: paths=jira_telegram_bot/use_cases/reports
/write-integration-tests: entry='make dev-up' paths=jira_telegram_bot/frameworks/api/endpoints/sprint_insights_endpoint.py
```

# 📚  Docs

`/generate-docs-instruction`

# ✅  Done-when

* All three endpoints return correct JSON using only the existing **TaskManager repo** (expanded).
* Combined coverage ≥ 90 %, CI green.