---

mode: agent
description: Implement a Sprint-Close → Team Evaluation updater (Webhook + CLI) that writes metrics to Google Sheets
tools: [terminalLastCommand, codeBase, usages, testFailure, findTestFiles]
-----------------------------------------

# 🛠️ Goal

When a **Jira sprint is closed**, compute per-developer metrics for that sprint and **upsert** rows into a specified **Google Sheets** tab. Also provide a **CLI/runner** so the same update can be executed on demand with parameters. Follow the repository’s Clean Architecture rules and Copilot Custom Instructions exactly.

This feature lives under:

* **Use case:** `jira_telegram_bot/use_cases/team_evaluation`
* **Webhook endpoint:** `jira_telegram_bot/frameworks/api/endpoints/jira_webhook.py` (extend existing FastAPI setup per `/fast-api-instruction`)
* **Google Sheets adapters/settings:** reuse and extend:

  * `jira_telegram_bot/adapters/gateways/google_sheets/google_sheets_gateway.py`
  * `jira_telegram_bot/adapters/google_sheet.py`
  * `jira_telegram_bot/settings/google_sheets_settings.py` (add a dedicated settings class for this use case, see below)
* **Jira repository:** use `jira_telegram_bot/adapters/repositories/jira/jira_server_repository.py`
* **User config for Farsi display names:** `jira_telegram_bot/adapters/user_config.py`

# 📝 Interactive variables

Expose these as inputs for both CLI and DI settings:

* `${input:sheet_id}` – Google Sheet ID (default: the provided sheet).
* `${input:tab_name}` – Target tab name (default: “Team Evaluation” or existing).
* `${input:project_key}` – Jira project key(s), comma-separated.
* `${input:sprint_id}` – Jira sprint ID to compute; if omitted in CLI, derive from `${input:sprint_name}`.
* `${input:sprint_name}` – Optional sprint name (fallback when id not provided).
* `${input:weekly_hours}` – Expected weekly work hours (default **46**).
* `${input:workdays}` – Workdays as 0–6 array, where Saturday=6 or Saturday=0 depending on your calendar; default company workweek **Sat–Thu** (6 days).
* `${input:dept_inference}` – Strategy for department detection: `component|label|user_config` (default `component`, with fallback chain).
* `${input:score_weights}` – JSON for حسن انجام کار weighting; default provided below.
* `${input:defect_thresholds}` – JSON thresholds for defect penalties.
* `${input:expected_hours_mode}` – `weekly|total` (default `weekly`).
* `${input:timezone}` – IANA TZ (default from settings, e.g., `Asia/Tehran`).
* `${input:dry_run}` – If true, compute but do not write.

All inputs must be injectable via `TeamEvaluationSettings` (see Settings) and overridable by CLI args.

# 📊 Data dictionary (columns to write)

Use **exact column order** below (Farsi headers), idempotently upsert by `(توسعه دهنده, پروژه, اسپرینت)`:

