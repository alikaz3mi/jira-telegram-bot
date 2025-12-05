# Story Synchronization - Implementation Summary

## Overview

Implemented a complete story synchronization feature that automatically syncs Jira story data (including worklog progress tracking) to Google Sheets. The implementation follows Clean Architecture principles with a repository pattern for data access and uses shared entities with the SynthPM module to avoid duplication.

## Recent Refactoring (Latest Updates)

### Entity Consolidation
- **Deleted**: `StorySheetRow` entity (was duplicate)
- **Now Uses**: `SynthPMFeatureEntity` from `entities/synth_pm/` (shared with SynthPM feature)
- **Benefit**: Single source of truth for feature/story data structure

### Repository Pattern Implementation
- **Created**: `TaskStoryRepository` for Google Sheets operations
- **Enhanced**: `JiraServerRepository` with worklog and time tracking methods
- **Moved Logic**: Worklog extraction and time tracking from use case to repository layer
- **Benefits**: Reusable across features, no duplication, easier to test

### Constants Migration
- **Added**: `DEPARTMENT_MAPPING` to `entities/story_synchronization/constants.py`
- **Removed**: Hardcoded department mapping from use case
- **Benefits**: Single place to update department mappings, follows Clean Architecture

### Column Mapping Consolidation
- **Unified**: `_parse_row_to_feature()` implementation between `TaskStoryRepository` and `SynthPMRepository`
- **Benefit**: Consistent parsing logic across the codebase

## What Was Created/Modified

### 1. Entities (`jira_telegram_bot/entities/`)

#### `synth_pm/pm_board_features.py`
- **`SynthPMFeatureEntity`**: Shared Pydantic entity (frozen=True) representing features/stories
  - 41+ fields including all tracking data
  - Used by both SynthPM and story synchronization features

#### `story_synchronization/constants.py`
- **`JIRA_TO_STORY_SYNC_STATUS`**: Maps Jira workflow statuses to Persian Google Sheet statuses
- **`STORY_SYNC_PRESERVE_STATUSES`**: PM/Business statuses that shouldn't be overwritten
- **`DEPARTMENT_MAPPING`**: Maps department names to field names (NEW)

#### `story_synchronization/story_sync_config.py`
- **`SheetBoardMapping`**: Maps a Jira board to a Google Sheet tab
- **`StorySyncConfig`**: Container for all mappings with validation

### 2. Repositories (`jira_telegram_bot/adapters/repositories/`)

#### `task_story_repository.py` (NEW)
- Implements `TaskStoryRepositoryInterface`
- **`get_sheet_features()`**: Reads features from Google Sheets
- **`update_sheet_feature()`**: Updates specific rows
- **`extract_issue_keys_from_features()`**: Extracts Jira issue keys
- **`_create_column_mapping()`**: Dynamic column mapping from headers
- **`_parse_row_to_feature()`**: Converts sheet rows to `SynthPMFeatureEntity`

#### `jira/jira_server_repository.py` (ENHANCED)
- **`get_worklog_data()`** (NEW): Repository method for worklog extraction
  - Fetches worklogs with expansion
  - Aggregates progress hours
  - Maps Jira usernames to Google Sheet names via UserConfig
  - Attributes hours to departments using `DEPARTMENT_MAPPING`
  - Returns: `(progress_hours, involved_people, dept_hours, individual_hours)`
  
- **`get_time_tracking()`** (NEW): Repository method for time estimates
  - Extracts ETA and total hours from Jira fields
  - Returns: `(eta_hours, total_hours)`

### 3. Use Cases (`jira_telegram_bot/use_cases/`)

#### Interfaces
- **`task_story_repository_interface.py`** (NEW): Interface for Google Sheets operations
- **`task_manager_repository_interface.py`** (ENHANCED): Added worklog methods

#### `story_synchronization/fetch_story_data_use_case.py`
- Fetches story data from Jira
- **Now uses repository methods** instead of internal logic:
  - `task_manager.get_time_tracking(issue)` 
  - `task_manager.get_worklog_data(issue)`
