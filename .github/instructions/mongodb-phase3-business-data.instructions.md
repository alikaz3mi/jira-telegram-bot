---

mode: agent
description: Phase 3 - Business Data Migration - Move business-critical operational data to MongoDB
tools: [terminalLastCommand, codeBase, usages, testFailure, findTestFiles]
-----------------------------------------

# 🚀 Phase 3: Business Data Migration

Migrate business-critical operational data from local JSON files to MongoDB. This includes progress reports, notification tracking, and operational metadata, while leveraging the API Calendar service and excluding deprecated calendar JSON files.

## 🎯 Goals

1. **Progress Reports Migration**: Move progress report data from JSON files to MongoDB
2. **Notification Tracking**: Migrate notification logs to MongoDB (excluding system logs)
3. **Project Information**: Centralize project metadata and configuration
4. **API Calendar Integration**: Integrate with API Calendar service for holiday/workday data
5. **Business Analytics Foundation**: Enable advanced reporting and analytics capabilities
6. **Data Archiving**: Implement data lifecycle management

## 📊 Data to Migrate

### From JSON Files to MongoDB Collections:

1. **`progress_reports`** - Team member progress reports and status updates
2. **`notification_tracking`** - Business notification history (not system logs)
3. **`project_metadata`** - Project configuration and information
4. **`workflow_states`** - Issue workflow and state tracking
5. **`integration_logs`** - Third-party integration activity logs

