# Release-Based Task Organization Workflow

## Overview

The SynthPM developer board sync now implements a **release-based task organization** workflow. Instead of creating individual tasks directly, the system groups tasks by their **"ریلیز" (Release)** column and creates a hierarchical structure with release stories as parents and feature tasks as subtasks.

## Motivation

### Previous Approach
- Individual tasks created directly in the developer board
- No automatic grouping or organization
- Difficult to track which tasks belong to which release
- Harder to manage dependencies within a release
- Release planning required manual organization

### New Approach
- Tasks automatically grouped by release column
- Release stories provide high-level organization
- Feature subtasks maintain detailed information
- Natural hierarchy for sprint planning
- Better visibility and progress tracking

## Workflow Details

### 1. Feature Extraction

The system reads all features from the developer board Google Sheet:

```python
features = await repository.get_developer_board_features()
```

Each feature entity contains:
- Task title, description, and acceptance criteria
- Release column value ("ریلیز")
- Sprint assignments
- Team member assignments
- Epic association
- Dates and priorities

### 2. Release Grouping

Features are grouped by their release column value:

```python
release_groups = self._group_features_by_release(features)
# Result: {"Version 2.5.0": [feature1, feature2, ...], "Version 2.6.0": [...]}
```

**Grouping Rules:**
- Features with the same release value are grouped together
- Empty or missing release values go to "No Release" group
- Case-sensitive matching on release names

### 3. Release Story Creation

For each release group, a Story is created or retrieved:

**Story Attributes:**
- **Summary**: `📦 Release: {release_name}`
- **Description**: List of all features in the release + total effort
- **Type**: Story
- **Sprint**: Inherited from features (uses first active/future sprint)
- **Epic**: Inherited from features (if all share same epic)
- **Labels**: `release:{release_name}`
- **Components**: Union of all feature components
- **Fix Version**: Release name as Jira version

**Example Story:**
```
Summary: 📦 Release: Version 2.5.0
Description:
  This story groups all tasks for the Version 2.5.0 release.
  
  Included Features:
  • Implement user authentication
  • Add dashboard analytics
  • Optimize database queries
  • Update API documentation
  
  Total Effort: 120h
  Team Members: john.doe, jane.smith, backend.dev
```

**Idempotency:**
- System checks if story already exists using JQL search
- Existing stories are reused, not duplicated
- Search: `project = "DEV" AND issuetype = Story AND summary ~ "Version 2.5.0"`

### 4. Feature Subtask Creation

For each feature in the release group, a subtask is created:

**Subtask Attributes:**
- **Summary**: Feature task title
- **Description**: Feature description with PM Board link
- **Type**: Sub-task
- **Parent**: Release story key
- **Assignee**: 
  - Single assignee: Assigned directly
  - Multiple assignees: Creates nested subtasks for each
- **Story Points**: Time estimate / 8 (for single assignee)
- **Components**: Feature-specific components
- **Dates**: Implementation start, deadline, target dates
- **Links**: Related to PM Board task

**Single Assignee Example:**
```
Summary: Implement user authentication
Type: Sub-task
Parent: DEV-1234 (Release: Version 2.5.0)
Assignee: john.doe
Story Points: 5
Components: Backend, Security
```

**Multiple Assignees Example:**
```
Summary: Optimize database queries
Type: Sub-task  
Parent: DEV-1234 (Release: Version 2.5.0)
Assignee: (none - managed via nested subtasks)
Components: Backend, Database

  Sub-tasks of this sub-task:
  ├── Backend optimization (john.doe, 3 SP)
  └── Query indexing (jane.smith, 2 SP)
```

### 5. Sheet Update

After creation, the Google Sheet is updated:

```python
await repository.update_developer_board_feature(
    sheet_row_number,
    {"developer_board_issue_key": subtask_key}
)
```

**Updated Columns:**
- `developer_board_issue_key`: The subtask key (e.g., DEV-1235)
- Issue is linked to parent story transparently in Jira

## Jira Structure

### Resulting Hierarchy

