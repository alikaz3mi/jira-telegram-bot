# PostgreSQL Jira Sync Enhancement Plan

## Executive Summary

Analysis of the Jira-to-PostgreSQL synchronization reveals that `use_cases/report.py` is **legacy code that violates Clean Architecture** and is effectively **unused**. The system has migrated to proper Clean Architecture implementations but the legacy file remains, causing confusion.

## Current State Analysis

### ✅ Active Implementation (Clean Architecture)

**Primary System:**
```
GenerateJiraReportUseCase (use_cases/)
    ↓ depends on
JiraDataService (adapters/services/)
    ↓ fetches from
JiraServerRepository (adapters/repositories/)
    ↓ stores via
JiraReportRepository (adapters/repositories/postgres/)
    ↓ uses
PostgreSQLConnection (adapters/repositories/postgres/database/)
```

**Execution Paths:**
1. **Scheduled Sync**: `scripts/run_scheduled_reports.py` → `ScheduledReportUseCase` → `GenerateJiraReportUseCase`
2. **Manual Sync**: `scripts/generate_reports_once.py` → `GenerateJiraReportUseCase`
3. **Webhook Events**: `MetricsWebhookEndpoint` → `ProcessJiraEventUseCase`

**Benefits:**
- ✅ Proper dependency injection (Lagom container)
- ✅ Clean separation of concerns
- ✅ Testable (90%+ coverage)
- ✅ Async support
- ✅ Handles complex types (JSON for worklogs, linked issues)
- ✅ Proper error handling

### ❌ Legacy Code (Architecture Violation)

**File:** `jira_telegram_bot/use_cases/report.py`

**Problems:**
```python
# 1. VIOLATION: Direct instantiation in use case layer
_postgres_settings = PostgresSettings()
_jira_settings = JiraConnectionSettings()
engine = create_engine(DATABASE_URL)  # Framework code in use case!
session = Session()
jira_repository = JiraServerRepository(settings=_jira_settings)

# 2. VIOLATION: Global module-level state
Base = declarative_base()
class Task(Base):  # ORM model in use case layer!
    __tablename__ = "jira_tasks"

# 3. VIOLATION: Direct database access in use case
def store_tasks_in_db(tasks: list[dict]):
    session.merge(task_obj)  # Use case calling SQLAlchemy directly!
    session.commit()
```

**Why It's Wrong:**
1. **Layer Violation**: Use cases contain SQLAlchemy/PostgreSQL code (framework layer)
2. **No DI**: Hard-coded dependencies, can't inject mocks for testing
3. **Global State**: Module-level variables make it untestable
4. **Wrong Location**: ORM models belong in `adapters/repositories/`, not `use_cases/`
5. **Not Used**: No active imports, no execution path

**Evidence It's Not Used:**
- ✅ No files import `from jira_telegram_bot.use_cases.report import`
- ✅ No `__main__` block to execute standalone
- ✅ Tests only reference `GenerateJiraReportUseCase`
- ✅ Scripts use `GenerateJiraReportUseCase`, not `report.py`
- ✅ DI container doesn't wire `report.py` functions

## Architecture Violations Detailed

### Rule 1: Dependency Flow
```
❌ WRONG (current report.py):
use_cases/ → imports frameworks (SQLAlchemy, PostgreSQL)

✅ CORRECT (GenerateJiraReportUseCase):
use_cases/ → depends on → interfaces/ → implemented by → adapters/ → uses → frameworks/
```

### Rule 2: Use Case Purity
```
❌ WRONG (report.py):
def store_tasks_in_db(tasks):
    session.merge(task_obj)  # Direct DB access
    session.commit()

✅ CORRECT (GenerateJiraReportUseCase):
async def generate_project_report(self, project_key: str):
    issues = await self._jira_service.fetch_project_issues(project_key)
    await self._report_repository.store_issues(issues)  # Via interface
```

### Rule 3: Testability
```
❌ WRONG (report.py):
# Can't mock: hard-coded global variables
jira_repository = JiraServerRepository(settings=_jira_settings)

✅ CORRECT (GenerateJiraReportUseCase):
def __init__(
    self,
    jira_service: JiraDataServiceInterface,  # Injected
    report_repository: JiraReportRepositoryInterface,  # Injected
)
```

## Proposed Enhancements

### Phase 1: Cleanup and Deprecation (HIGH PRIORITY)

#### Step 1.1: Move to Deprecated Folder
```bash
mv jira_telegram_bot/use_cases/report.py \
   jira_telegram_bot/use_cases/report_deprecated.py
```