1. **توسعه دهنده** – Developer Farsi display name (`user_config.google_sheet_name`).
2. **دپارتمان** – Comma-separated union of departments the user worked on in the sprint.
3. **پروژه** – Jira project name (or key).
4. **اسپرینت** – Sprint name.
5. **توسعه** – Count of issues with type in `{Task, Sub-task, Improvement}` assigned to the user and in the sprint.
6. **باگ** – Count of issues with type `Bug`.
7. **پشتیبانی** – Count of issues labeled `Support` **or** epic name is `پشتیبانی`.
8. **تسکهای اولویت بالا** – Count of `{Task, Sub-task, Improvement}` with priority `Highest`.
9. **زمان ثبت شده هفته** – Sum of worklogs (hours) in the sprint week.
10. **زمان انتظاری هفته** – Expected hours for the same week, computed from calendar JSON (see Algorithm).
11. **زمان باگ** – Worklog hours on `Bug` issues.
12. **زمان توسعه** – Worklog hours on `{Task, Sub-task, Improvement}`.
13. **زمان پشتیبانی** – Worklog hours on support issues (label `Support` or epic `پشتیبانی`).
14. **میانگین ددلاین دلیوری به ساعت** – Avg(`delivery_time - due_date`) in hours; negative = early.
15. **بازگشت از مرور به بک لاگ** – Count of status transitions from any “Review” status back to `{Backlog, To Do, In Progress}`.
16. **درصد پاس شدن تست استوری** – Leave empty (`""`).
17. **درصد پاس شدن معیارهای پذیرش** – Leave empty (`""`).
18. **تسکهای اولویت بالا تکمیل شده** – Count of `Highest` priority items moved to `Done` in sprint.
19. **میانگین باگهای ثبت شده برای استوری های از پشتیبانی** – Count of Bugs with label `Support` or epic `پشتیبانی` **related to** the user’s delivered stories, normalized per delivered story (see Algorithm).
20. **میانگین باگهای ثبت شده در یوزر استوری توسط تستر** – Count of Bugs with label `tester` linked to the user’s delivered stories, normalized per delivered story.
21. **توسعه تحویل داده شده** – Count of delivered `{Task, Sub-task, Improvement}` (status `Done` in sprint).
22. **باگ تحویل داده شده** – Count of `Bug` moved to `Done` in sprint.
23. **پشتیبانی تحویل داده شده** – Count of support issues delivered in sprint.
24. **درصد حسن انجام کار** – Composite score 0–100 (formula below; round to int).

# 🔄 Workflow

1. **Domain Entities** (`jira_telegram_bot/entities`)

   * `TeamEvaluationRow` – fields for the 24 columns above.
   * `SprintClosedEvent` – `{ sprint_id: int, sprint_name: str, project_keys: list[str], ended_at: datetime }`.
   * `WorklogSlice` – `{ issue_key: str, author: str, started_at: datetime, hours: float }`.
   * `IssueSnapshot` – minimal projection used by the use case (typed fields only).
   * `Department` Enum, `IssueTypeGroup` Enum, `StatusGroup` Enum, `PriorityLevel` Enum.
   * `TeamEvaluationScoreWeights` – `{deadline: float, worklog: float, high_priority: float, defects: float}` (sum=1).

2. **Interfaces** (`jira_telegram_bot/use_cases/interfaces`)

   * `TaskManagerRepositoryInterface` (reuse or extend) – async methods:

     * `get_sprint(sprint_id: int) -> Sprint`
     * `get_sprint_issues(project_keys: list[str], sprint_id: int) -> list[IssueSnapshot]`
     * `get_issue_worklogs(issue_keys: list[str]) -> list[WorklogSlice]`
     * `get_issue_changelogs(issue_keys: list[str]) -> dict[str, list[ChangeLogEvent]]`
     * `get_issue_epic(issue_key: str) -> Optional[str]`
   * `GoogleSheetGatewayInterface` – async methods:

     * `upsert_rows(sheet_id: str, tab_name: str, rows: list[TeamEvaluationRow], upsert_keys: tuple[str, str, str]) -> None`
   * `UserConfigInterface` (reuse) – resolve Farsi names and optional department defaults:

     * `get_google_sheet_name(jira_account_id: str) -> str`
     * `infer_departments(user: str, issue: IssueSnapshot) -> set[str]`
   * `CalendarRepositoryInterface` – read `data/storage/{year}.json`:

     * `get_holidays(year: int) -> set[date]`
     * `get_disabled_days(year: int) -> set[date]`
     * `get_calendar_header(year: int, month: int) -> dict`
   * `LeaveRepositoryInterface` – **placeholder only**; methods defined but return empty for now.

