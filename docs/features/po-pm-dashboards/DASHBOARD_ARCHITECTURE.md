# PO/PM Dashboard Architecture

## Overview

This document describes the comprehensive architecture for Product Owner (PO) and Project Manager (PM) dashboards that combine Jira task progress with Git commit data.

## Current State Analysis

### Existing Data Sources

#### 1. Jira Task Data (PostgreSQL: `jira_tasks_enhanced`)
- **Updated via**: Scheduled sync every 30 minutes
- **Location**: `jira_telegram_bot/adapters/repositories/postgres/jira_report_repository.py`
- **Data includes**:
  - Task status, assignee, story points
  - Sprint information
  - Time estimates (original, remaining)
  - Dates (created, updated, resolved, target start/end)
  - Epic links, components, labels
  - Worklog entries (JSON)
  - Linked issues (JSON)

#### 2. Git Commit Data (PostgreSQL: `git_commit`)
- **Updated via**: Manual execution of `fetch_store_gitlab_commits.py`
- **Data includes**:
  - Commit ID, repository, committer
  - Commit time, message
  - Lines added/removed
  - Python lines changed
  - Conventional commit flag

#### 3. Metrics Data (Google Sheets via Webhook)
- **Updated via**: Real-time Jira webhooks
- **Data includes**:
  - Daily scoreboard (deadlines, tasks resolved, hours logged, commits)
  - Sprint metrics matrix (assigned tasks, completed tasks, time logged, MRs)

### Existing Dashboard Components

#### Currently Available (`reports_full.py`):
1. **Sprint Progress Dashboard**
   - Sprint completion rate
   - Task status breakdown  
   - High-priority blockers
   - Burn-down placeholder

2. **Team Productivity Dashboard**
   - Average task completion time
   - Developer workload
   - Bug vs. feature ratio

3. **Sprint-Level Dashboard (Per Sprint)**
   - Completion by sprint
   - Status breakdown by sprint
   - Burn-down by sprint

---

## 🎯 **Recommended Architecture for Issue Update Management**

### Architecture Principle: **Event-Driven + Scheduled Batch**

```
┌─────────────────────────────────────────────────────────────┐
│                   JIRA ISSUE UPDATES                        │
└──────────────┬──────────────────────────────────────────────┘
               │
               ├─────────────► [WEBHOOK] Real-time Events
               │                    │
               │                    ├─► ProcessJiraEventUseCase
               │                    │        │
               │                    │        ├─► Daily Metrics (Google Sheets)
               │                    │        └─► Event Log (PostgreSQL)
               │
               └─────────────► [SCHEDULED] Batch Sync (Every 30 min)
                                    │
                                    ├─► GenerateJiraReportUseCase
                                    │        │
                                    │        └─► JiraReportRepository
                                    │                 │
                                    │                 └─► jira_tasks_enhanced (PostgreSQL)
                                    │
                                    └─► Combined with Git Data
                                             │
                                             └─► PO/PM Dashboards
```

### Dual-Path Strategy

#### Path 1: Real-Time Metrics (Webhook-Driven)
**Purpose**: Immediate visibility for daily operations

**Flow**:
```python
Jira Webhook → MetricsWebhookEndpoint
              → ProcessJiraEventUseCase
              → MetricsProcessorService
              → UpdateSheetUseCase
              → Google Sheets (Daily Scoreboard)
```

**When to use**:
- ✅ Real-time status updates needed
- ✅ Daily team metrics (tasks resolved today, hours logged)
- ✅ Sprint-level daily tracking
- ✅ Immediate notifications to PO/PM

**Events tracked**:
- `issue_created`
- `issue_updated` 
- `issue_resolved`
- `issue_reopened`
- `worklog_updated`

#### Path 2: Analytical Dashboard (Scheduled Sync)
**Purpose**: Deep analytics, trends, historical data

**Flow**:
```python
APScheduler (30 min) → ScheduledReportUseCase
                      → GenerateJiraReportUseCase
                      → JiraDataService.fetch_project_issues()
                      → JiraReportRepository.store_issues()
                      → PostgreSQL (jira_tasks_enhanced)
                      
PostgreSQL + Analytics → Dashboard Generation
                      → Excel/Web Dashboard
                      → Email Reports to PO/PM
```

**When to use**:
- ✅ Historical trend analysis
- ✅ Sprint retrospectives
- ✅ Cross-project comparisons
- ✅ Capacity planning
- ✅ Performance metrics over time

---

## 🏗️ **Enhanced Architecture for Issue Updates**

### Phase 1: Improve Current Sync (IMMEDIATE)

