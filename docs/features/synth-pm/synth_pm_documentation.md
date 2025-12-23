# SynthPM Feature Documentation

## Overview

SynthPM is a comprehensive feature that provides bidirectional synchronization between Google Sheets, Jira boards (PM Board and Developer), and Telegram notifications. This feature enables seamless project management across multiple platforms with automatic task creation, status synchronization, and team notifications.

**NEW: Release-Based Task Organization** - Tasks are now automatically grouped by their Release column ("ریلیز") and organized under release stories with features as subtasks, providing better structure and visibility for release management.

## Architecture

The SynthPM feature follows Clean Architecture principles with proper dependency injection:

### Core Components

1. **Repository Layer** (`SynthPMRepository`)
   - Handles Google Sheets ↔ Jira ↔ Telegram synchronization
   - Implements header-based column mapping for flexibility
   - Manages release-based story creation with subtasks

2. **Use Case Layer** (`SynthPMUseCase`)
   - Contains business logic for feature synchronization
   - Groups features by release column
   - Creates hierarchical structure (Release Story → Feature Subtasks)
   - Manages Telegram notifications with enhanced formatting

3. **Entities Layer** (`constants.py`)
   - Centralized status/priority mappings
   - Telegram icons and status descriptions
   - Persian ↔ English translations

4. **Settings** (`SynthPMSettings`)
   - Configuration for Google Sheets, Jira, and Telegram
   - Injected via dependency injection container

## Key Features

### ✅ **Release-Based Task Organization** (NEW)
- **Automatic Grouping**: Tasks are grouped by their "ریلیز" (Release) column value
- **Release Stories**: A Story is created for each release with descriptive summary
- **Feature Subtasks**: Individual tasks become subtasks under their release story
- **Hierarchy Benefits**:
  - Better release visibility and tracking
  - Cleaner backlog organization
  - Easy sprint planning by release
  - Natural dependency management within releases

### ✅ **Dual Board Creation**
- Tasks are automatically created in both **PM Board** and **Developer** boards
- Developer tasks are linked to PM Board tasks via Jira issue linking
- Both issue keys are stored in Google Sheet for tracking
- Release stories maintain epic and sprint associations

### ✅ **Smart Status Mapping**
- **Persian Google Sheet Status** ↔ **Jira Status** mapping:
  - `۵` (آماده پیاده سازی فنی) → `To Do`
  - `۶` (در حال پیاده سازی) → `In Progress`
  - `۴` (در مرحله طراحی) → `In Progress` (UI/UX special handling)
  - `۷` (در مرحله تست فنی) → `Review`
  - `۸` (آماده تحویل) → `Done`

### ✅ **Enhanced Telegram Notifications**
- **Epic Hashtags**: Uses epic names as hashtags for better organization
- **Status Icons**: Visual indicators for different statuses and priorities
- **Smart Triggers**: Only posts notifications for relevant status changes
- **Rich Formatting**: Includes task details, links, and visual elements

### ✅ **Flexible Column Mapping**
- **Header-based parsing**: Uses actual column names instead of fixed positions
- **Multi-language support**: Handles both Persian and English column headers
- **Robust against changes**: Adding/removing columns won't break the system

### ✅ **Bidirectional Synchronization**
- **Google Sheets → Jira**: Creates/updates Jira tasks from sheet data
- **Jira → Google Sheets**: Updates sheet when Jira tasks change
- **Status Tracking**: Maintains sync status for each row

## Release-Based Workflow

### How It Works

1. **Feature Extraction**: System reads all features from the developer board sheet
2. **Release Grouping**: Features are grouped by their "ریلیز" (Release) column value
3. **Story Creation**: For each release group:
   - Check if a release story already exists
   - If not, create a new Story with release name as title
   - Story includes summary of all features in the release
   - Story inherits sprint, epic, and component settings from features
4. **Subtask Creation**: For each feature in the release:
   - Create as subtask under the release story
   - Assign to appropriate team members
   - Link to PM Board task
   - Include all feature details (dates, components, story points)