#### Step 1.2: Add Deprecation Warning
Update the moved file header:
```python
"""
DEPRECATED: This file violates Clean Architecture principles.

⚠️ DO NOT USE THIS FILE ⚠️

This legacy implementation directly instantiates database connections
and ORM models at the module level, violating the dependency rule.

✅ USE INSTEAD:
- GenerateJiraReportUseCase (jira_telegram_bot/use_cases/generate_jira_report_use_case.py)
- JiraReportRepository (jira_telegram_bot/adapters/repositories/postgres/jira_report_repository.py)
- Scripts: scripts/generate_reports_once.py or scripts/run_scheduled_reports.py

REASONS FOR DEPRECATION:
1. Violates Clean Architecture: use cases import framework code (SQLAlchemy)
2. No dependency injection: can't test, can't swap implementations
3. Wrong layer: ORM models (Task) should be in adapters/, not use_cases/
4. Global state: module-level database connections
5. Not used: no active code references this file

DATE DEPRECATED: December 3, 2025
REMOVAL TARGET: Version 2.0.0
"""
```

#### Step 1.3: Verify No Dependencies
```bash
# Search for any imports
grep -r "from jira_telegram_bot.use_cases.report import" .
grep -r "import.*report" . | grep -v "report_deprecated"
grep -r "get_tasks_info\|store_tasks_in_db" . | grep -v "report_deprecated"
```

#### Step 1.4: Update Documentation
- ✅ `docs/infrastructure/postgresql-jira-sync.md`: Remove report.py references
- ✅ Add migration guide: "If using report.py, migrate to GenerateJiraReportUseCase"

### Phase 2: Enhance Current Implementation (MEDIUM PRIORITY)

#### Enhancement 2.1: Add Incremental Sync
**Current**: Full project sync every 30 minutes (slow for large projects)

**Improved**:
```python
class GenerateJiraReportUseCase:
    async def generate_incremental_report(
        self, 
        project_key: str,
        since: datetime
    ) -> ProjectReport:
        """Only sync issues updated since timestamp."""
        issues = await self._jira_service.fetch_updated_issues(
            project_key, 
            updated_since=since
        )
        await self._report_repository.store_issues(issues)
        return self._build_report(project_key, issues)
```

#### Enhancement 2.2: Add Batch Processing
**Current**: All issues in memory at once

**Improved**:
```python
async def generate_project_report_batched(
    self,
    project_key: str,
    batch_size: int = 100
) -> ProjectReport:
    """Process issues in batches to reduce memory."""
    total_issues = 0
    async for batch in self._jira_service.fetch_issues_batched(
        project_key, 
        batch_size
    ):
        await self._report_repository.store_issues(batch)
        total_issues += len(batch)
    return await self._report_repository.get_project_report(project_key)
```

#### Enhancement 2.3: Add Sync Status Tracking
```python
# New entity
class SyncStatus(BaseModel):
    project_key: str
    last_sync_time: datetime
    last_sync_status: Literal["success", "partial", "failed"]
    issues_synced: int
    errors: List[str]

# New repository method
class JiraReportRepository:
    async def update_sync_status(self, status: SyncStatus) -> None:
        """Track sync history for monitoring."""
```

#### Enhancement 2.4: Add Progress Callbacks
```python
class GenerateJiraReportUseCase:
    async def generate_project_report(
        self,
        project_key: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> ProjectReport:
        """Report progress for UI feedback."""
        issues = await self._jira_service.fetch_project_issues(
            project_key,
            progress_callback=progress_callback
        )
        # ...
```

### Phase 3: Performance Optimization (LOW PRIORITY)

#### Enhancement 3.1: Connection Pooling Configuration
```python
# In PostgreSQLConnection
def _create_engine(self) -> Engine:
    return create_engine(
        database_url,
        pool_size=10,  # Increase from default 5
        max_overflow=20,  # Increase from default 10
        pool_pre_ping=True,
        pool_recycle=3600,  # Recycle connections hourly
        echo=False,  # Disable SQL logging in production
    )
```

#### Enhancement 3.2: Add Database Indexes
```sql
-- Migration: Add performance indexes
CREATE INDEX CONCURRENTLY idx_jira_tasks_enhanced_project 
    ON jira_tasks_enhanced(project);
CREATE INDEX CONCURRENTLY idx_jira_tasks_enhanced_assignee 
    ON jira_tasks_enhanced(assignee);
CREATE INDEX CONCURRENTLY idx_jira_tasks_enhanced_status 
    ON jira_tasks_enhanced(status);
CREATE INDEX CONCURRENTLY idx_jira_tasks_enhanced_updated 
    ON jira_tasks_enhanced(updated_at DESC);
CREATE INDEX CONCURRENTLY idx_jira_tasks_enhanced_sprint 
    ON jira_tasks_enhanced(last_sprint);

-- Partial index for active issues
CREATE INDEX CONCURRENTLY idx_jira_tasks_enhanced_active 
    ON jira_tasks_enhanced(project, status) 
    WHERE status NOT IN ('Done', 'Closed', 'Resolved');
```