- Converts Jira issues to `SynthPMFeatureEntity`
- Maps statuses using `JIRA_TO_STORY_SYNC_STATUS`

#### `story_synchronization/sync_story_to_sheets_use_case.py`
- **Now uses** `TaskStoryRepositoryInterface` for Google Sheets operations
- **Now uses** `SynthPMFeatureEntity` throughout (was `StorySheetRow`)
- Full sync mode: Clears and rewrites all data
- Incremental sync mode: Updates only changed stories
- Preserves statuses in `STORY_SYNC_PRESERVE_STATUSES`
- Retry logic for Google Sheets quota errors

### 3. Configuration

- **`config/story_sync_config.json`**: Board-to-sheet mappings
  - Configured for ParsChat Features sheet
  - Spreadsheet ID: 1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4
  - Sheet name: "ParsChat Features"
  - Board key: PARSCHAT

### 4. Script (`scripts/sync_stories.py`)

CLI tool with three commands:
- **`sync`**: Manual one-time sync
  - `--boards`: Sync specific boards
  - `--full`: Full sync (all data)
  - `--days-back`: Custom days to look back
- **`scheduled`**: Continuous sync (cron-ready)
  - `--interval`: Minutes between syncs (default: 5)
  - `--days-back-scheduled`: Days to track (default: 7)
- **`test`**: Test connections to Jira and Google Sheets

### 5. Dependency Injection

Updated `config_dependency_injection.py`:
- Added imports for story synchronization entities and use cases
- Added `_load_story_sync_config()` function
- Registered `StorySyncConfig` entity
- Registered `TaskStoryRepositoryInterface` → `TaskStoryRepository`
- Registered `FetchStoryDataUseCase`
- Registered `SyncStoryToSheetsUseCase`
- Enhanced `JiraServerRepository` registration (no changes needed - backward compatible)

### 6. Tests (`tests/use_cases/story_synchronization/`)

- **`test_fetch_story_data_use_case.py`**: Tests for fetch use case
  - Now uses `SynthPMFeatureEntity` instead of `StorySheetRow`
  - Tests JQL building, issue conversion, worklog aggregation
  - Mocks repository methods for worklog and time tracking
  
- **`test_sync_story_to_sheets_use_case.py`**: Tests for sync use case
  - Now uses `SynthPMFeatureEntity` throughout
  - Tests full and incremental sync modes
  - Tests retry logic and error handling

**All tests updated and passing**

## Key Features

### Repository-Based Worklog Tracking

The worklog extraction logic is now centralized in `JiraServerRepository`:

**`get_worklog_data(issue)` method:**
1. Fetches issue with worklog expansion
2. Iterates through all worklogs
3. Sums `timeSpentSeconds` to calculate progress hours
4. Uses `UserConfig` to map Jira usernames to Google Sheet names
5. Attributes hours to departments using `DEPARTMENT_MAPPING` constant
6. Builds individual developer hours mapping

**Benefits:**
- ✅ Reusable across different features (not just story sync)
- ✅ No code duplication
- ✅ Consistent user name mapping
- ✅ Centralized department attribution
- ✅ Easier to test and maintain
- ✅ Follows Clean Architecture (repository handles data access)

### Repository-Based Time Tracking

**`get_time_tracking(issue)` method:**
1. Extracts time tracking from Jira fields
2. Returns ETA and total hours
3. Handles both `timetracking` object and `timeoriginalestimate` field

### Unified Entity Model

Uses `SynthPMFeatureEntity` shared with SynthPM feature:
- ✅ Single source of truth
- ✅ No duplicate entity definitions
- ✅ Consistent data structure across features
- ✅ Easier maintenance

### Google Sheets Repository

`TaskStoryRepository` handles all Google Sheets operations:
- Dynamic column mapping from sheet headers
- Unified `_parse_row_to_feature()` implementation (same as SynthPM)
- Supports reading and updating features
- Proper error handling and logging

### Status Synchronization

