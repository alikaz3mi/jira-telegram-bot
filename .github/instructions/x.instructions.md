
---

## ❶ Sprint-Level Insights

*(stories #1, #2, #5, #8, #9)*

````yaml
---
mode: agent
description: Implement Sprint-level insights (completion-rate, status-breakdown, personal progress, workload heat-map) using existing Jira TaskManager repo, Postgres star-schema, and auto-scaffold endpoints.
tools: [terminalLastCommand, githubRepo, testFailure]
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
| **DTOs**                    | entities/report\_dtos/{sprint\_completion\_rate,task\_status\_breakdown,workload\_heatmap}\_dto.py                   |
| **Use-Cases**               | use\_cases/reports/{get\_sprint\_completion\_rate,get\_task\_status\_breakdown,get\_workload\_heatmap}\_use\_case.py |
| **Repo Interface (extend)** | **jira\_telegram\_bot/use\_cases/interfaces/task\_manager\_repository\_interface.py**                                |
| **Repo Impl (Postgres)**    | adapters/repositories/postgres/task\_manager\_postgres\_repository.py                                                |
| **Star-Schema Migrations**  | migrations/versions/xxxxx\_star\_schema\_{issues,projects,sprints,releases,worklogs}.sql                             |
| **Materialised Views (MV)** | migrations/versions/xxxxx\_mv\_{sprint\_metrics,task\_breakdown,workload}.sql                                        |
| **Tests**                   | tests/use\_cases/reports/…, tests/integration/api\_sprint\_insights/                                                 |
| **Docs**                    | docs/reports/sprint\_insights/                                                                                       |

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

````

---

## ❷ Release-Level Insights  
*(stories #3, #6, #7)*  

```yaml
---
mode: agent
description: Implement Release-level insights (high-priority blockers, release progress, blocking tasks) on issues · releases tables, plus Slack alert & audit log.
tools: [terminalLastCommand, githubRepo, testFailure]
---

# 🥅  Goal  
Expose three endpoints under `/projects/{project_key}/releases/{release_name}`:

| Path                                   | Purpose (stories)                     |
| -------------------------------------- | ------------------------------------- |
| **GET /blockers**                      | High-Priority Blockers (#3)           |
| **GET /progress_rate**                 | Release Progress Rate (#6)            |
| **GET /blocking_tasks**                | Blocking Tasks per Release (#7)       |

# 🛠  Step 0 · Scaffold the endpoints
```text
/fastapi-framework-endpoint:
  endpoint_name_pascal: ReleaseInsightsEndpoint
  use_case_names: GetHighPriorityBlockersUseCase,GetReleaseProgressRateUseCase,GetBlockingTasksForReleaseUseCase
  tag: Releases
  route_prefix: "/projects/{project_key}/releases/{release_name}"
  http_ops: "GET:/blockers  ,  GET:/progress_rate  ,  GET:/blocking_tasks"
  permission_classes:
````

# 📂  Additional Artefacts

| Artefact                    | Path                                                                                                                             |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| DTOs                        | entities/report\_dtos/{blocker\_issue,release\_progress,release\_blocking\_tasks}\_dto.py                                        |
| Use-Cases                   | use\_cases/reports/{get\_high\_priority\_blockers,get\_release\_progress\_rate,get\_blocking\_tasks\_for\_release}\_use\_case.py |
| Repo Interface/Impl         | **extend** task\_manager\_repository\_interface + postgres impl                                                                  |
| Slack adapter & Celery task | adapters/notifications/slack\_notification\_adapter.py, adapters/tasks/release\_alert\_task.py                                   |
| Audit log                   | adapters/repositories/postgres/audit\_log\_repository.py                                                                         |
| Tests & Docs                | tests/…, docs/reports/release\_insights/                                                                                         |

# 🔄  Tasks

1. **Repo extension** – add methods:

   * `get_release_scope(project_key, release_name)`
   * `count_release_completed_vs_total(release_name)`
   * `list_blocking_tasks(release_name)`
2. **Use-Cases** – implement logic; reuse common DTO patterns.
3. **Slack alert** – when blocker age > threshold; audit each alert.
4. **Endpoints** – paging on `/blockers` (query `limit`, `offset`).

# 🧪  Tests

```bash
/write-unit-tests: paths=jira_telegram_bot/use_cases/reports
/write-integration-tests: entry='make dev-up' paths=jira_telegram_bot/frameworks/api/endpoints/release_insights_endpoint.py
```

# 📚  Docs

`/generate-docs-instruction`

# ✅  Done-when

* Three endpoints work with tables **issues · releases** only.
* Slack-alert mock tested, audit row stored; coverage ≥ 90 %.

````

---

## ❸ Goals, API-Hub & Audit  
*(stories #4, #10, #11)*  

```yaml
---
mode: agent
description: Implement Sprint Goals storage, public GraphQL/REST metrics hub, and project-wide audit log endpoint.
tools: [terminalLastCommand, githubRepo, testFailure]
---

# 🥅  Goal  
Implement two endpoints and one GraphQL schema:

| Path / Schema                               | Purpose (stories)                           |
| ------------------------------------------- | ------------------------------------------- |
| **POST /…/goal + GET /…/goal**             | Sprint Goals/Targets widget (#4)            |
| **GET /metrics/graphql**                    | Unified GraphQL API for all metrics (#10)   |
| **GET /administration/audit**               | Paginated audit log (#11)                   |

# 🛠  Step 0-A · Sprint Goal endpoint
```text
/fastapi-framework-endpoint:
  endpoint_name_pascal: SprintGoalEndpoint
  use_case_names: SetSprintGoalUseCase,GetSprintGoalUseCase
  tag: Sprints
  route_prefix: "/projects/{project_key}/sprints/{sprint_id|active}"
  http_ops: "POST:/goal  ,  GET:/goal"
  permission_classes: IsProductOwner
````

# 🛠  Step 0-B · Audit endpoint

```text
/fastapi-framework-endpoint:
  endpoint_name_pascal: AuditEndpoint
  use_case_names: GetAuditLogUseCase
  tag: Administration
  route_prefix: "/administration"
  http_ops: "GET:/audit"
  permission_classes: IsAdmin
```

# 📂  Additional Artefacts

| Artefact                       | Path                                                                                                     |
| ------------------------------ | -------------------------------------------------------------------------------------------------------- |
| Sprint Goal Entity + Use-Cases | entities/sprint\_goal\_entities.py, use\_cases/sprints/{set,get}\_sprint\_goal\_use\_case.py             |
| GraphQL schema                 | frameworks/api/graphql/schema.py (strawberry)                                                            |
| Audit Repository + Use-Case    | adapters/repositories/postgres/audit\_log\_repository.py, use\_cases/audit/get\_audit\_log\_use\_case.py |
| Repo Interface/Impl            | extend task\_manager\_repository\_interface if sprint meta needed                                        |
| Migration                      | migrations/versions/xxxxx\_create\_table\_sprint\_goals.sql                                              |
| Tests / Docs                   | tests/…, docs/administration/                                                                            |

# 🔄  Tasks

1. **Sprint Goals table** – FK to `sprints` (id), not separate entity set.
2. **GraphQL** – expose resolvers reusing existing use-cases; mount at `/metrics/graphql`.
3. **Audit log** – unified table capturing config & alert actions; endpoint paginates.

# 🧪  Tests

```bash
/write-unit-tests: paths=jira_telegram_bot/use_cases/sprints,set sprint goal use case path…,jira_telegram_bot/use_cases/audit/get_audit_log_use_case.py
/write-integration-tests: entry='make dev-up' paths=jira_telegram_bot/frameworks/api/endpoints/sprint_goal_endpoint.py,jira_telegram_bot/frameworks/api/endpoints/audit_endpoint.py
```

# 📚  Docs

`/generate-docs-instruction`

# ✅  Done-when

* Goals saved & retrieved; GraphQL returns metrics; audit endpoint delivers paged data.
* All use only **issues · projects · releases · worklogs (+ sprint\_goals)** tables.
* Coverage ≥ 90 %, CI green.

```

---

### Key Adjustments (why these blocks meet your extra notes)

1. **Jira Layer** – No new interface; we *extend* the already-present `task_manager_repository_interface` and its default `jira_server_repository` implementation.  
2. **Database** – No bespoke tables like “task_status_breakdown”; all queries/MVs derive from **issues, projects, releases, sprints, worklogs** (star-schema). Sprint-specific data such as goals goes into a dedicated table **linked by `sprint_id`** only.  
3. **Endpoint Paths** – Every route now begins with explicit **`/projects/{project_key}/…`**, followed by **sprint_id | active** or **release_name**, making project/sprint/release context mandatory.  
4. **Story Coverage** – The three blocks jointly cover **all ten** original user-stories, grouping them by natural domain (Sprint, Release, Governance).  

Run the blocks in order ➊➋➌ to scaffold code, tests, and docs while keeping your architecture consistent and your existing Jira integration intact.
```