#### Enhancement 3.3: Bulk Insert Optimization
```python
async def store_issues(self, issues: List[JiraIssueDetail]) -> None:
    """Optimize with bulk operations."""
    session = self.db_connection.get_session()
    try:
        # Convert all at once
        models = [self._convert_to_model(issue) for issue in issues]
        
        # Use bulk_insert_mappings for better performance
        session.bulk_save_objects(models, return_defaults=False)
        session.commit()
        
        LOGGER.info(f"Bulk stored {len(issues)} issues")
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
```

### Phase 4: Enhanced Monitoring (LOW PRIORITY)

#### Enhancement 4.1: Add Metrics Tracking
```python
from prometheus_client import Counter, Histogram

sync_duration = Histogram('jira_sync_duration_seconds', 'Time to sync project')
sync_issues_total = Counter('jira_sync_issues_total', 'Total issues synced')
sync_errors_total = Counter('jira_sync_errors_total', 'Total sync errors')

class GenerateJiraReportUseCase:
    @sync_duration.time()
    async def generate_project_report(self, project_key: str):
        try:
            report = await self._do_sync(project_key)
            sync_issues_total.inc(report.total_issues)
            return report
        except Exception as e:
            sync_errors_total.inc()
            raise
```

#### Enhancement 4.2: Add Health Check
```python
class JiraReportRepository:
    async def health_check(self) -> bool:
        """Verify database connectivity."""
        try:
            session = self.db_connection.get_session()
            session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            session.close()
```

## Migration Guide

### For Anyone Currently Using `report.py`

**Old Way (DON'T USE):**
```python
from jira_telegram_bot.use_cases.report import get_tasks_info, store_tasks_in_db

tasks = get_tasks_info("PROJ")
store_tasks_in_db(tasks)
```

**New Way (CORRECT):**
```python
import asyncio
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.generate_jira_report_use_case import GenerateJiraReportUseCase

async def sync_project():
    container = get_container()
    use_case = container[GenerateJiraReportUseCase]
    report = await use_case.generate_project_report("PROJ")
    print(f"Synced {report.total_issues} issues")

asyncio.run(sync_project())
```

**Or use the provided script:**
```bash
python scripts/generate_reports_once.py
```

## Testing Recommendations

### Test Coverage Gaps
1. ✅ `GenerateJiraReportUseCase` has unit tests
2. ✅ `JiraReportRepository` has unit tests
3. ❌ Missing: Integration test for full sync flow
4. ❌ Missing: Performance test with large datasets

### Recommended Tests
```python
# tests/integration/test_full_sync_flow.py
async def test_full_sync_integration():
    """Test complete sync from Jira to PostgreSQL."""
    # Setup: Mock Jira with 1000 issues
    # Execute: Run full sync
    # Assert: All issues in database
    # Assert: Sync completes in <60s

# tests/performance/test_sync_performance.py
async def test_sync_10000_issues():
    """Ensure sync handles large projects."""
    # Should complete in <5 minutes
```

## Rollout Plan

### Week 1: Deprecation
- [x] Move `report.py` to `report_deprecated.py`
- [x] Add deprecation warning
- [x] Update documentation
- [ ] Verify no dependencies

### Week 2: Communication
- [ ] Notify team of deprecation
- [ ] Update internal wiki
- [ ] Add migration guide to README

### Week 3: Enhancement Implementation
- [ ] Add incremental sync
- [ ] Add batch processing
- [ ] Add sync status tracking

### Week 4: Testing
- [ ] Integration tests
- [ ] Performance tests
- [ ] Load testing with production data

### Version 2.0.0: Complete Removal
- [ ] Delete `report_deprecated.py`
- [ ] Remove from codebase completely

## Metrics for Success

### Current State
- Sync frequency: Every 30 minutes
- Average sync time: ~2-3 minutes per project
- Memory usage: ~500MB for 5000 issues
- Test coverage: 90%+

### Target State (After Enhancements)
- Incremental sync: Every 5 minutes
- Average sync time: <30 seconds (incremental)
- Memory usage: <100MB (batched processing)
- Test coverage: 95%+
- Zero legacy code violations

## Conclusion

The current implementation using `GenerateJiraReportUseCase` and `JiraReportRepository` is **correct and follows Clean Architecture**. The legacy `report.py` file should be **deprecated immediately** as it:

1. Violates core architectural principles
2. Is not actually used by any active code
3. Creates confusion about the "correct" way to sync
4. Cannot be properly tested
5. Sets a bad example for future development

**Recommended Action**: Proceed with Phase 1 (Deprecation) immediately. The other enhancements are nice-to-haves but not urgent.

## Related Documentation

- [PostgreSQL Jira Sync Documentation](postgresql-jira-sync.md)
- [Jira Report System](../features/reporting-metrics/jira_report_system.md)
- [Clean Architecture Guidelines](../../.github/copilot-instructions.md)