5. **Sheet Update**: Update Google Sheet with created issue keys

### Example Structure

```
📦 Release: Version 2.5.0 (Story)
├── 🔨 Implement user authentication (Sub-task) → Assignee: john.doe
├── 🔨 Add dashboard analytics (Sub-task) → Assignee: jane.smith  
├── 🔨 Optimize database queries (Sub-task) → Assignees: multiple → creates further subtasks
│   ├── Backend optimization (Sub-task) → Assignee: backend.dev
│   └── Query indexing (Sub-task) → Assignee: db.admin
└── 🔨 Update API documentation (Sub-task) → Assignee: tech.writer
```

### Benefits

1. **Better Organization**: Clear release-level visibility in backlogs
2. **Sprint Planning**: Easy to pull entire releases into sprints
3. **Progress Tracking**: See completion status at release level
4. **Dependency Management**: Related features naturally grouped together
5. **Reporting**: Generate release reports from story level
6. **Team Coordination**: All team members see full release context

## Implementation Details

### Release Grouping Logic

```python
def _group_features_by_release(
    features: List[SynthPMFeatureEntity]
) -> Dict[str, List[SynthPMFeatureEntity]]:
    """Group features by their release column value."""
    release_groups = {}
    for feature in features:
        release_name = feature.release if feature.release else "No Release"
        if release_name not in release_groups:
            release_groups[release_name] = []
        release_groups[release_name].append(feature)
    return release_groups
```

### Release Story Creation

```python
async def create_release_story(
    release_name: str,
    features: List[SynthPMFeatureEntity]
) -> Optional[str]:
    """Create a story for a release based on features."""
    # Calculate total effort
    total_hours = sum(f.total_hours for f in features)
    
    # Get all team members
    all_assignees = extract_all_assignees(features)
    
    # Build feature list for description
    feature_list = "\\n".join([f"• {f.task_title}" for f in features])
    
    # Create story
    story_data = TaskData(
        project_key=developer_board_project_key,
        summary=f"📦 Release: {release_name}",
        description=f"Release grouping for {release_name}\\n\\n{feature_list}",
        task_type="Story",
        labels=[f"release:{release_name}"],
        # ... sprint, epic, components from first feature
    )
    
    return create_task(story_data)
```

### Subtask Creation

```python
async def create_subtask_for_release(
    parent_story_key: str,
    feature: SynthPMFeatureEntity,
    assignees: List[str]
) -> Optional[str]:
    """Create a subtask for a feature under a release story."""
    subtask_data = TaskData(
        project_key=developer_board_project_key,
        summary=feature.task_title,
        description=feature.description,
        task_type="Sub-task",
        parent_key=parent_story_key,
        assignee=assignees[0] if len(assignees) == 1 else None,
        # ... dates, components, story points
    )
    
    subtask = create_task(subtask_data)
    
    # For multiple assignees, create individual subtasks
    if len(assignees) > 1:
        create_subtasks_for_assignees(subtask.key, assignees, feature)
    
    return subtask.key
```

### Status Mapping Constants

```python
# Persian to Jira Status Mapping
Developer_TO_JIRA_STATUS = {
    "۵": "To Do",                    # آماده پیاده سازی فنی
    "۶": "In Progress",              # در حال پیاده سازی
    "۴": "In Progress",              # در مرحله طراحی (UI/UX)
    "۷": "Review",                   # در مرحله تست فنی
    "۸": "Done",                     # آماده تحویل
}

# Priority Mapping
PRIORITY_MAPPING = {
    "Highest": "Highest",
    "High": "High",
    "Medium": "Medium",
    "Low": "Low",
    # Persian mappings
    "بالاترین": "Highest",
    "بالا": "High",
    "متوسط": "Medium",
    "پایین": "Low",
}
```

### Column Header Mapping

The system dynamically maps Google Sheet columns using headers:

