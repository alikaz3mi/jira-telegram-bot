# PostgreSQL Jira Task Synchronization

## Overview

This document describes how the system synchronizes Jira tasks into PostgreSQL database for reporting, analytics, and metrics tracking.

## Architecture

The system follows Clean Architecture principles with clear separation between layers:

```
┌─────────────────────────────────────────────────────────────┐
│                        Frameworks                           │
│  - FastAPI Endpoints (Webhooks)                            │
│  - APScheduler (Scheduled Jobs)                            │
│  - CLI Scripts                                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                      Use Cases                              │
│  - GenerateJiraReportUseCase                               │
│  - ProcessJiraEventUseCase                                 │
│  - ScheduledReportUseCase                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                      Adapters                               │
│  Repositories:                                              │
│  - JiraReportRepository (PostgreSQL)                       │
│  - JiraServerRepository (Jira API)                         │
│  Services:                                                  │
│  - JiraDataService                                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                      Entities                               │
│  - JiraIssueDetail                                         │
│  - WorklogEntry                                            │
│  - LinkedIssue                                             │
│  - ProjectReport                                           │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

### Table: `jira_tasks_enhanced`

The enhanced table stores comprehensive Jira task information:

```sql
CREATE TABLE jira_tasks_enhanced (
    -- Primary Key
    key VARCHAR PRIMARY KEY,
    
    -- Basic Information
    summary TEXT,
    description TEXT,
    epic_name TEXT,
    comments TEXT,
    task_type VARCHAR,
    
    -- People
    assignee VARCHAR,
    reporter VARCHAR,
    
    -- Status & Priority
    priority VARCHAR,
    status VARCHAR,
    
    -- Dates
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    resolved_at TIMESTAMP,
    target_start TIMESTAMP,
    target_end TIMESTAMP,
    due_date TIMESTAMP,
    last_synced TIMESTAMP,
    
    -- Project & Organization
    project VARCHAR,
    components VARCHAR[],
    labels VARCHAR[],
    release VARCHAR[],
    
    -- Sprint Information
    last_sprint VARCHAR,
    sprint_repeats INTEGER,
    
    -- Estimation & Tracking
    story_points FLOAT,
    original_estimate TEXT,
    remaining_estimate TEXT,
    
    -- Complex Data (JSON)
    worklog_entries JSON,
    linked_issues JSON
);
```

### Table: `jira_tasks` (Legacy)

The legacy table with basic fields:

```sql
CREATE TABLE jira_tasks (
    key VARCHAR PRIMARY KEY,
    summary TEXT,
    description TEXT,
    epic_name TEXT,
    comments TEXT,
    task_type VARCHAR,
    assignee VARCHAR,
    reporter VARCHAR,
    priority VARCHAR,
    status VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    resolved_at TIMESTAMP,
    target_start TIMESTAMP,
    target_end TIMESTAMP,
    story_points FLOAT,
    components VARCHAR[],
    labels VARCHAR[],
    last_sprint VARCHAR,
    sprint_repeats INTEGER,
    release VARCHAR[],
    original_estimate TEXT,
    remaining_estimate TEXT
);
```

## Synchronization Methods

### 1. Scheduled Bulk Synchronization

**Purpose**: Periodic full synchronization of all Jira tasks to PostgreSQL

**Implementation**: `jira_telegram_bot/use_cases/generate_jira_report_use_case.py` (replaces deprecated `report.py`)

> ⚠️ **Note**: The legacy `report.py` file is deprecated and should not be used. It violates Clean Architecture principles. See `postgresql-sync-enhancement-plan.md` for details.

**Process**:
1. Fetch all issues from specified Jira projects using JQL
2. Extract comprehensive task information
3. Transform to database schema
4. Upsert to PostgreSQL (merge operation)

**Usage**:
```bash
# One-time sync using Clean Architecture implementation
python scripts/generate_reports_once.py

# Scheduled sync (runs every 30 minutes)
python scripts/run_scheduled_reports.py
```

**Code Flow** (Clean Architecture):
```python
# Modern implementation using dependency injection
class GenerateJiraReportUseCase:
    async def generate_project_report(self, project_key: str) -> ProjectReport:
        """Generate comprehensive report via clean interfaces."""
        issues = await self._jira_service.fetch_project_issues(project_key)
        await self._report_repository.store_issues(issues)
        return ProjectReport(
            project_key=project_key,
            generated_at=datetime.now(),
            total_issues=len(issues),
            issues=issues,
        )
```

**Legacy Code** (Deprecated):
```python
# ⚠️ DEPRECATED - DO NOT USE
# This code from report.py violates Clean Architecture
def get_tasks_info(project_key: str) -> list[dict]:
    """Deprecated: Use GenerateJiraReportUseCase instead."""
    # Direct Jira API calls - should be in adapter layer
    issues = jira_repository.jira.search_issues(...)
    return tasks_info

