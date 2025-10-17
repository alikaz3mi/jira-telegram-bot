# Department Dependencies Feature Implementation

## Overview
This feature implements department-level task dependencies with automatic deadline calculation and Jira issue linking for the SynthPM system.

## Changes Made

### 1. Entity Updates

#### `SynthPMFeatureEntity` (`jira_telegram_bot/entities/synth_pm/pm_board_features.py`)
- Added `department_deps` field to store department dependency information
- Format: "UI/UX -> Frontend, Backend -> AI" (blocking_dept -> blocked_dept)

#### `TaskData` (`jira_telegram_bot/entities/task.py`)
- Added `reporter` field to specify the task reporter (used for subtask reporter assignment)

### 2. New Module: Department Dependency Calculator

#### `DepartmentDependencyCalculator` (`jira_telegram_bot/entities/synth_pm/department_dependency_calculator.py`)

A utility class that handles:

**Key Methods:**
- `parse_department_deps()`: Parses dependency string into a dictionary
- `calculate_working_days_from_hours()`: Converts story points (hours) to working days considering holidays/weekends
- `calculate_department_deadlines()`: Calculates start/end dates for each department based on:
  - Feature deadline (working backwards)
  - Department dependencies (blocking relationships)
  - Story points per department
  - Persian calendar holidays and weekends (Fridays)
- `get_department_from_component()`: Normalizes component names to department names

**Logic:**
- Works **backwards** from the feature deadline
- Calculates end date for each department
- Considers blocking dependencies (e.g., Frontend must wait for UI/UX to complete)
- Accounts for 8-hour working days
- Skips Fridays (Iran's weekend) and holidays from Persian calendar

### 3. Repository Updates

#### `SynthPMRepository` (`jira_telegram_bot/adapters/repositories/synth_pm_repository.py`)

**Column Mapping:**
- Added "Department Deps" to column mapping for Google Sheets parsing
- Extracts dependency information from the sheet

**New Methods:**
- `get_component_lead()`: Retrieves the component lead from `projects_info.json`
- `_create_subtask_blocking_links()`: Creates Jira "Dependency" links between subtasks
- `_update_subtask_blocking_links()`: Updates Jira links when dependencies change
- `_update_subtask_time_estimates_and_dependencies()`: Updates both time and deadlines when feature changes

**Updated Methods:**
- `_create_subtasks_for_assignees()`:
  - Parses department dependencies
  - Calculates department-specific deadlines
  - Sets reporter to component lead
  - Creates subtasks with calculated dates
  - Creates blocking links between subtasks
  
- `_update_assignees_and_subtasks()`:
  - Calls new method to update dependencies along with time estimates
  
- `_update_subtask_time_estimate_and_dates()`:
  - Now accepts `department_dates` parameter
  - Uses calculated dates instead of feature dates when available

#### `JiraServerRepository` (`jira_telegram_bot/adapters/repositories/jira/jira_server_repository.py`)
- Updated `build_issue_fields()` to handle the `reporter` field

## How It Works

### Creating New Features
1. User adds a feature to Google Sheets with Department Deps (e.g., "UI/UX -> Frontend")
2. System parses the dependency string
3. For each assignee's department:
   - Calculates start/end dates based on feature deadline, story points, and dependencies
   - Creates subtask with calculated dates
   - Sets reporter to component lead from `projects_info.json`
4. Creates Jira "Dependency" links between subtasks (e.g., Frontend subtask depends on UI/UX subtask)

### Updating Existing Features
1. When Department Deps change in Google Sheets
2. System recalculates all department deadlines
3. Updates each subtask with new dates
4. Updates Jira dependency links to match new dependencies

## Example

**Sheet Configuration:**
```
Task: Implement User Profile Page
Department Deps: UI/UX -> Frontend, Frontend -> Backend
Deadline: 2025-10-30
Story Points:
  - UI/UX: 16 hours (2 days)
  - Frontend: 32 hours (4 days)
  - Backend: 24 hours (3 days)
```

**Calculated Deadlines (working backwards from Oct 30):**
```
Frontend: Oct 26-30 (4 days, ends at deadline)
UI/UX: Oct 22-23 (2 days, must complete before Frontend starts on Oct 26)
Backend: Oct 17-19 (3 days, must complete before UI/UX starts on Oct 22)
```

**Note:** In this example, if the dependencies were "UI/UX -> Frontend, Frontend -> Backend", Backend would be the last to execute (closest to deadline), since it depends on Frontend completing first.

**Jira Links:**
- Frontend subtask "depends on" UI/UX subtask
- Backend subtask "depends on" Frontend subtask

## Configuration

The system uses `projects_info.json` to determine component leads:
```json
{
  "PARSCHAT": {
    "components": [
      { "name": "Front-end", "lead": "z_lotfian" },
      { "name": "Backend", "lead": "m_samei" },
      ...
    ]
  }
}
```

## Dependencies

- **jdatetime**: Persian calendar support
- **Persian Calendar API**: Holiday data stored in `/data/storage/`
- Existing `JsonCalendarRepository` for holiday/weekend checking

## Notes

- Fridays are considered weekends (Iran's calendar)
- Each working day = 8 hours
- Dependencies are format: `blocking_dept -> blocked_dept`
- Multiple blockers supported: `UI/UX -> Frontend, Backend -> Frontend`
- Deadlines calculated backwards from feature deadline
- Reporter automatically set to component lead for all subtasks
