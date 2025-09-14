# SynthPM Filtering Feature Documentation

## Overview

The SynthPM filtering feature allows you to synchronize only specific features based on sprint names, release names, or version numbers. This is particularly useful for:

- **Performance optimization**: Sync only relevant features instead of the entire sheet
- **Focused development**: Work on specific sprints or releases
- **Testing**: Test synchronization with a subset of data
- **Deployment workflows**: Deploy features by release or sprint

## Core Components

### 1. SynthPMSyncFilterCriteria Entity

Located in `entities/synth_pm/sync_filter_criteria.py`, this entity defines the filtering criteria:

```python
from jira_telegram_bot.entities.synth_pm.sync_filter_criteria import SynthPMSyncFilterCriteria

# Filter by specific sprints
sprint_filter = SynthPMSyncFilterCriteria.create_sprint_filter(
    sprints=["Sprint-1", "Sprint-2"],
    include_empty=False  # Don't include features with no sprint
)

# Filter by releases
release_filter = SynthPMSyncFilterCriteria.create_release_filter(
    releases=["v1.0", "v1.1"],
    versions=["1.0.0", "1.1.0"],  # Can filter by both release names and version numbers
    include_empty=False
)

# Combined filtering
combined_filter = SynthPMSyncFilterCriteria.create_combined_filter(
    sprints=["Sprint-3"],
    releases=["v2.0"],
    include_empty_sprint=False,
    include_empty_release=False
)
```

### 2. Repository Level Filtering

The repository method `get_developer_board_features()` now accepts an optional filter parameter:

```python
# Get all features (default behavior)
all_features = await repository.get_developer_board_features()

# Get filtered features
filtered_features = await repository.get_developer_board_features(filter_criteria)
```

### 3. Use Case Level Integration

The main use case now supports filtering:

```python
from jira_telegram_bot.use_cases.synth_pm import SynthPMUseCase

# Sync with filter
sync_result = await synth_pm_use_case.sync_developer_board_features(filter_criteria)

# Convenience methods
sync_result = await synth_pm_use_case.sync_features_by_sprint(["Sprint-1", "Sprint-2"])
sync_result = await synth_pm_use_case.sync_features_by_release(releases=["v1.0"])
```

## Configuration Options

Add these environment variables to enable default filtering:

```bash
# Enable default filtering for all sync operations
SYNTH_PM_ENABLE_DEFAULT_FILTERING=true

# Default filters (comma-separated lists)
SYNTH_PM_DEFAULT_FILTER_SPRINTS=Sprint-1,Sprint-2
SYNTH_PM_DEFAULT_FILTER_RELEASES=v1.0,v1.1
SYNTH_PM_DEFAULT_FILTER_VERSIONS=1.0.0,1.1.0

# Include features with empty values
SYNTH_PM_FILTER_INCLUDE_EMPTY_SPRINT=false
SYNTH_PM_FILTER_INCLUDE_EMPTY_RELEASE=false
```

## Usage Examples

### Example 1: Sync Only Current Sprint

```python
# Sync features for the current sprint only
filter_criteria = SynthPMSyncFilterCriteria.create_sprint_filter(
    sprints=["Sprint-5"],
    include_empty=False
)

result = await synth_pm_use_case.sync_developer_board_features(filter_criteria)
print(f"Synced {result.get('total_features', 0)} features from Sprint-5")
```

### Example 2: Sync Features for Release Deployment

```python
# Sync features for a specific release
filter_criteria = SynthPMSyncFilterCriteria.create_release_filter(
    versions=["2.1.0"],
    include_empty=False
)

result = await synth_pm_use_case.sync_developer_board_features(filter_criteria)
print(f"Synced {result.get('total_features', 0)} features for release 2.1.0")
```

### Example 3: Using Convenience Methods

```python
# Sync by sprint using convenience method
result = await synth_pm_use_case.sync_features_by_sprint(
    sprints=["Sprint-1", "Sprint-2"],
    include_empty=False
)

# Sync by release using convenience method
result = await synth_pm_use_case.sync_features_by_release(
    releases=["v1.0"],
    include_empty=False
)
```

### Example 4: Script Usage

Update your sync scripts to use filtering:

```python
# scripts/run_synth_pm.py
import asyncio
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.synth_pm.sync_filter_criteria import SynthPMSyncFilterCriteria
from jira_telegram_bot.use_cases.synth_pm import SynthPMUseCase

async def sync_current_sprint():
    container = get_container()
    synth_pm_use_case = container[SynthPMUseCase]

    # Only sync Sprint-3 features
    result = await synth_pm_use_case.sync_features_by_sprint(["Sprint-3"])
    print(f"Sync completed: {result}")

if __name__ == "__main__":
    asyncio.run(sync_current_sprint())
```

## Filter Behavior

### Sprint Filtering
- **Exact match**: Feature's `sprint` field must exactly match one of the provided sprint names
- **Case sensitive**: "Sprint-1" ≠ "sprint-1"
- **Empty handling**: Control whether features with no sprint are included via `include_empty_sprint`

### Release Filtering
- **Dual field support**: Filters against both `release` and `version` fields
- **OR logic**: Feature is included if it matches either the release name OR version number
- **Empty handling**: Control whether features with no release/version are included via `include_empty_release`

### Combined Filtering
- **AND logic**: Feature must match ALL specified criteria (sprints AND releases)
- **Flexible**: Can specify any combination of sprints, releases, and versions

## Performance Benefits

### Before Filtering
```
[INFO] Retrieved 182 features
```

### After Filtering
```
[INFO] Retrieved 15 features (filtered from all features)
```

The filtering reduces:
- **Network overhead**: Less data transferred from Google Sheets
- **Processing time**: Fewer features to validate and sync
- **Jira API calls**: Only relevant features are processed
- **Memory usage**: Smaller datasets in memory

## Monitoring and Logging

Filter operations are logged for visibility:

```
[INFO] Applying sync filter criteria: sprints=['Sprint-1'], releases=['v1.0'], versions=None
[INFO] Retrieved 15 features (filtered from all features)
```

## Testing

Test the filtering functionality:

```bash
python scripts/test_synth_pm_filtering.py
```

This test script verifies:
- Filter entity creation
- Filter logic correctness
- Repository integration
- Convenience method functionality

## Migration Guide

### For Existing Code

Existing code continues to work without changes:
```python
# This still works - no filtering applied
features = await repository.get_developer_board_features()
sync_result = await synth_pm_use_case.sync_developer_board_features()
```

### To Add Filtering

Simply pass filter criteria:
```python
# Add filtering
filter_criteria = SynthPMSyncFilterCriteria.create_sprint_filter(["Sprint-1"])
features = await repository.get_developer_board_features(filter_criteria)
sync_result = await synth_pm_use_case.sync_developer_board_features(filter_criteria)
```

## Best Practices

1. **Use specific filters**: Filter by current sprint/release rather than syncing everything
2. **Configure defaults**: Set up default filters in environment variables for consistent behavior
3. **Monitor performance**: Check logs to see filtering effectiveness
4. **Test filters**: Use the test script to verify filter criteria before production
5. **Document sprints**: Use consistent sprint naming (e.g., "Sprint-1", "Sprint-2")
6. **Regular cleanup**: Remove old sprint/release filters from configuration