def store_tasks_in_db(tasks: list[dict]):
    """Deprecated: Use JiraReportRepository instead."""
    # Direct SQLAlchemy calls - should be in repository layer
    session.merge(task_obj)
    session.commit()
```

### 2. Enhanced Repository Pattern

**Purpose**: Clean Architecture implementation with proper separation of concerns

**Implementation**: `jira_telegram_bot/adapters/repositories/postgres/jira_report_repository.py`

**Key Features**:
- Proper entity/model separation
- Async support
- Worklog and linked issues handling
- JSON serialization for complex types

**Code Flow**:
```python
class JiraReportRepository(JiraReportRepositoryInterface):
    """PostgreSQL implementation of Jira report repository."""
    
    async def store_issues(self, issues: List[JiraIssueDetail]) -> None:
        """Store or update issues in the database."""
        session = self.db_connection.get_session()
        try:
            for issue in issues:
                # Convert entity to SQLAlchemy model
                task_model = self._convert_to_model(issue)
                # Merge = upsert (insert or update)
                session.merge(task_model)
            session.commit()
        finally:
            session.close()
    
    def _convert_to_model(self, issue: JiraIssueDetail) -> JiraTaskModel:
        """Convert entity to database model."""
        return JiraTaskModel(
            key=issue.key,
            summary=issue.summary,
            # ... all other fields
            worklog_entries=[entry.model_dump() for entry in issue.worklog_entries],
            linked_issues=[link.model_dump() for link in issue.linked_issues],
            last_synced=datetime.now(),
        )
```

### 3. Webhook-Based Real-Time Sync

**Purpose**: Real-time updates when Jira issues change

**Implementation**: `jira_telegram_bot/frameworks/fastapi/webhooks/metrics/metrics_webhook_endpoint.py`

**Process**:
1. Receive Jira webhook event
2. Parse webhook payload
3. Process event through use case
4. Update metrics and database

**Webhook Events Handled**:
- `jira:issue_created`
- `jira:issue_updated`
- `jira:worklog_updated`

**Code Flow**:
```python
@router.post("/jira")
async def process_jira_webhook(request: Request):
    """Process incoming Jira webhook events."""
    payload = await request.json()
    
    # Route to use case
    await process_jira_event_use_case.execute(
        webhook_event=payload["webhookEvent"],
        issue_data=payload["issue"],
    )
    
    return {"status": "processed"}
```

## Data Extraction Details

### Fields Extracted from Jira

#### Basic Fields
```python
task_info = {
    "key": issue.key,                              # PROJ-123
    "summary": issue.fields.summary,               # Task title
    "description": issue.fields.description,       # Task description
    "task_type": issue.fields.issuetype.name,     # Task, Bug, Story
    "status": issue.fields.status.name,           # To Do, In Progress, Done
    "priority": issue.fields.priority.name,       # High, Medium, Low
}
```

#### People
```python
task_info["assignee"] = issue.fields.assignee.displayName if issue.fields.assignee else None
task_info["reporter"] = issue.fields.reporter.displayName
```

#### Dates
```python
task_info["created_at"] = issue.fields.created
task_info["updated_at"] = issue.fields.updated
task_info["resolved_at"] = issue.fields.resolutiondate
task_info["target_start"] = issue.fields.customfield_10109
task_info["target_end"] = issue.fields.customfield_10110
```

#### Epic Information
```python
# First pass: collect all epics
for issue in issues:
    if issue.fields.issuetype.name == "Epic":
        epics[issue.key] = issue.fields.summary

# Second pass: link tasks to epics
task_info["epic_name"] = epics.get(issue.fields.customfield_10100)
```

#### Sprint Information
```python
sprint_field = issue.fields.customfield_10104  # Sprint custom field
if sprint_field and len(sprint_field) > 0:
    # Extract last sprint name from sprint string
    sprint_str = str(sprint_field[-1])
    name_start = sprint_str.find("name=") + 5
    name_end = sprint_str.find(",startDate")
    last_sprint_name = sprint_str[name_start:name_end]
else:
    last_sprint_name = "Backlog"

task_info["last_sprint"] = last_sprint_name
task_info["sprint_repeats"] = len(sprint_field) if sprint_field else 0
```

#### Story Points
```python
task_info["story_points"] = issue.fields.customfield_10106
```

#### Components and Labels
```python
task_info["components"] = [c.name for c in issue.fields.components] if issue.fields.components else []
task_info["labels"] = issue.fields.labels if issue.fields.labels else []
```

#### Release Information
```python
fix_versions = issue.fields.fixVersions
task_info["release"] = [fv.name for fv in fix_versions] if fix_versions else []
```

#### Time Tracking
```python
timetracking = issue.fields.timetracking
if timetracking:
    task_info["original_estimate"] = timetracking.originalEstimate  # e.g., "2h", "3d"
    task_info["remaining_estimate"] = timetracking.remainingEstimate