- Maps Jira workflow statuses to Persian Google Sheet statuses
- Uses existing `JIRA_TO_GOOGLE_SHEET_STATUS` constant
- Updates وضعیت column on every sync

### Department Hours

Breaks down logged hours by department:
- AI team hours
- Backend team hours
- Frontend team hours
- DevOps team hours
- UI/UX team hours

Based on user configuration (`user_config.json`).

### Individual Developer Tracking

Tracks hours for 18 individual developers:
کاظمی، موسوی، مرادی، جانلو، سجادی، حسینی، قمری، زنگنه، سامعی، اروجی، لطفیان، آدابی، دادجو، قاسمی، صدرایی، امام دادی، نسیم، هروی

### Incremental Updates

- Only fetches stories updated in the last N days (default: 30)
- Updates existing rows with latest Progress (h) and status
- Appends new rows for newly created stories
- Preserves old stories not in the current fetch window

## Usage Examples

### Daily Full Sync (Cron)
```bash
0 8 * * * cd $(pwd) && python scripts/sync_stories.py sync --full
```

### Incremental Sync Every 15 Minutes
```bash
*/15 * * * * cd $(pwd) && python scripts/sync_stories.py sync --days-back 7
```

### Continuous Scheduled Sync
```bash
python scripts/sync_stories.py scheduled --interval 10 --days-back-scheduled 14
```

## Architecture Compliance

✅ **Clean Architecture**: Follows all principles
- Entities are pure business objects (Pydantic models with frozen=True)
- Use cases contain application logic only
- Repositories handle all data access (Jira API, Google Sheets)
- Dependencies flow inward (frameworks → adapters → use cases → entities)
- No framework dependencies in use cases or entities

✅ **Repository Pattern**: Properly implemented
- `TaskStoryRepository`: Google Sheets data access
- `JiraServerRepository`: Jira API data access with worklog methods
- Interfaces define contracts (`TaskStoryRepositoryInterface`, `TaskManagerRepositoryInterface`)
- Use cases depend on interfaces, not implementations

✅ **Shared Entities**: No duplication
- Uses `SynthPMFeatureEntity` from synth_pm module
- Deleted `StorySheetRow` duplicate entity
- Constants in `entities/story_synchronization/constants.py`

✅ **Copilot Custom Instructions**: Fully compliant
- Snake_case for functions and variables
- PascalCase for classes
- NumPy-style docstrings with type annotations
- No inline comments (only docstrings)
- Type annotations throughout
- Lagom dependency injection
- Pydantic entities with proper validation

✅ **Testing**: High coverage with unittest
- Unit tests for all use cases
- Mocking external dependencies
- Arrange-Act-Assert pattern
- Updated to use `SynthPMFeatureEntity`

## Integration Points

### Existing Components Used
- `TaskManagerRepositoryInterface`: Jira issue fetching + **worklog methods (NEW)**
- `UserConfigInterface`: User department and name mapping
- `SpreadsheetGatewayInterface`: Google Sheets operations
- `SynthPMFeatureEntity`: Shared entity from synth_pm module
- `JIRA_TO_STORY_SYNC_STATUS`: Status mapping constant

### New Components Created
- `TaskStoryRepository`: Google Sheets repository for story sync
- `TaskStoryRepositoryInterface`: Interface for Google Sheets operations
- `StorySyncConfig`: Story-specific configuration
- `DEPARTMENT_MAPPING`: Department name to field name mapping
- Repository methods in `JiraServerRepository`:
  - `get_worklog_data()`: Worklog extraction and aggregation
  - `get_time_tracking()`: Time estimate extraction

### Refactoring Improvements
- ❌ Removed `StorySheetRow` duplicate entity
- ❌ Removed hardcoded `DEPARTMENT_MAPPING` from use case
- ❌ Removed duplicate worklog extraction logic
- ❌ Removed duplicate time tracking logic
- ✅ Consolidated to use `SynthPMFeatureEntity`
- ✅ Moved worklog logic to repository layer
- ✅ Unified column parsing with SynthPM
- ✅ Constants properly placed in entities layer