```
📦 DEV-1234: Release: Version 2.5.0 (Story)
│   Sprint: DEV Sprint 45
│   Epic: User Experience Improvements
│   Status: In Progress
│
├── 🔨 DEV-1235: Implement user authentication (Sub-task)
│   ├── Assignee: john.doe
│   ├── Story Points: 5
│   └── Status: To Do
│
├── 🔨 DEV-1236: Add dashboard analytics (Sub-task)
│   ├── Assignee: jane.smith
│   ├── Story Points: 4
│   └── Status: In Progress
│
├── 🔨 DEV-1237: Optimize database queries (Sub-task)
│   ├── Assignees: Multiple (via nested subtasks)
│   │   ├── DEV-1238: Backend optimization (john.doe, 3 SP)
│   │   └── DEV-1239: Query indexing (jane.smith, 2 SP)
│   └── Status: To Do
│
└── 🔨 DEV-1240: Update API documentation (Sub-task)
    ├── Assignee: tech.writer
    ├── Story Points: 1.5
    └── Status: To Do
```

## Benefits

### For Project Managers
1. **Release Visibility**: Clear view of all work in each release
2. **Progress Tracking**: Story completion shows release progress
3. **Sprint Planning**: Easy to include/exclude entire releases
4. **Reporting**: Generate release burndown charts
5. **Scope Management**: Add/remove features at release level

### For Developers
1. **Context**: See all related work in one place
2. **Dependencies**: Understand feature relationships within release
3. **Backlog Organization**: Cleaner, more organized backlogs
4. **Sprint Focus**: Know which release you're working on
5. **Team Coordination**: See what other team members are doing in the release

### For Stakeholders
1. **Transparency**: Clear release scope and progress
2. **Communication**: Easy to discuss specific releases
3. **Planning**: Better understanding of release timelines
4. **Risk Management**: Identify blocked releases quickly

## Configuration

### Required Google Sheet Columns

The release-based workflow requires these columns:

| Column Name (Persian) | Column Name (English) | Required | Description |
|-----------------------|----------------------|----------|-------------|
| عنوان تسک | Task Title | ✅ | Feature name |
| ریلیز | Release | ✅ | Release identifier |
| اسپرینت | Sprint | ✅ | Sprint assignment(s) |
| افراد درگیر | Involved People | ✅ | Team member names |
| وضعیت | Status | ✅ | Current status |
| اپیک | Epic | ⚪ | Epic name (optional) |
| اولویت | Priority | ⚪ | Priority level |
| ددلاین | Deadline | ⚪ | Due date |

### Settings

No additional configuration needed. The feature works with existing SynthPM settings:

```python
# In synth_pm_settings.json or environment
{
  "project_key": "MYPROJECT",
  "spreadsheet_id": "your-sheet-id",
  "boards": {
    "developer_board": {
      "jira_board_key": "DEV",
      "sheet_name": "Developer Board",
      "enabled": true
    }
  }
}
```

## Usage

### Running Sync

The release-based workflow is automatic when running the sync:

```bash
# One-time sync
python scripts/run_synth_pm.py sync

# Scheduled sync (every 5 minutes)
python scripts/run_synth_pm.py scheduled --interval 5
```

### Via API

```python
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase

container = get_container()
use_case = container[SynthPMUseCase]

result = await use_case.sync_developer_board_features()
print(result)
```

## Troubleshooting

### Issue: Stories Not Created

**Symptoms**: Features created as standalone tasks, not subtasks

**Possible Causes:**
1. Release column is empty or missing
2. Features don't meet validation requirements
3. Sprint information missing

**Solution:**
- Ensure all features have release column populated
- Check logs for validation errors
- Verify sprint assignments exist

### Issue: Duplicate Stories

**Symptoms**: Multiple stories for same release

**Possible Causes:**
1. Release names have typos or variations
2. Concurrent sync operations

**Solution:**
- Standardize release naming conventions
- Use consistent capitalization and formatting
- Avoid running multiple syncs simultaneously

### Issue: Subtasks Not Linked to Parent

**Symptoms**: Subtasks appear as standalone tasks

**Possible Causes:**
1. Parent story creation failed
2. Jira permissions issue
3. Invalid parent key

**Solution:**
- Check Jira user has permission to create sub-tasks
- Verify story was created successfully
- Review error logs for specific failures

### Issue: Wrong Team Members Assigned