else:
    task_info["original_estimate"] = None
    task_info["remaining_estimate"] = None
```

#### Comments
```python
comments_text = []
if issue.fields.comment:
    for comment in issue.fields.comment.comments:
        commenter = comment.author.displayName
        if commenter != issue.fields.reporter.displayName:
            comments_text.append(f"{commenter}: {comment.body}")
task_info["comments"] = "\n".join(comments_text)
```

#### Worklog Entries (Enhanced Repository Only)
```python
worklog_entries = []
for worklog in issue.fields.worklog.worklogs:
    worklog_entries.append(WorklogEntry(
        author=worklog.author.displayName,
        time_spent_seconds=worklog.timeSpentSeconds,
        comment=worklog.comment,
        created=worklog.created,
        updated=worklog.updated,
        started=worklog.started,
    ))
```

#### Linked Issues (Enhanced Repository Only)
```python
linked_issues = []
for link in issue.fields.issuelinks:
    if hasattr(link, 'outwardIssue'):
        linked_issues.append(LinkedIssue(
            key=link.outwardIssue.key,
            relationship=link.type.outward,
            summary=link.outwardIssue.fields.summary,
        ))
    elif hasattr(link, 'inwardIssue'):
        linked_issues.append(LinkedIssue(
            key=link.inwardIssue.key,
            relationship=link.type.inward,
            summary=link.inwardIssue.fields.summary,
        ))
```

## Database Connection

### Connection Setup

```python
from jira_telegram_bot.adapters.repositories.postgres.database.postgres_connection import PostgresConnection
from jira_telegram_bot.settings.postgre_db_settings import PostgresSettings

# Initialize connection
settings = PostgresSettings()  # Loads from .env
db_connection = PostgresConnection(settings)

# Get SQLAlchemy engine
engine = db_connection.get_engine()

# Get session
session = db_connection.get_session()
```

### Environment Configuration

Set in `.env` file:
```bash
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=jira_tasks_db
```

### Connection URL Format

```python
DATABASE_URL = f"postgresql://{user}:{encoded_password}@{host}:{port}/{db_name}"
```

## Upsert Logic

### Using SQLAlchemy `session.merge()`

The system uses SQLAlchemy's `merge()` operation for upsert:

```python
# Create or update task
task_obj = Task(
    key=task_data["key"],  # Primary key
    summary=task_data["summary"],
    # ... other fields
)

# Merge performs:
# - INSERT if key doesn't exist
# - UPDATE if key exists
session.merge(task_obj)
session.commit()
```

**How it works**:
1. Checks if a record with the given primary key (`key`) exists
2. If exists: Updates all fields with new values
3. If not exists: Inserts new record
4. Maintains data integrity and prevents duplicates

## Scheduled Synchronization

### Setup

**Use Case**: `ScheduledReportUseCase`

```python
class ScheduledReportUseCase:
    """Orchestrates scheduled report generation."""
    
    async def setup_scheduled_reports(self, interval_minutes: int = 30):
        """Setup recurring job."""
        await self._scheduler_service.schedule_recurring_job(
            job_func=self._generate_reports,
            interval_minutes=interval_minutes,
            job_name="jira_report_generation",
        )
```

### Running Scheduler

```bash
# Method 1: Direct script
python scripts/run_scheduled_reports.py

# Method 2: Docker
docker-compose up jira-report-scheduler

# Method 3: Systemd service
sudo systemctl start jira-report-scheduler
```

### Docker Configuration

```yaml
# docker-compose.yml
services:
  jira-report-scheduler:
    build: .
    command: python scripts/run_scheduled_reports.py
    environment:
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=jira_tasks
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    depends_on:
      - postgres
    restart: unless-stopped
```

## Migration Handling

### Automatic Schema Updates

The legacy `report.py` includes automatic migrations:

```python
def ensure_schema_updates():
    """Add new columns if they don't exist."""
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE jira_tasks ADD COLUMN IF NOT EXISTS release text[];")
        )
        conn.execute(
            text("ALTER TABLE jira_tasks ADD COLUMN IF NOT EXISTS original_estimate text;")
        )
        conn.execute(
            text("ALTER TABLE jira_tasks ADD COLUMN IF NOT EXISTS remaining_estimate text;")
        )