3. **Use Case** (`jira_telegram_bot/use_cases/team_evaluation`)

   * `ComputeTeamEvaluationUseCase` (async):

     * Inputs: `sheet_id, tab_name, project_keys, sprint_id|sprint_name`.
     * Flow:

       1. Resolve sprint (dates, name, id).
       2. Fetch sprint issues, worklogs, and changelogs in one or few paginated calls.
       3. Group by assignee; map to Farsi names via `UserConfigInterface`.
       4. Derive department union per user across issues.
       5. Compute all metrics (Algorithm section).
       6. Build `TeamEvaluationRow` list.
       7. `GoogleSheetGatewayInterface.upsert_rows(...)` with upsert keys `(توسعه دهنده, پروژه, اسپرینت)`.
   * `RunTeamEvaluationCliUseCase` (sync wrapper calling async) to support CLI.

4. **Adapters**

   * Jira: reuse `jira_server_repository.py`; extend if needed to expose batched:

     * issue fields: `issuetype`, `priority`, `labels`, `components`, `epic`, `duedate`, `status`, `assignee`, `project`, `changelog.transitions`, `worklogs`.
   * Google Sheets: reuse existing gateway; if missing upsert, add:

     * Upsert by scanning the tab for key triplets and updating existing rows; otherwise append.
   * Calendar: implement a small file-reader under `jira_telegram_bot/adapters/repositories/calendar/json_calendar_repository.py`.
   * Leave: stub `json_leave_repository.py` with empty returns (placeholders).
   * Department inference: in `user_config.py`, expose a helper or mapping for department labels; otherwise a fallback based on `components` or presence of labels like `Backend, DevOps, Frontend, Data, Product`.

5. **API/Webhook** (`frameworks/api/endpoints/jira_webhook.py`)

   * Extend FastAPI endpoint to handle Jira board events.
   * Detect **sprint closed** event (`sprint.state == "closed"` or payload type `sprint_closed`).
   * Extract `sprint_id`, `sprint_name`, `project_keys` (from board or issues), `ended_at`.
   * Call `ComputeTeamEvaluationUseCase` with DI-injected settings (sheet id, tab).
   * Return 202 on accepted.

6. **Settings** (`jira_telegram_bot/settings/team_evaluation_settings.py`)

   * Create `TeamEvaluationSettings(BaseSettings)`:

     * `sheet_id: str`
     * `tab_name: str = "Team Evaluation"`
     * `weekly_hours: float = 46.0`
     * `workdays: tuple[int, ...] = (6, 0, 1, 2, 3, 4)`  # Sat–Thu; adjust to your weekday numbering
     * `expected_hours_mode: Literal["weekly","total"] = "weekly"`
     * `dept_inference: Literal["component","label","user_config"] = "component"`
     * `timezone: str = "Asia/Tehran"`
     * `score_weights: TeamEvaluationScoreWeights = {deadline:0.35, worklog:0.25, high_priority:0.20, defects:0.20}`
     * `defect_thresholds: dict = {"support_per_story": 0.3, "tester_per_story": 0.4, "max_penalty": 60}`
   * Bind via Lagom in `config_dependency_injection.py` and `app_container.py`.

7. **CLI entrypoint** (`jira_telegram_bot/frameworks/cli/team_evaluation_cli.py`)

   * Parse args mirroring Interactive variables; call `RunTeamEvaluationCliUseCase`.

8. **Tests** (`tests/use_cases/team_evaluation/`)

   * Mock Jira repo, Sheets gateway, Calendar & Leave repos, UserConfig.
   * Cover success paths, missing due dates, no worklogs, mixed departments, multi-project sprints, idempotent upsert behavior, and webhook payload variations.
   * Provide sample calendars in `tests/samples/calendars/{year}.json`.

9. **CI/Quality**

   * PEP-8, docstrings only (no inline comments), full typing.
   * ≥ 90% coverage for the new use cases and adapters.

# 🧮 Algorithm & rules

## 1) Grouping & classification

* **Issue groups**

  * `DEV_GROUP = {Task, Sub-task, Improvement}`
  * `BUG_GROUP = {Bug}`
  * `SUPPORT_GROUP` = issues with label `Support` **or** epic name (case-insensitive, normalized) equals `پشتیبانی`.