```python
COLUMN_MAPPING = {
    # Persian Headers
    "عنوان تسک": "task_title",
    "اپیک": "epic",
    "ریلیز": "release",
    "ضرورت": "necessity",
    "اولویت": "priority",
    "وضعیت": "status",
    "تخمین ساعت": "eta_hours",
    "کل ساعت": "total_hours",
    "اسپرینت": "sprint",
    "ددلاین": "deadline",
    "تاریخ شروع پیاده سازی": "implementation_start_date",

    # English Headers
    "Task Title": "task_title",
    "Epic": "epic",
    "Release": "release",
    "Priority": "priority",
    "Status": "status",
    "ETA Hours": "eta_hours",
    "Total Hours": "total_hours",
    "Sprint": "sprint",
    "Deadline": "deadline",
    "Implementation Start Date": "implementation_start_date",
}
```

### Telegram Message Format

Enhanced Telegram notifications include:

```python
def _format_telegram_message(self, feature: DeveloperFeatureEntity, action: str) -> str:
    """Format enhanced Telegram message with icons and hashtags."""

    # Epic hashtag
    epic_hashtag = f"#{feature.epic.replace(' ', '_')}" if feature.epic else "#General"

    # Status and priority icons
    status_icon = STATUS_ICONS.get(feature.status, "📝")
    priority_icon = PRIORITY_ICONS.get(feature.priority, "⚪")

    # Enhanced message format
    message = f"""
{status_icon} **Task Update** {action}

📝 **{feature.task_title}**
{epic_hashtag}

🏷️ **Status**: {STATUS_DESCRIPTIONS.get(feature.status, feature.status)}
{priority_icon} **Priority**: {feature.priority}
📅 **Deadline**: {feature.deadline.strftime('%Y-%m-%d') if feature.deadline else 'Not set'}

🔗 **Jira Links**:
• PM Board: [{feature.jira_issue_key}]({jira_link})
• Developer: [{feature.developer_issue_key}]({developer_link})
"""
    return message
```

## Configuration

### Environment Variables

```bash
# Google Sheets Configuration
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
GOOGLE_SHEETS_SHEET_NAME=your_sheet_name
GOOGLE_APPLICATION_CREDENTIALS=path_to_service_account.json

# Jira Configuration
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your_username
JIRA_API_TOKEN=your_api_token

# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# SynthPM Specific
SYNTH_PM_ENABLED=true
SYNTH_PM_SYNC_INTERVAL=300  # seconds
```

### Dependency Injection Setup

```python
def _configure_synth_pm(container: Container) -> None:
    """Configure SynthPM components."""
    # Settings
    container[SynthPMSettings] = Singleton(
        lambda: SynthPMSettings()
    )

    # Repository
    container[SynthPMRepositoryInterface] = Singleton(
        lambda c: SynthPMRepository(
            google_sheet_client=c[GoogleSheetClient],
            jira_repository=c[TaskManagerRepositoryInterface],
            settings=c[SynthPMSettings]
        )
    )

    # Use case
    container[SynthPMUseCase] = Singleton(
        lambda c: SynthPMUseCase(
            repository=c[SynthPMRepositoryInterface],
            settings=c[SynthPMSettings]
        )
    )
```

### Google Sheets Setup

1. Create a Google Sheets document with the required columns
2. Name the worksheet as configured in settings (default: "developer Features")
3. Ensure the service account has edit permissions on the sheet
4. Set up the header row with Persian/English column names as specified

### Jira Setup

1. Ensure both **PM Board** and **Developer** projects exist in Jira
2. Configure appropriate statuses, priorities, and workflows for both boards
3. Set up webhooks to point to your API endpoint for bidirectional sync
4. Configure issue linking between PM Board and Developer boards

### Telegram Setup

1. Create a Telegram channel for posting updates
2. Optionally create a connected group
3. Ensure the bot has posting permissions in both

## Usage Examples

### Basic Synchronization

```python
from jira_telegram_bot.app_container import get_container

# Get configured use case
container = get_container()
synth_pm_usecase = container[SynthPMUseCase]

# Sync Google Sheets with Jira
sync_status = await synth_pm_usecase.sync_sheet_with_jira()
print(f"Synced {sync_status.processed_count} features")
```