```

### Manual Migrations

For the enhanced repository, migrations are in:
`jira_telegram_bot/adapters/repositories/postgres/database/migrations/`

Example migration:
```python
class Migration001AddDueDateAndProject(MigrationInterface):
    """Add due_date and project columns."""
    
    def get_migration_id(self) -> str:
        return "001_add_due_date_and_project"
    
    def up(self, connection) -> None:
        connection.execute(
            text("""
                ALTER TABLE jira_tasks_enhanced 
                ADD COLUMN IF NOT EXISTS due_date TIMESTAMP,
                ADD COLUMN IF NOT EXISTS project VARCHAR
            """)
        )
```

Run migrations:
```bash
python scripts/run_migrations.py
```

## Performance Considerations

### Batch Processing

Process issues in batches to avoid memory issues:

```python
def get_tasks_info(project_key: str) -> list[dict]:
    start_at = 0
    max_results = 100  # Batch size
    all_issues = []
    
    while True:
        batch = jira_repository.jira.search_issues(
            f"project = {project_key}",
            startAt=start_at,
            maxResults=max_results,
        )
        if not batch:
            break
        all_issues.extend(batch)
        if len(batch) < max_results:
            break
        start_at += max_results
    
    return all_issues
```

### Indexing

Key indexes for performance:

```sql
-- Primary key index (automatic)
CREATE INDEX idx_jira_tasks_key ON jira_tasks_enhanced(key);

-- Query optimization indexes
CREATE INDEX idx_jira_tasks_project ON jira_tasks_enhanced(project);
CREATE INDEX idx_jira_tasks_assignee ON jira_tasks_enhanced(assignee);
CREATE INDEX idx_jira_tasks_status ON jira_tasks_enhanced(status);
CREATE INDEX idx_jira_tasks_created ON jira_tasks_enhanced(created_at);
CREATE INDEX idx_jira_tasks_sprint ON jira_tasks_enhanced(last_sprint);
```

### Connection Pooling

SQLAlchemy automatically manages connection pooling:

```python
# Default pool size: 5 connections
# Max overflow: 10 additional connections
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before use
)
```

## Error Handling

### Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
)
def store_tasks_in_db(tasks: list[dict]):
    """Store with automatic retry."""
    try:
        for task in tasks:
            session.merge(Task(**task))
        session.commit()
    except Exception as e:
        session.rollback()
        LOGGER.error(f"Failed to store tasks: {e}")
        raise
    finally:
        session.close()
```

### Transaction Management

```python
session = Session()
try:
    # Multiple operations in one transaction
    for task in tasks:
        session.merge(Task(**task))
    session.commit()
except Exception as e:
    session.rollback()  # Rollback on error
    LOGGER.error(f"Transaction failed: {e}")
    raise
finally:
    session.close()  # Always close session
```

## Testing

### Unit Tests

Test the repository independently:

```python
class TestJiraReportRepository:
    def test_store_issues(self):
        """Test storing issues in database."""
        mock_db = Mock(spec=DatabaseConnectionInterface)
        repo = JiraReportRepository(mock_db)
        
        issues = [JiraIssueDetail(key="PROJ-1", ...)]
        await repo.store_issues(issues)
        
        mock_db.get_session().merge.assert_called()
```

### Integration Tests

Test full synchronization flow:

```bash
python -m pytest tests/e2e/test_migrations.py -v
```

## Monitoring

### Logging

All operations are logged:

```python
from jira_telegram_bot import LOGGER

LOGGER.info(f"Fetching issues for project: {project_key}")
LOGGER.info(f"Found {len(issues)} issues")
LOGGER.info(f"Upserted {len(tasks)} tasks into database")
LOGGER.error(f"Failed to store tasks: {error}")
```

### Metrics

Track synchronization metrics:

```python
# In use case
sync_start = datetime.now()
result = await self._repository.store_issues(issues)
sync_duration = (datetime.now() - sync_start).total_seconds()

LOGGER.info(f"Sync completed in {sync_duration}s, stored {len(issues)} issues")
```

## Summary

The system provides **three methods** for synchronizing Jira tasks to PostgreSQL:

1. **Scheduled Bulk Sync** (`report.py`): Periodic full synchronization
2. **Enhanced Repository** (`jira_report_repository.py`): Clean Architecture implementation
3. **Webhook Sync**: Real-time updates via webhooks

All methods use **upsert logic** (`session.merge()`) to ensure data consistency, with comprehensive field extraction including custom fields, sprints, comments, worklogs, and linked issues.

## Related Documentation

- [Metrics System Overview](../features/reporting-metrics/metrics_system_overview.md)
- [Jira Report System](../features/reporting-metrics/jira_report_system.md)
- [API Documentation](../features/reporting-metrics/api_documentation.md)
- [Configuration Guide](../features/reporting-metrics/configuration_guide.md)