* **High priority** = `priority.name == "Highest"`.
* **Delivered** = first transition to any status in `Done` category **during the sprint timebox**. If not available, fallback to `resolutiondate` if within sprint timebox.
* **Department inference**

  * Strategy order: if `dept_inference=="component"` use Component names; else if `label` search labels; else `user_config` mapping.
  * Union all departments the user touched within the sprint; join by `, `.

## 2) Worklogs

* Fetch worklogs for all sprint issues (batch).
* **زمان ثبت شده هفته**: Sum hours of worklogs whose `started_at` falls within the **calendar week** of `sprint.endDate` in `timezone`.
* **زمان باگ / توسعه / پشتیبانی**: Same, but restricted by issue group (Bug / Dev / Support).

## 3) Expected hours (“زمان انتظاری هفته”)

* Read `data/storage/{year}.json`; derive holidays/disabled days in the **week containing sprint.endDate**.
* Company weekly hours = `${input:weekly_hours}` (**46**).
* Workdays = `${input:workdays}` (**6 days** Sat–Thu).
* `daily_hours = weekly_hours / len(workdays)`.
* Count business days in that week, excluding holidays from the JSON and **excluding placeholder leaves** returned by `LeaveRepositoryInterface` (currently empty).
* `expected_hours = business_days * daily_hours`.
* If `expected_hours_mode == "total"` and sprint spans multiple weeks, sum per-week expected hours across the sprint.

## 4) Deadline delivery delta (hours)

* For each delivered issue with a `duedate`:

  * `delta_hours = (delivery_time - due_date) in hours` (use TZ-aware datetimes, floor to integer).
* Average across a developer’s delivered issues in the sprint.
* If no due dates, store empty string.

## 5) “Review → Back” regressions

* From changelogs, count transitions whose **fromStatus ∈ {"Review","In Review","Code Review"}** and **toStatus ∈ {"Backlog","To Do","In Progress"}**.
* Sum per developer.

## 6) High-priority completion counts

* `High priority completed` = number of `Highest` issues delivered in sprint.

## 7) Support/tester bug metrics (means)

* Consider **bugs linked** to delivered stories in the sprint:

  * “Related to” = bug has `relates to` link to a delivered story **or** is in the same epic as a delivered story.
* **Support bugs per delivered story**:

  * Count bugs with label `Support` or epic `پشتیبانی` related to delivered stories; divide by number of delivered stories (DEV_GROUP delivered). Use 0 if denominator is 0.
* **Tester bugs per delivered story**:

  * Count bugs with label `tester`; divide by delivered stories similarly.

## 8) حسن انجام کار (composite score, 0–100)

* Let:

  * `S_deadline = clamp(100 - max(0, avg_delta_hours_late) * k_deadline, 0, 100)`, with `k_deadline = 2.0 / 1h` (2 points penalty per late hour; early delivery does not increase >100).
  * `S_worklog = clamp(100 * min(registered_hours / expected_hours, 1.0), 0, 100)`.
  * `S_high = 100 * (completed_highest / max(total_highest,1))` if total_highest>0 else 100.
  * `support_rate = support_bugs_per_story` and `tester_rate = tester_bugs_per_story`.
  * `defect_penalty = min( (support_rate / T_support)*30 + (tester_rate / T_tester)*30, max_penalty )`, where defaults from `${input:defect_thresholds}` are `T_support=0.3`, `T_tester=0.4`, `max_penalty=60`.
  * `S_defects = 100 - defect_penalty`.
* Compute:

  * `Score = round( 100 * ( w_deadline*S_deadline + w_worklog*S_worklog + w_high*S_high + w_defects*S_defects ) / 100 )`
* Default weights:

  * `w_deadline=0.35, w_worklog=0.25, w_high=0.20, w_defects=0.20`.

All numeric fields should be integers where obvious (counts) and 1-decimal precision for means; blank strings for “to be implemented” columns.

# 📄 Google Sheets write protocol