#### Enhancement 1.1: Add Issue Update Events to Webhook
**Current**: Webhook only updates daily metrics, doesn't update PostgreSQL
**Needed**: Real-time PostgreSQL updates for critical changes

```python
# New use case: jira_telegram_bot/use_cases/sync_jira_issue_use_case.py

class SyncJiraIssueUseCase:
    """Real-time sync of critical Jira issue updates to PostgreSQL."""
    
    def __init__(
        self,
        jira_service: JiraDataServiceInterface,
        report_repository: JiraReportRepositoryInterface,
    ):
        self._jira_service = jira_service
        self._report_repository = report_repository
    
    async def sync_issue_update(
        self, 
        issue_key: str,
        event_type: str
    ) -> bool:
        """Sync single issue to PostgreSQL on critical events."""
        
        # Only sync for critical events
        if event_type not in [
            'issue_updated', 
            'issue_resolved',
            'issue_reopened',
            'worklog_updated'
        ]:
            return True  # Skip non-critical events
        
        # Fetch latest issue data
        issue_detail = await self._jira_service.fetch_issue_details(issue_key)
        
        # Update PostgreSQL immediately
        await self._report_repository.store_issues([issue_detail])
        
        LOGGER.info(f"Real-time synced {issue_key} on {event_type}")
        return True
```

**Integration**:
```python
# In ProcessJiraEventUseCase
async def process_jira_webhook(self, webhook_data: Dict[str, Any]) -> bool:
    # Existing: Update Google Sheets metrics
    await self.metrics_processor.process_metric_event(metric_event)
    
    # NEW: Also update PostgreSQL for dashboard
    issue_key = webhook_data.get("issue", {}).get("key")
    event_type = webhook_data.get("issue_event_type_name")
    
    if issue_key and event_type:
        await self.sync_issue_use_case.sync_issue_update(
            issue_key, 
            event_type
        )
```

#### Enhancement 1.2: Incremental Sync Instead of Full Sync
**Current**: Every 30 min, fetches ALL issues
**Needed**: Fetch only changed issues since last sync

```python
# In JiraDataService
async def fetch_updated_issues(
    self, 
    project_key: str,
    since: datetime
) -> List[JiraIssueDetail]:
    """Fetch only issues updated since timestamp."""
    
    jql = f"project = {project_key} AND updated >= '{since.strftime('%Y-%m-%d %H:%M')}'"
    
    issues = self._jira_repository.search_issues(
        jql,
        start_at=0,
        max_results=100,
        expand="changelog,worklog,issuelinks"
    )
    
    return [await self._convert_to_detailed_issue(i, epics) for i in issues]
```

#### Enhancement 1.3: Add Sync Status Tracking

```python
# New table: sync_status
class SyncStatus(Base):
    __tablename__ = "sync_status"
    
    project_key = Column(String, primary_key=True)
    last_full_sync = Column(DateTime)
    last_incremental_sync = Column(DateTime)
    last_sync_status = Column(String)  # success, partial, failed
    issues_synced = Column(Integer)
    errors = Column(JSON)
```

---

### Phase 2: Git Integration for Dev Metrics (RECOMMENDED)

#### Current Issue: Manual Git Sync
**File**: `jira_telegram_bot/adapters/fetch_store_gitlab_commits.py`
**Problem**: Must be run manually, no automation

#### Solution: Add to Scheduled Sync

```python
# In ScheduledReportUseCase
async def _generate_reports(self) -> None:
    """Generate reports with Git data."""
    
    # 1. Sync Jira issues
    for project_key in self._project_keys:
        await self._report_use_case.generate_project_report(project_key)
    
    # 2. Sync Git commits (NEW)
    await self._git_sync_use_case.fetch_and_store_commits()
    
    # 3. Generate combined dashboard (NEW)
    await self._dashboard_generator.generate_po_pm_dashboards(
        self._project_keys
    )
```

---

### Phase 3: Combined Dashboard Generation (NEW)

#### New Component: PO/PM Dashboard Generator