**Symptoms**: Subtasks assigned to wrong people

**Possible Causes:**
1. UserConfig mapping incorrect
2. "Involved People" column format wrong
3. Name matching issues

**Solution:**
- Verify UserConfig has correct google_sheet_name
- Use exact names as configured
- Check user config with: `python scripts/run_synth_pm.py config`

## Best Practices

### Release Naming
- Use semantic versioning: "Version 2.5.0"
- Include project identifier if needed: "Mobile v2.5.0"
- Be consistent across all features
- Avoid special characters

### Feature Organization
- Group related features in same release
- Keep releases reasonably sized (5-15 features)
- Align releases with sprint boundaries
- Use epics for larger initiatives across releases

### Sheet Management
- Fill release column before status reaches "۵. آماده پیاده سازی فنی"
- Update release if feature scope changes
- Don't change release names after creation (creates new story)
- Archive completed releases to separate sheet

### Sprint Planning
- Include entire release stories in sprints when possible
- Consider dependencies between features in a release
- Monitor release progress via story completion
- Use release labels for filtering and reporting

## Migration Guide

### From Old Workflow to Release-Based

If you have existing tasks created without releases:

1. **Update Google Sheet**: Add release values to existing rows
2. **Run Sync**: System will create stories and link existing tasks
3. **Manual Cleanup** (optional): 
   - Move existing standalone tasks under release stories manually
   - Or let them coexist (recommended - don't break existing work)

### Gradual Adoption

You can adopt gradually:
- Old rows without releases: Create as before (standalone tasks)
- New rows with releases: Create as subtasks under stories
- No breaking changes to existing functionality

## API Reference

### New Repository Methods

```python
async def get_story_by_release_name(
    release_name: str
) -> Optional[str]:
    """Check if story exists for release."""
    pass

async def create_release_story(
    release_name: str,
    features: List[SynthPMFeatureEntity]
) -> Optional[str]:
    """Create a release story."""
    pass

async def create_subtask_for_release(
    parent_story_key: str,
    feature: SynthPMFeatureEntity,
    assignees: Optional[List[str]] = None
) -> Optional[str]:
    """Create subtask under release story."""
    pass
```

### New Use Case Methods

```python
def _group_features_by_release(
    features: List[SynthPMFeatureEntity]
) -> Dict[str, List[SynthPMFeatureEntity]]:
    """Group features by release column."""
    pass

async def _create_release_story_with_subtasks(
    release_name: str,
    features: List[SynthPMFeatureEntity],
    sync_results: Dict[str, Any]
) -> Optional[str]:
    """Create release story and all subtasks."""
    pass
```

## Monitoring and Reporting

### Sync Results

The sync operation returns enhanced results:

```python
{
    "status": "success",
    "results": {
        "created_jira_tasks": 5,           # PM Board tasks
        "created_developer_board_tasks": 8, # Stories + Subtasks
        "updated_jira_tasks": 2,
        "updated_developer_board_tasks": 3,
        "skipped": [],
        "errors": []
    }
}
```

### Logs

Key log messages:

```
INFO: Grouped features into 3 releases: ['Version 2.5.0', 'Version 2.6.0', 'No Release']
INFO: Processing release 'Version 2.5.0' with 5 features
INFO: Created release story DEV-1234 for Version 2.5.0
INFO: Created subtask DEV-1235 for feature Implement user authentication
INFO: Successfully processed release 'Version 2.5.0' with story DEV-1234
```

### Jira Queries

Useful JQL queries:

```jql
# All release stories
project = DEV AND issuetype = Story AND summary ~ "Release:"

# Specific release
project = DEV AND issuetype = Story AND summary ~ "Version 2.5.0"

# All subtasks in a release
parent = DEV-1234

# Incomplete features in release
parent = DEV-1234 AND status != Done

# Releases in current sprint
project = DEV AND issuetype = Story AND summary ~ "Release:" AND sprint = "DEV Sprint 45"
```

## Conclusion

The release-based workflow provides significant improvements in task organization, visibility, and management. By automatically grouping features by release and creating a hierarchical structure, teams can better plan, track, and deliver their work.

For questions or issues, please refer to the main SynthPM documentation or contact the development team.