* **Upsert key:** `(توسعه دهنده, پروژه, اسپرینت)`.
* Ensure header row exists; create if missing.
* Batch updates in ≤ 500 rows per call.
* Respect rate limits with exponential backoff.
* If `${input:dry_run}` is true, log computed rows via the configured `LOGGER` and skip writes.

# 🌐 Webhook flow

1. Receive Jira webhook in `jira_webhook.py`.
2. Validate payload & signature if configured.
3. If event indicates **sprint closed**:

   * Extract `sprint_id`, `sprint_name`, `ended_at`, and derive `project_keys` (from board or issue list).
   * Invoke `ComputeTeamEvaluationUseCase` with DI-bound settings.
4. Respond with HTTP 202 and a short JSON.

# ⚙️ Dependency Injection

Add bindings in `config_dependency_injection.py` and `app_container.py`:

* `TaskManagerRepositoryInterface` → Jira adapter
* `GoogleSheetGatewayInterface` → Google sheets gateway adapter
* `CalendarRepositoryInterface` → JSON calendar adapter
* `LeaveRepositoryInterface` → JSON leave adapter (stub)
* `UserConfigInterface` → existing adapter
* `TeamEvaluationSettings` → from env

# 🧪 Tests (unittest)

* `tests/use_cases/team_evaluation/test_compute_team_evaluation_use_case.py`

  * `test_a_computes_all_columns_happy_path`
  * `test_a_idempotent_upsert_same_sprint`
  * `test_a_no_due_dates_sets_blank_deadline_delta`
  * `test_a_expected_hours_excludes_holidays`
  * `test_a_support_and_tester_bug_rates_normalized`
  * `test_a_department_inference_fallbacks`
  * `test_a_handles_multi_project_sprint`
* `tests/frameworks/api/test_jira_webhook_sprint_closed.py`

  * Parse payloads with/without sprint id; ensure UC called once.
* Use factories under `tests/samples/` for issues, worklogs, calendars.


# 🧱 Function signatures (sketch; docstrings only, full typing, no inline comments)

* `ComputeTeamEvaluationUseCase.run(sheet_id: str, tab_name: str, project_keys: list[str], sprint_id: Optional[int], sprint_name: Optional[str]) -> list[TeamEvaluationRow]`
* `CalendarService.calculate_expected_hours(week_start: date, week_end: date, weekly_hours: float, workdays: tuple[int,...]) -> float`
* `ClassificationService.classify_issue(issue: IssueSnapshot) -> IssueTypeGroup`
* `ChangelogService.count_review_regressions(events: list[ChangeLogEvent]) -> int`
* `DeadlineService.average_deadline_delta_hours(issues: list[IssueSnapshot]) -> Optional[float]`
* `DefectService.compute_defect_scores(delivered_stories: list[IssueSnapshot], bugs: list[IssueSnapshot]) -> tuple[float, float]`
* `ScoreService.compute_hosn_score(weights: TeamEvaluationScoreWeights, ...) -> int`

Break long functions per rules; extract constants/enums to `entities/constants.py` if needed.

# 🧯 Error handling

* Use custom exceptions in `jira_telegram_bot/utils/exceptions.py`.
* Distinguish: configuration errors, Jira API errors, Sheets API errors, and validation errors.
* Propagate with actionable messages; log once per failure path.

# 🔐 Idempotency

* Upsert by key triplet; do not duplicate rows across replays.
* If sprint re-closed or webhook delivered multiple times, UC is safe to re-run.

# ➕ Optional extension (deferred)

* Emit a compact JSON artifact per sprint to `data/team_evaluation/{sprint_id}.json`.
* Index rows into Elasticsearch `team_evaluation-*` for analytics (separate adapter).

# ✅ Deliverables

1. **Runnable code** (CLI + Use Case + Adapters + Settings + Tests) that writes computed rows to the configured Google Sheet tab.
2. **Webhook path** integrated into `jira_telegram_bot/frameworks/api/endpoints/jira_webhook.py`, wired to trigger the use case on **sprint closed**.

# 📤 Meta-commands

/write-unit-tests
/write-integrated-tests
/generate-docs