```python
# jira_telegram_bot/use_cases/dashboards/generate_po_pm_dashboard_use_case.py

class GeneratePOPMDashboardUseCase:
    """Generate comprehensive dashboards for PO and PM."""
    
    def __init__(
        self,
        report_repository: JiraReportRepositoryInterface,
        git_repository: GitCommitRepositoryInterface,
        dashboard_writer: DashboardWriterInterface,
    ):
        self._report_repo = report_repository
        self._git_repo = git_repository
        self._dashboard_writer = dashboard_writer
    
    async def generate_po_dashboard(
        self, 
        project_keys: List[str],
        sprint_id: Optional[str] = None
    ) -> PODashboard:
        """Generate Product Owner focused dashboard."""
        
        # Fetch data
        issues = await self._fetch_issues_for_projects(project_keys)
        commits = await self._git_repo.get_commits_by_projects(project_keys)
        
        # Calculate PO metrics
        metrics = {
            'feature_completion_rate': self._calc_feature_completion(issues),
            'sprint_velocity': self._calc_sprint_velocity(issues),
            'scope_changes': self._calc_scope_changes(issues),
            'release_progress': self._calc_release_progress(issues),
            'blockers': self._identify_blockers(issues),
            'technical_debt': self._calc_tech_debt(issues, commits),
            'quality_metrics': {
                'bugs_per_feature': self._calc_bugs_per_feature(issues),
                'rework_rate': self._calc_rework_rate(issues),
                'code_churn': self._calc_code_churn(commits)
            }
        }
        
        # Generate dashboard
        dashboard = PODashboard(
            project_keys=project_keys,
            generated_at=datetime.now(),
            metrics=metrics,
            charts=self._generate_po_charts(metrics),
            insights=self._generate_po_insights(metrics)
        )
        
        # Write to output (Excel, PDF, Google Sheets, etc.)
        await self._dashboard_writer.write_dashboard(dashboard)
        
        return dashboard
    
    async def generate_pm_dashboard(
        self, 
        project_keys: List[str]
    ) -> PMDashboard:
        """Generate Project Manager focused dashboard."""
        
        # Fetch data
        issues = await self._fetch_issues_for_projects(project_keys)
        commits = await self._git_repo.get_commits_by_projects(project_keys)
        worklogs = self._extract_worklogs(issues)
        
        # Calculate PM metrics
        metrics = {
            'team_velocity': self._calc_team_velocity(issues),
            'capacity_utilization': self._calc_capacity_utilization(worklogs),
            'cycle_time': self._calc_cycle_time(issues),
            'lead_time': self._calc_lead_time(issues),
            'wip_limits': self._check_wip_limits(issues),
            'developer_metrics': {
                dev: {
                    'tasks_completed': self._count_tasks(issues, dev),
                    'story_points': self._sum_story_points(issues, dev),
                    'hours_logged': self._sum_hours(worklogs, dev),
                    'commits': self._count_commits(commits, dev),
                    'code_quality': self._calc_code_quality(commits, dev)
                }
                for dev in self._get_developers(issues)
            },
            'risk_assessment': self._assess_risks(issues)
        }
        
        # Generate dashboard
        dashboard = PMDashboard(
            project_keys=project_keys,
            generated_at=datetime.now(),
            metrics=metrics,
            charts=self._generate_pm_charts(metrics),
            recommendations=self._generate_pm_recommendations(metrics)
        )
        
        # Write to output
        await self._dashboard_writer.write_dashboard(dashboard)
        
        return dashboard
```

---

## 📊 **Dashboard Metrics Breakdown**

### For Product Owner (PO)

#### Strategic Metrics
1. **Feature Completion Rate**
   - % of committed features delivered
   - Trend over sprints
   - By epic/release

2. **Sprint Velocity**
   - Story points completed per sprint
   - Velocity trend
   - Predictability score

3. **Scope Changes**
   - Stories added mid-sprint
   - Stories removed
   - Impact on velocity

4. **Release Progress**
   - % complete by fix version
   - Stories done vs. remaining
   - Release risk assessment

5. **Quality Metrics**
   - Bugs per feature
   - Rework rate (reopened issues)
   - Code churn (git commits)

#### Tactical Metrics
1. **Blockers & Dependencies**
   - High-priority blocked issues
   - Cross-team dependencies
   - Resolution time

2. **Technical Debt**
   - Tech debt stories
   - Refactoring work
   - Code quality trends

### For Project Manager (PM)

#### Team Performance
1. **Team Velocity**
   - Story points/sprint
   - Commitment vs. completion
   - Trend analysis

2. **Capacity Utilization**
   - Planned vs. actual hours
   - By developer
   - Overtime tracking

3. **Cycle Time & Lead Time**
   - Time from start to done
   - Time from created to done
   - Bottleneck identification

4. **WIP Limits**
   - Tasks in progress
   - Per status/developer
   - Queue health

#### Developer Metrics
1. **Individual Performance**
   - Tasks completed
   - Story points delivered
   - Hours logged
   - Commits made
   - Lines of code

2. **Code Quality**
   - Conventional commits %
   - Code review feedback
   - Bug introduction rate

3. **Productivity Trends**
   - Week-over-week comparison
   - Sprint-over-sprint comparison