### Data NOT to Migrate:
- ❌ **Calendar JSON files** (deprecated, replaced by API Calendar)
- ❌ **System logs** (handled by Loki/Elasticsearch)
- ❌ **Metrics data** (doesn't exist yet)

## 🏗️ Architecture Components

### 1. Business Data Entities
**Location**: `jira_telegram_bot/entities/business/`

* `progress_report.py` - Enhanced progress report entity
* `notification_record.py` - Business notification tracking entity
* `project_metadata.py` - Project information and configuration entity
* `workflow_state.py` - Issue workflow tracking entity
* `integration_activity.py` - Third-party integration logs entity

### 2. Business Repository Interfaces
**Location**: `jira_telegram_bot/use_cases/interfaces/business/`

* `progress_report_repository_interface.py`
* `notification_tracking_repository_interface.py`
* `project_metadata_repository_interface.py`
* `workflow_state_repository_interface.py`
* `integration_activity_repository_interface.py`

### 3. MongoDB Business Repositories
**Location**: `jira_telegram_bot/adapters/repositories/mongodb/business/`

* `mongodb_progress_report_repository.py`
* `mongodb_notification_tracking_repository.py`
* `mongodb_project_metadata_repository.py`
* `mongodb_workflow_state_repository.py`
* `mongodb_integration_activity_repository.py`

### 4. API Calendar Integration
**Location**: `jira_telegram_bot/adapters/external_apis/`

* `api_calendar_service.py` - Integration with API Calendar service
* `calendar_data_cache.py` - Caching layer for calendar data
* `calendar_types.py` - Calendar-related type definitions

### 5. Business Data Services
**Location**: `jira_telegram_bot/use_cases/business/`

* `progress_reporting_service.py` - Enhanced progress report management
* `notification_management_service.py` - Business notification orchestration
* `project_management_service.py` - Project metadata management
* `business_analytics_service.py` - Analytics and reporting foundation

## 📝 Implementation Details

### Enhanced Progress Report Structure
```python
ProgressReport:
    report_id: str  # unique identifier
    assignee: str
    project_key: str
    sprint_id: Optional[str]
    reported_at: datetime
    report_period: DateRange
    completed_tasks: List[TaskSummary]
    in_progress_tasks: List[TaskSummary]
    blocked_tasks: List[TaskSummary]
    hours_logged: float
    productivity_metrics: ProductivityMetrics
    challenges: List[str]
    achievements: List[str]
    next_period_goals: List[str]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    version: int
```

### Notification Tracking Structure
```python
NotificationRecord:
    notification_id: str
    notification_type: str  # deadline, progress, status_change, etc.
    target_entity: EntityReference  # issue, sprint, project
    recipient: UserReference
    channel: str  # telegram, email, slack
    sent_at: datetime
    delivery_status: str  # sent, delivered, failed, bounced
    content_hash: str  # for deduplication
    metadata: Dict[str, Any]
    related_notifications: List[str]  # for threading
    created_at: datetime
    expires_at: Optional[datetime]
```

### Project Metadata Structure
```python
ProjectMetadata:
    project_key: str  # primary key
    project_name: str
    project_type: str
    status: str  # active, archived, deprecated
    team_members: List[TeamMemberRole]
    jira_connection_id: str  # reference to Phase 1
    configuration: ProjectConfiguration
    metrics_config: MetricsConfiguration
    workflow_config: WorkflowConfiguration
    integration_settings: IntegrationSettings
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime]
    version: int
```

### API Calendar Integration
```python
class APICalendarService:
    async def get_holidays(self, year: int, country: str = "IR") -> List[Holiday]:
        # Fetch holidays from API Calendar service

    async def get_business_days(self, start_date: date, end_date: date) -> List[date]:
        # Calculate business days using API

    async def is_holiday(self, date: date) -> bool:
        # Check if specific date is holiday

    async def get_working_hours(self, date: date) -> WorkingHours:
        # Get working hours for specific date
```

## 🔄 Migration Workflow

### 1. Progress Reports Migration
1. **Data Analysis**: Analyze existing progress report JSON structure
2. **Schema Enhancement**: Design enhanced schema with analytics capabilities
3. **Batch Migration**: Migrate reports in chronological batches
4. **Data Enrichment**: Add project and user references
5. **Validation**: Verify data integrity and completeness

### 2. Notification Tracking Migration
1. **Log Analysis**: Extract business notifications from existing logs
2. **Deduplication**: Remove duplicate notifications
3. **Classification**: Categorize notifications by type and importance
4. **Relationship Mapping**: Establish notification threading and relationships
5. **Historical Import**: Import with proper timestamps and metadata

### 3. Project Metadata Centralization
1. **Configuration Extraction**: Extract project configs from various sources
2. **Schema Unification**: Create unified project metadata schema
3. **Team Assignment**: Map team members to projects
4. **Integration Settings**: Centralize integration configurations
5. **Validation Rules**: Implement project configuration validation

### 4. API Calendar Integration
1. **Service Integration**: Integrate with API Calendar service
2. **Caching Layer**: Implement intelligent caching for calendar data
3. **Fallback Strategy**: Handle API unavailability gracefully
4. **Data Synchronization**: Keep calendar data synchronized
5. **Performance Optimization**: Optimize for frequent calendar queries

### 5. Business Analytics Foundation
1. **Data Modeling**: Design analytics-friendly data structures
2. **Aggregation Pipelines**: Create MongoDB aggregation queries
3. **Performance Indexes**: Add indexes for common analytics queries
4. **Real-time Updates**: Enable real-time analytics updates
5. **Dashboard Integration**: Prepare for Grafana dashboard integration

## 📋 Interactive Variables

* `${input:migration_start_date}` - Start date for historical data migration
* `${input:progress_report_retention_months}` - Progress report retention (default: 24)
* `${input:notification_retention_days}` - Notification tracking retention (default: 90)
* `${input:enable_analytics}` - Enable analytics aggregations (default: true)
* `${input:api_calendar_url}` - API Calendar service URL
* `${input:api_calendar_token}` - API Calendar authentication token
* `${input:cache_calendar_hours}` - Calendar data cache TTL (default: 24)
* `${input:enable_archiving}` - Enable automatic data archiving (default: true)

## 🔧 Technical Implementation

### Enhanced Progress Report Repository
```python
class MongoDBProgressReportRepository(ProgressReportRepositoryInterface):
    async def save_reports(self, reports: List[ProgressReport]) -> List[ProgressReport]:
        # Batch save with validation and deduplication

    async def get_reports_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        assignee: Optional[str] = None,
        project_key: Optional[str] = None
    ) -> List[ProgressReport]:
        # Optimized range queries with filtering

    async def get_productivity_trends(
        self,
        assignee: str,
        months: int = 6
    ) -> ProductivityTrends:
        # Analytics aggregation for productivity tracking

    async def archive_old_reports(self, before_date: datetime) -> int:
        # Archive old reports with metadata preservation
```

### Notification Tracking Service
```python
class NotificationTrackingService:
    async def record_notification(
        self,
        notification: NotificationRecord
    ) -> str:
        # Record notification with deduplication

    async def get_delivery_statistics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> DeliveryStatistics:
        # Analytics for notification delivery

    async def cleanup_expired_notifications(self) -> int:
        # Clean up expired notifications

    async def get_notification_thread(
        self,
        entity_reference: EntityReference
    ) -> List[NotificationRecord]:
        # Get related notifications for an entity
```

### API Calendar Integration
```python
class CachedAPICalendarService:
    def __init__(self, api_service: APICalendarService, cache: CacheInterface):
        self.api_service = api_service
        self.cache = cache

    async def get_holidays_cached(self, year: int) -> List[Holiday]:
        cache_key = f"holidays:{year}"
        holidays = await self.cache.get(cache_key)
        if holidays is None:
            holidays = await self.api_service.get_holidays(year)
            await self.cache.set(cache_key, holidays, ttl=86400 * 7)  # 1 week
        return holidays

    async def calculate_business_days_in_range(
        self,
        start_date: date,
        end_date: date
    ) -> int:
        # Efficient business day calculation with caching
```

## 🧪 Testing Strategy

### Unit Tests
- Progress report CRUD operations and analytics
- Notification tracking and threading
- Project metadata validation
- API Calendar service integration
- Data archiving and cleanup

### Integration Tests
- End-to-end progress reporting workflow
- Notification delivery and tracking
- Project configuration management
- Calendar API reliability and fallback
- Cross-collection data consistency

### Performance Tests
- Progress report query performance
- Notification tracking at scale
- Calendar API response times
- Analytics aggregation performance
- Bulk migration performance

### Business Tests
- Progress report accuracy and completeness
- Notification delivery reliability
- Project metadata integrity
- Calendar data accuracy
- Analytics data correctness

## 📁 File Structure
```
jira_telegram_bot/
├── entities/business/
│   ├── __init__.py
│   ├── progress_report.py
│   ├── notification_record.py
│   ├── project_metadata.py
│   ├── workflow_state.py
│   └── integration_activity.py
├── use_cases/interfaces/business/
│   ├── __init__.py
│   ├── progress_report_repository_interface.py
│   ├── notification_tracking_repository_interface.py
│   ├── project_metadata_repository_interface.py
│   ├── workflow_state_repository_interface.py
│   └── integration_activity_repository_interface.py
├── adapters/repositories/mongodb/business/
│   ├── __init__.py
│   ├── mongodb_progress_report_repository.py
│   ├── mongodb_notification_tracking_repository.py
│   ├── mongodb_project_metadata_repository.py
│   ├── mongodb_workflow_state_repository.py
│   └── mongodb_integration_activity_repository.py
├── adapters/external_apis/
│   ├── __init__.py
│   ├── api_calendar_service.py
│   ├── calendar_data_cache.py
│   └── calendar_types.py
├── use_cases/business/
│   ├── __init__.py
│   ├── progress_reporting_service.py
│   ├── notification_management_service.py
│   ├── project_management_service.py
│   └── business_analytics_service.py
└── frameworks/cli/
    ├── business_migration_cli.py
    └── analytics_cli.py
```

## 📊 Analytics & Reporting Foundation

### Grafana Dashboard Preparation
1. **HR Viewer Dashboard**:
   - Team productivity metrics
   - Progress report summaries
   - Work hours tracking
   - Team performance trends

2. **Accountant Viewer Dashboard**:
   - Project cost tracking
   - Time allocation reports
   - Resource utilization metrics
   - Budget vs. actual reporting

3. **CEO Viewer Dashboard**:
   - High-level KPIs
   - Project delivery metrics
   - Team efficiency trends
   - Strategic milestone tracking

### MongoDB Aggregation Pipelines
```python
# Example aggregation for team productivity
team_productivity_pipeline = [
    {"$match": {"reported_at": {"$gte": start_date, "$lte": end_date}}},
    {"$group": {
        "_id": "$assignee",
        "total_hours": {"$sum": "$hours_logged"},
        "completed_tasks": {"$sum": {"$size": "$completed_tasks"}},
        "avg_productivity": {"$avg": "$productivity_metrics.efficiency_score"}
    }},
    {"$sort": {"total_hours": -1}}
]
```

## 📈 Success Criteria

1. **Migration Completeness**: 100% of business data migrated successfully
2. **Data Integrity**: Zero data loss during migration process
3. **Query Performance**: Business queries ≤100ms response time (95th percentile)
4. **Analytics Ready**: Dashboard-ready aggregations performing ≤1s
5. **API Integration**: 99.5% uptime for calendar API integration
6. **Storage Efficiency**: ≥30% reduction in storage footprint vs. JSON files
7. **Archiving Success**: Automated archiving reducing active data by ≥50%

## 🚀 Deliverables

1. **Enhanced Business Entities**: Comprehensive business data models
2. **Migration Pipeline**: Automated business data migration tools
3. **Repository Suite**: High-performance business data repositories
4. **API Calendar Integration**: Robust calendar service integration
5. **Analytics Foundation**: MongoDB aggregations for dashboard feeding
6. **Archiving System**: Automated data lifecycle management
7. **Dashboard Schemas**: Grafana-ready data schemas and queries

## 🔄 Dependencies on Previous Phases

This phase builds on Phases 1 & 2:
- **MongoDB Infrastructure**: Uses connection and base patterns from Phase 1
- **User References**: Links to user profiles from Phase 2
- **Configuration Management**: Leverages settings infrastructure from Phase 1
- **Session Context**: Uses session management from Phase 2

## 📚 Additional Dependencies

Add to `requirements.txt`:
```
pandas~=2.1.0  # For data analysis during migration
httpx~=0.25.0  # For API Calendar service integration
tenacity~=8.2.0  # For API retry logic
```

## ⚠️ Risk Mitigation

### Business Continuity Risks
- **Progress Report Loss**: Multiple backup strategies and validation
- **Notification Gaps**: Dual tracking during migration period
- **Calendar Dependency**: Robust fallback for API unavailability
- **Analytics Disruption**: Gradual migration with continuous validation

### Technical Risks
- **Large Data Migration**: Streaming and checkpoint-based migration
- **API Rate Limits**: Intelligent caching and request throttling
- **Query Performance**: Comprehensive indexing and optimization
- **Data Consistency**: ACID transactions for critical operations

### Operational Risks
- **Dashboard Downtime**: Parallel analytics pipelines during migration
- **Reporting Gaps**: Maintain both old and new reporting during transition
- **User Impact**: Zero-downtime migration with fallback capabilities
- **Rollback Complexity**: Point-in-time recovery and rollback procedures

---

**Remember**: This phase establishes the business data foundation that will enable advanced analytics, automated reporting, and strategic insights for HR, accounting, and executive dashboards.