### Manual Task Creation

```python
# Create task in both PM Board and Developer boards
feature_data = developerFeatureEntity(
    task_title="New Feature Implementation",
    epic="Epic Name",
    priority="High",
    status="۶",  # در حال پیاده سازی
    eta_hours=40,
    departments="Backend,Frontend"
)

result = await synth_pm_usecase.create_jira_task_from_feature(feature_data)
print(f"Created PM Board: {result.pm_board_key}, Developer: {result.developer_key}")
```

## API Endpoints

### Sync Endpoint
```http
POST /api/synth-developer/sync
Content-Type: application/json

{
    "force_sync": false,
    "notify_telegram": true
}
```

### Status Update Endpoint
```http
POST /api/synth-developer/status
Content-Type: application/json

{
    "row_number": 5,
    "new_status": "۷",
    "updated_by": "user@example.com"
}
```

## Monitoring and Logging

### Sync Status Tracking

The system maintains sync status for each row:

```python
class developerSheetSyncStatus:
    total_rows: int
    processed_count: int
    error_count: int
    created_tasks: List[str]
    updated_tasks: List[str]
    errors: List[str]
    last_sync_time: datetime
```

### Logging

All operations are logged with structured logging:

```python
LOGGER.info(f"Starting SynthPM sync for {sheet_name}")
LOGGER.debug(f"Processing row {row_number}: {feature.task_title}")
LOGGER.error(f"Failed to create Jira task: {error}")
```

## Error Handling

### Common Issues and Solutions

1. **Google Sheets Access Issues**
   - Verify service account permissions
   - Check spreadsheet sharing settings
   - Validate credentials file path

2. **Jira API Errors**
   - Verify API token permissions
   - Check project permissions for both PM Board and Developer
   - Validate issue type and field configurations

3. **Status Mapping Errors**
   - Ensure status values match constants
   - Check for typos in Persian status text
   - Verify Jira workflow transitions

4. **Telegram Notification Failures**
   - Verify bot token validity
   - Check chat ID permissions
   - Validate message formatting

## Performance Considerations

### Optimization Strategies

1. **Batch Processing**: Process multiple rows in single API calls
2. **Caching**: Cache Jira project metadata and user information
3. **Rate Limiting**: Respect API rate limits for Google Sheets and Jira
4. **Incremental Sync**: Only sync changed rows when possible

### Monitoring Metrics

- Sync duration and frequency
- API call counts and error rates
- Message delivery success rates
- Memory and CPU usage during sync

## Security

### Data Protection

1. **Credentials Management**: Use environment variables and secure storage
2. **API Permissions**: Principle of least privilege for all integrations
3. **Data Encryption**: Encrypt sensitive data in transit and at rest
4. **Audit Logging**: Track all data access and modifications

### Access Control

- Service account restrictions
- Jira project-level permissions
- Telegram bot scope limitations
- Google Sheets sharing controls

## Future Enhancements

### Planned Features

1. **Advanced Filtering**: Custom filters for selective synchronization
2. **Multi-Sheet Support**: Handle multiple Google Sheets
3. **Conflict Resolution**: Automated handling of sync conflicts
4. **Analytics Dashboard**: Visual sync status and metrics
5. **Webhook Integration**: Real-time sync triggers from Jira/Google Sheets

### Integration Opportunities

- Integration with other project management tools
- Support for additional notification channels (Slack, Discord)
- API for external systems integration
- Mobile app notifications

## Troubleshooting

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger('jira_telegram_bot.adapters.repositories.synth_pm_repository').setLevel(logging.DEBUG)
```

### Common Debug Commands

```bash
# Test Google Sheets connection
python -m jira_telegram_bot.scripts.test_google_sheets

# Test Jira connectivity
python -m jira_telegram_bot.scripts.test_jira_connection

# Validate status mappings
python -m jira_telegram_bot.scripts.validate_status_mappings