#### Risk Management
1. **Schedule Risks**
   - Tasks behind schedule
   - Critical path issues
   - Velocity drops

2. **Quality Risks**
   - Bug trend increasing
   - Rework increasing
   - Code churn high

3. **Resource Risks**
   - Overallocated developers
   - Key person dependencies
   - Skill gaps

---

## 🔄 **Complete Data Flow**

### Real-Time Path (Webhook)
```
Jira Issue Update
    ↓
[Webhook Triggered]
    ↓
MetricsWebhookEndpoint
    ↓
ProcessJiraEventUseCase
    ├─► MetricsProcessorService → Google Sheets (Daily)
    └─► SyncJiraIssueUseCase → PostgreSQL (Critical Updates)
```

### Batch Path (Scheduled)
```
[APScheduler - Every 30 min]
    ↓
ScheduledReportUseCase
    ├─► GenerateJiraReportUseCase
    │       ↓
    │   JiraDataService.fetch_updated_issues()
    │       ↓
    │   JiraReportRepository.store_issues()
    │       ↓
    │   PostgreSQL (jira_tasks_enhanced)
    │
    ├─► GitSyncUseCase
    │       ↓
    │   fetch_store_gitlab_commits()
    │       ↓
    │   PostgreSQL (git_commit)
    │
    └─► GeneratePOPMDashboardUseCase
            ↓
        Combine Jira + Git data
            ↓
        Calculate metrics
            ↓
        Generate charts
            ↓
        DashboardWriter
            ├─► Excel files
            ├─► Google Sheets
            ├─► PDF reports
            └─► Email to PO/PM
```

---

## 🛠️ **Implementation Plan**

### Week 1: Enhance Issue Update Handling
- [ ] Implement `SyncJiraIssueUseCase` for real-time PostgreSQL updates
- [ ] Add incremental sync to `JiraDataService`
- [ ] Create `sync_status` table
- [ ] Update `ProcessJiraEventUseCase` to call sync use case
- [ ] Test webhook → PostgreSQL flow

### Week 2: Automate Git Integration
- [ ] Create `GitSyncUseCase` with proper DI
- [ ] Add to `ScheduledReportUseCase`
- [ ] Create `GitCommitRepositoryInterface`
- [ ] Implement `GitCommitRepository` (Clean Architecture)
- [ ] Test scheduled git sync

### Week 3: Build Dashboard Generator
- [ ] Create entities: `PODashboard`, `PMDashboard`
- [ ] Implement `GeneratePOPMDashboardUseCase`
- [ ] Build metric calculation functions
- [ ] Create `DashboardWriterInterface`
- [ ] Implement writers (Excel, Google Sheets, PDF)

### Week 4: Testing & Deployment
- [ ] Integration tests
- [ ] Performance testing with production data
- [ ] Documentation
- [ ] Deploy to production
- [ ] Train PO/PM on dashboard usage

---

## 📈 **Expected Benefits**

### For Product Owners
- **Better Planning**: Historical velocity, predictable sprints
- **Risk Visibility**: Early warning on scope creep, quality issues
- **Data-Driven Decisions**: Feature prioritization based on metrics
- **Stakeholder Communication**: Clear progress visualization

### For Project Managers
- **Resource Optimization**: Identify overallocation, bottlenecks
- **Quality Monitoring**: Track code quality, technical debt
- **Team Health**: Developer productivity trends, burnout detection
- **Schedule Management**: Accurate completion predictions

### For Development Team
- **Transparency**: Clear visibility into metrics
- **Recognition**: Data shows individual contributions
- **Improvement**: Metrics help identify areas to improve
- **Accountability**: Clear expectations and tracking

---

## 🔧 **Technical Considerations**

### Performance
- Use incremental sync (only changed issues)
- Index PostgreSQL tables properly
- Cache frequently accessed data
- Batch process dashboard generation

### Scalability
- Handle multiple projects (current: MYPROJECT, PROJ1)
- Support adding new metrics without code changes
- Allow custom dashboard configurations
- Support multiple output formats

### Reliability
- Idempotent webhook processing
- Retry logic for failed syncs
- Fallback to batch sync if webhook fails
- Health checks and monitoring

### Security
- Sensitive data handling (developer emails, hours)
- Access control for dashboard viewing
- Secure webhook endpoints
- Audit logging

---

## 📚 **Related Documentation**

- [PostgreSQL Jira Sync](../../infrastructure/postgresql-jira-sync.md)
- [Metrics System Overview](../reporting-metrics/metrics_system_overview.md)
- [Webhook Architecture](../webhooks/webhook_architecture.md)
- [Enhancement Plan](../../infrastructure/postgresql-sync-enhancement-plan.md)