## Future Enhancements

Potential improvements for the future:
- Real-time sync via Jira webhooks
- Worklog comment inclusion
- Historical worklog tracking
- Custom field support
- Filtering by labels or sprints
- Dashboard generation
- Email notifications

## Files Created/Modified

### Created
1. **Entities**
   - `jira_telegram_bot/entities/story_synchronization/__init__.py`
   - `jira_telegram_bot/entities/story_synchronization/constants.py` (includes DEPARTMENT_MAPPING)
   - `jira_telegram_bot/entities/story_synchronization/story_sync_config.py`

2. **Repositories**
   - `jira_telegram_bot/adapters/repositories/task_story_repository.py`

3. **Interfaces**
   - `jira_telegram_bot/use_cases/interfaces/task_story_repository_interface.py`

4. **Use Cases**
   - `jira_telegram_bot/use_cases/story_synchronization/__init__.py`
   - `jira_telegram_bot/use_cases/story_synchronization/fetch_story_data_use_case.py`
   - `jira_telegram_bot/use_cases/story_synchronization/sync_story_to_sheets_use_case.py`

5. **Configuration**
   - `config/story_sync_config.json`

6. **Scripts**
   - `scripts/sync_stories.py`

7. **Documentation**
   - `docs/features/story-synchronization/README.md`
   - `docs/features/story-synchronization/IMPLEMENTATION_SUMMARY.md`

8. **Tests**
   - `tests/use_cases/story_synchronization/__init__.py`
   - `tests/use_cases/story_synchronization/test_fetch_story_data_use_case.py`
   - `tests/use_cases/story_synchronization/test_sync_story_to_sheets_use_case.py`

### Modified
1. `jira_telegram_bot/config_dependency_injection.py`
   - Added story synchronization DI registrations
   - Registered `TaskStoryRepository` and `TaskStoryRepositoryInterface`

2. `jira_telegram_bot/use_cases/interfaces/task_manager_repository_interface.py`
   - Added `get_worklog_data()` method
   - Added `get_time_tracking()` method

3. `jira_telegram_bot/adapters/repositories/jira/jira_server_repository.py`
   - Implemented `get_worklog_data()` method
   - Implemented `get_time_tracking()` method
   - Added helper methods: `_get_google_sheet_name()`, `_get_user_department()`

### Deleted (Refactoring)
1. `jira_telegram_bot/entities/story_synchronization/story_sheet_row.py` ❌ (replaced by SynthPMFeatureEntity)

### Renamed (Refactoring)
1. `story_sync_repository.py` → `task_story_repository.py`
2. `StorySyncRepositoryInterface` → `TaskStoryRepositoryInterface`

## Testing Results

All tests updated to use `SynthPMFeatureEntity` and passing successfully.

### Test Coverage
- ✅ Use case tests updated
- ✅ Mocking repository methods
- ✅ No syntax errors
- ✅ All files compile successfully

## Conclusion

The story synchronization feature is **production-ready** and follows all project conventions with significant improvements:

### ✅ Achievements
1. **Clean Architecture**: Proper separation of concerns with repository pattern
2. **No Duplication**: Unified entity model (`SynthPMFeatureEntity`), shared worklog logic
3. **Reusability**: Worklog and time tracking methods can be used by other features
4. **Maintainability**: Constants in proper layer, single source of truth
5. **Testability**: Repository methods easy to mock and test
6. **Scalability**: Repository pattern allows easy extension

### 🎯 Key Improvements from Refactoring
- Moved worklog extraction to `JiraServerRepository` (reusable)
- Moved time tracking to `JiraServerRepository` (reusable)
- Deleted duplicate `StorySheetRow` entity
- Created `TaskStoryRepository` for Google Sheets operations
- Moved `DEPARTMENT_MAPPING` to constants layer
- Unified column parsing logic with SynthPM

The feature provides automated worklog tracking, status synchronization, and comprehensive data aggregation to Google Sheets, enabling better project visibility and metrics tracking.
