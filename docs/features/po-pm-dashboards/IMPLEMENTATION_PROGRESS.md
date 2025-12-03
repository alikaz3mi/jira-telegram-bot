# PO/PM Dashboard Implementation Progress

## Overview
Implementation of real-time Jira synchronization to PostgreSQL for PO/PM dashboards in Grafana.

## Completed ✅

### Phase 1: Enhanced Issue Update Handling (75% Complete)

#### 1. SyncJiraIssueUseCase ✅
**Location:** `jira_telegram_bot/use_cases/sync_jira_issue_use_case.py`

- Created real-time webhook-triggered sync use case
- Handles critical events: `issue_created`, `issue_updated`, `issue_resolved`, `issue_reopened`, `issue_closed`, `worklog_updated`
- Methods:
  - `sync_issue_from_webhook()` - Real-time single issue sync
  - `bulk_sync_issues()` - Batch sync with full/incremental modes
  - `_fetch_updated_issues()` - Incremental sync logic (placeholder)
  - `_update_sync_status_after_webhook()` - Track webhook sync stats
  - `_update_sync_status_after_bulk()` - Track batch sync stats

#### 2. SyncStatus Entity ✅
**Location:** `jira_telegram_bot/entities/sync_status.py`

- Pydantic model tracking sync operations
- Fields: project_key, last_full_sync, last_incremental_sync, sync_status, issues_synced/failed, duration, errors

#### 3. Database Migration ✅
**Location:** `jira_telegram_bot/adapters/repositories/postgres/database/migrations/migration_002_add_sync_status.py`

- Created `sync_status` table with:
  - project_key (PK)
  - Sync timestamps (full + incremental)
  - Success/failure tracking
  - Error logging (JSONB)
  - Indexed for query performance
- Migration status: **Applied successfully** ✅

#### 4. Repository Updates ✅
**Location:** `jira_telegram_bot/adapters/repositories/postgres/jira_report_repository.py`

- Added `SyncStatusModel` ORM model
- Implemented methods:
  - `get_sync_status()` - Retrieve sync state by project
  - `update_sync_status()` - Update sync tracking
- Updated interface with new methods

#### 5. Bug Fixes ✅
- Fixed migration runner import paths (`adapters.database` → `adapters.repositories.postgres.database`)
- Fixed `scripts/run_migrations.py` import path
- Converted migration methods to `@property` decorators

---

## In Progress 🔄

### Webhook Integration
**Status:** Use case ready, needs integration with `ProcessJiraEventUseCase`

**Current State:**
- `SyncJiraIssueUseCase` fully implemented
- Ready to be called from webhook handler
- Needs DI wiring

**Next Steps:**
1. Inject `SyncJiraIssueUseCase` into `ProcessJiraEventUseCase`
2. Call `sync_issue_from_webhook()` after Google Sheets update
3. Test with live webhook events

---

## Pending ⏳

### 1. Incremental Sync Enhancement
**Complexity:** Medium
**Dependencies:** JiraDataService enhancement

**Tasks:**
- Implement `fetch_updated_issues(project_key, since_timestamp)` in JiraDataService
- Use JQL query: `project = {key} AND updated >= {timestamp}`
- Update `_fetch_updated_issues()` in SyncJiraIssueUseCase to use new method

### 2. Dependency Injection Configuration
**Complexity:** Low
**File:** `config_dependency_injection.py`

**Tasks:**
```python
# Add to container
container[SyncJiraIssueUseCase] = Singleton(
    lambda: SyncJiraIssueUseCase(
        jira_service=container[JiraDataServiceInterface],
        report_repository=container[JiraReportRepositoryInterface],
    )
)
```

### 3. Grafana SQL Views for Dashboards
**Complexity:** High
**Priority:** High (user needs these for dashboard building)

**Required Views:**

#### PO Metrics Views:
1. **Sprint Velocity Trend**
   ```sql
   CREATE VIEW grafana_sprint_velocity AS
   SELECT 
     project,
     last_sprint,
     COUNT(*) as total_stories,
     SUM(story_points) as total_points,
     SUM(CASE WHEN status = 'Done' THEN story_points ELSE 0 END) as completed_points
   FROM jira_tasks_enhanced
   WHERE task_type IN ('Story', 'Epic')
   GROUP BY project, last_sprint
   ORDER BY last_sprint DESC;
   ```

2. **Completion Rate**
   ```sql
   CREATE VIEW grafana_completion_rate AS
   SELECT 
     project,
     last_sprint,
     COUNT(*) as total_issues,
     COUNT(CASE WHEN status = 'Done' THEN 1 END) as completed_issues,
     ROUND(100.0 * COUNT(CASE WHEN status = 'Done' THEN 1 END) / COUNT(*), 2) as completion_rate
   FROM jira_tasks_enhanced
   WHERE last_sprint IS NOT NULL
   GROUP BY project, last_sprint;
   ```