# Test Telegram bot
python -m jira_telegram_bot.scripts.test_telegram_bot
```

## Support

For additional support:

1. Check the logs for detailed error messages
2. Verify all configuration settings
3. Test individual components in isolation
4. Review the troubleshooting guide
5. Contact the development team with specific error details

---

*Last updated: August 1, 2025*
*Version: 2.0.0*
  }
}
```

#### POST /synth-developer/jira-webhook
Handle Jira webhook events for developer features.

**Request Body:**
```json
{
  "issue": {
    "key": "PM Board-123",
    "fields": {
      "status": {"name": "In Progress"},
      "summary": "Updated task title"
    }
  },
  "issue_event_type_name": "issue_updated"
}
```

#### POST /synth-developer/sheet-update
Handle manual Google Sheets updates.

**Request Body:**
```json
{
  "row_number": 5,
  "updates": {
    "status": "۲",
    "task_title": "Updated task"
  }
}
```

### Webhook Endpoints

#### POST /webhook/telegram
Handle Telegram webhook events (already implemented).

## Usage

### Running as a Script

Use the provided script for various operations:

```bash
# One-time synchronization
python scripts/run_synth_pm.py sync

# Run as background service
python scripts/run_synth_pm.py service

# Test connections
python scripts/run_synth_pm.py test
```

### Integration with FastAPI

The SynthPM endpoints are automatically registered when the API server starts. They are available at:

- `http://your-domain/synth-developer/sync`
- `http://your-domain/synth-developer/jira-webhook`
- `http://your-domain/synth-developer/sheet-update`

### Background Synchronization

The system can run continuous background synchronization:

1. Configure the sync interval in environment variables
2. Start the background service using the script or integrate with your main application
3. Monitor logs for sync status and errors

## Workflow

### Status Change Flow

1. **Sheet Update**: User changes status to "۲" in Google Sheets
2. **Jira Creation**: If no Jira issue exists, one is created in the PM Board project
3. **Telegram Post**: A formatted message is posted to the configured Telegram channel
4. **Bidirectional Sync**: Further changes in either system sync to the other

### Field Mapping

#### Priority Mapping
- بحرانی → Highest
- بالا → High
- متوسط → Medium
- پایین → Low
- خیلی پایین → Lowest

#### Status Mapping
- ۱ → To Do
- ۲ → In Progress
- ۳ → Done
- بررسی → In Review
- تست → Testing
- آماده انتشار → Ready for Release

## Monitoring and Troubleshooting

### Logs

The system provides comprehensive logging for:
- Sync operations and results
- API requests and responses
- Error conditions and recovery
- Background task status

### Sync Status

The system maintains sync status information including:
- Last sync time
- Total rows processed
- Error messages
- Success/failure counts

### Common Issues

1. **Authentication Errors**
   - Verify Google Sheets token path and permissions
   - Check Jira credentials and project access
   - Ensure Telegram bot tokens are valid

2. **Data Parsing Errors**
   - Verify sheet column structure matches expected format
   - Check for invalid date formats
   - Ensure numeric fields contain valid numbers

3. **Sync Failures**
   - Monitor network connectivity
   - Check API rate limits
   - Verify webhook endpoint accessibility

## Development

### Adding New Fields

1. Update `developerFeatureEntity` in `entities/developer_feature.py`
2. Modify `_parse_row_to_feature` in the repository
3. Update `_get_field_column_mapping` for column positions
4. Add field handling in sync logic

### Custom Status Triggers

Modify the `status_trigger_value` setting to change which status triggers Telegram posts.

### Extended Integrations

The architecture supports adding new integrations by:
1. Creating new repository interfaces
2. Implementing adapters for external services
3. Extending the use case with new business logic

## Security Considerations

- Store sensitive tokens and credentials securely
- Use HTTPS for all webhook endpoints
- Implement proper authentication for API endpoints
- Monitor access logs for suspicious activity
- Regular rotation of API tokens and credentials