3. **Scope Change Tracking**
   ```sql
   CREATE VIEW grafana_scope_changes AS
   SELECT 
     project,
     last_sprint,
     COUNT(CASE WHEN sprint_repeats > 0 THEN 1 END) as carried_over,
     COUNT(CASE WHEN sprint_repeats = 0 THEN 1 END) as new_items,
     AVG(sprint_repeats) as avg_sprint_repeats
   FROM jira_tasks_enhanced
   WHERE last_sprint IS NOT NULL
   GROUP BY project, last_sprint;
   ```

#### PM Metrics Views:
1. **Developer Capacity**
   ```sql
   CREATE VIEW grafana_developer_capacity AS
   SELECT 
     assignee,
     project,
     last_sprint,
     COUNT(*) as assigned_tasks,
     SUM(story_points) as total_points,
     COUNT(CASE WHEN status = 'Done' THEN 1 END) as completed_tasks
   FROM jira_tasks_enhanced
   WHERE assignee IS NOT NULL AND last_sprint IS NOT NULL
   GROUP BY assignee, project, last_sprint;
   ```

2. **Cycle Time**
   ```sql
   CREATE VIEW grafana_cycle_time AS
   SELECT 
     key,
     assignee,
     project,
     task_type,
     EXTRACT(EPOCH FROM (resolved_at - created_at)) / 86400 as cycle_time_days,
     created_at,
     resolved_at
   FROM jira_tasks_enhanced
   WHERE resolved_at IS NOT NULL
   ORDER BY resolved_at DESC;
   ```

3. **Git Integration (requires git_commit table)**
   ```sql
   CREATE VIEW grafana_developer_commits AS
   SELECT 
     gc.author_email,
     jt.project,
     jt.last_sprint,
     COUNT(DISTINCT gc.commit_hash) as total_commits,
     COUNT(DISTINCT jt.key) as issues_worked,
     SUM(gc.additions) as lines_added,
     SUM(gc.deletions) as lines_removed
   FROM git_commit gc
   JOIN jira_tasks_enhanced jt ON gc.issue_key = jt.key
   GROUP BY gc.author_email, jt.project, jt.last_sprint;
   ```

### 4. Automated Git Sync
**Complexity:** Medium
**Current State:** Manual execution via `fetch_store_gitlab_commits.py`

**Tasks:**
- Create `SyncGitCommitsUseCase`
- Integrate with `ScheduledReportUseCase`
- Run alongside Jira sync (every 30 minutes)

### 5. Testing
**Complexity:** Medium

**Test Suites Needed:**
- Unit tests for `SyncJiraIssueUseCase`
- Integration tests for repository sync_status methods
- End-to-end webhook→PostgreSQL flow test
- Grafana view validation tests

---

## Architecture Summary

### Data Flow
```
Jira Webhook → ProcessJiraEventUseCase → SyncJiraIssueUseCase → PostgreSQL
                    ↓
              Google Sheets (existing)
              
Scheduled Job (30min) → GenerateJiraReportUseCase → PostgreSQL
                                                    ↓
                                                 Grafana ← SQL Views
```

### Database Tables
- `jira_tasks_enhanced` - Main issue data (existing)
- `git_commit` - Git commit data (existing)
- `sync_status` - Sync tracking (NEW ✅)

### Key Files Modified/Created
1. ✅ `use_cases/sync_jira_issue_use_case.py` (NEW)
2. ✅ `entities/sync_status.py` (NEW)
3. ✅ `migrations/migration_002_add_sync_status.py` (NEW)
4. ✅ `repositories/postgres/jira_report_repository.py` (MODIFIED)
5. ✅ `use_cases/interfaces/jira_report_repository_interface.py` (MODIFIED)
6. ✅ `scripts/run_migrations.py` (FIXED)
7. ✅ `migration_runner.py` (FIXED)

---

## Next Steps (Priority Order)

1. **HIGH**: Update DI configuration to wire `SyncJiraIssueUseCase`
2. **HIGH**: Integrate webhook with sync use case
3. **HIGH**: Create Grafana SQL views (user waiting for this)
4. **MEDIUM**: Implement incremental sync in JiraDataService
5. **MEDIUM**: Automate Git commit sync
6. **LOW**: Write comprehensive test suite

---

## Technical Debt
- Old migration `migration_001_add_due_date_and_project.py` has incorrect import path
- `report.py` deprecated but still in codebase (removal planned for v2.0.0)
- Incremental sync currently falls back to full sync

---

## User Clarifications
- User will build Grafana dashboards manually
- We provide: data pipeline (real-time updates + SQL views)
- User handles: Grafana visualization layer

---

**Last Updated:** December 3, 2024
**Status:** Phase 1 - 75% Complete
