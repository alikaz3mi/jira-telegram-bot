# Department Dependencies Feature - Complete Explanation

## Overview

The Department Dependencies feature in SynthPM automatically schedules subtasks based on department dependencies and time estimates. This ensures that dependent tasks are properly sequenced with correct start and end dates.

## How It Works

### 1. Dependency Format

The `Department Deps` column in your Google Sheet uses this format:
```
Blocking Department blocks Blocked Department
```

**Examples:**
- `UI/UX blocks Frontend` means Frontend **depends on** (is blocked by) UI/UX
- `UI/UX blocks Frontend, Backend blocks AI` means:
  - Frontend depends on UI/UX
  - AI depends on Backend

**Alternative Format:** You can also use arrow notation:
- `UI/UX -> Frontend` (same as `UI/UX blocks Frontend`)
- Both formats can be mixed: `UI/UX blocks Frontend, Backend -> AI`

### 2. Time Calculation Logic

Given your example:
- **Task Duration**: 10 Nov to 17 Nov (7 days total)
- **Department Deps**: `UI/UX -> Frontend`
- **Time Estimates**: UI/UX = 24h, Frontend = 24h, AI = 24h

#### The Scheduling Process:

```
Timeline (working days, 8 hours/day):

┌─────────────────────────────────────────────────────┐
│                   Feature Timeline                   │
│              10 Nov ────────────► 17 Nov            │
└─────────────────────────────────────────────────────┘

With Dependencies: UI/UX -> Frontend

┌──────────────┐                      ┌──────────────┐
│   UI/UX      │                      │  Frontend    │
│   24h (3d)   │  ─────blocks────►    │   24h (3d)   │
│ 10-13 Nov    │                      │  14-17 Nov   │
└──────────────┘                      └──────────────┘

Independent:
┌──────────────┐
│     AI       │
│   24h (3d)   │  (No dependency, starts at beginning)
│ 10-13 Nov    │
└──────────────┘
```

### 3. Step-by-Step Calculation

#### Example Scenario:
- **Feature Deadline**: 17 Nov
- **Departments**: UI/UX (24h), Frontend (24h), AI (24h)
- **Dependencies**: `UI/UX -> Frontend`

#### Calculation:

**Step 1: Identify Independent vs Dependent Departments**
- **Dependent**: Frontend (depends on UI/UX)
- **Independent**: UI/UX (no dependencies), AI (no dependencies)

**Step 2: Work Backwards from Deadline**

1. **Frontend** (blocked department):
   - Must finish by: **17 Nov** (feature deadline)
   - Duration: 24h = 3 working days
   - Working backwards: 17 Nov → 16 Nov → 15 Nov (skip Friday 14th) → 14 Nov
   - **Frontend dates: 14 Nov (start) to 17 Nov (end)**

2. **UI/UX** (blocks Frontend):
   - Must finish BEFORE Frontend starts: **< 14 Nov**
   - End date: **13 Nov** (day before Frontend starts)
   - Duration: 24h = 3 working days
   - Working backwards: 13 Nov → 12 Nov → 11 Nov → 10 Nov
   - **UI/UX dates: 10 Nov (start) to 13 Nov (end)**

3. **AI** (independent, no dependencies):
   - Can start immediately: **10 Nov** (feature start)
   - Duration: 24h = 3 working days
   - **AI dates: 10 Nov (start) to 13 Nov (end)**

### 4. Multiple Dependencies

If you have: `UI/UX -> Frontend, Backend -> Frontend`

This means Frontend depends on **BOTH** UI/UX and Backend completing first.

```
┌──────────────┐
│   UI/UX      │  ─────┐
│   24h (3d)   │       │
│ 10-13 Nov    │       │
└──────────────┘       │
                       ├─────blocks────►  ┌──────────────┐
┌──────────────┐       │                  │  Frontend    │
│   Backend    │  ─────┘                  │   24h (3d)   │
│   24h (3d)   │                          │  14-17 Nov   │
│ 10-13 Nov    │                          └──────────────┘
└──────────────┘
```

Frontend will only start after **both** UI/UX and Backend are complete.

## Implementation Details

### Code Components

1. **DepartmentDependencyCalculator** (`entities/synth_pm/department_dependency_calculator.py`)
   - Parses dependency strings
   - Calculates working days (excluding Fridays and holidays)
   - Schedules department start/end dates

2. **SynthPMRepository** (`adapters/repositories/synth_pm_repository.py`)
   - Creates subtasks with calculated dates
   - Links subtasks with blocking relationships
   - Updates subtask schedules when feature changes

### Key Methods

#### `parse_department_deps()`
Converts string format to dictionary (supports both "blocks" and "->" formats):
```python
Input: "UI/UX blocks Frontend, Backend blocks AI"
# OR
Input: "UI/UX -> Frontend, Backend -> AI"
Output: {
    "Frontend": ["UI/UX"],
    "AI": ["Backend"]
}
```

#### `calculate_department_deadlines()`
Calculates start/end dates for each department:
```python
Input:
- feature_deadline: 17 Nov
- dept_deps: {"Frontend": ["UI/UX"]}
- department_hours: {"UI/UX": 24, "Frontend": 24}
- holidays: set()

Output: {
    "UI/UX": {"start": 10 Nov, "end": 13 Nov},
    "Frontend": {"start": 14 Nov, "end": 17 Nov}
}
```

#### `_create_subtasks_for_assignees()`
Creates Jira subtasks with:
- Calculated start/end dates
- Story point allocations
- Blocking links between subtasks

## Business Rules

### Working Days
- **8 hours = 1 working day**
- **Friday is excluded** (Iranian weekend)
- **Holidays are excluded** (from Jira settings)

### Date Calculations
- All calculations work **backwards from the feature deadline**
- Dependent tasks are scheduled **before** the tasks that depend on them
- Independent tasks start at the **feature start date**

### Subtask Creation
1. Each assignee gets a subtask for their department
2. Subtasks inherit:
   - Component (department)
   - Time estimate (story points in hours)
   - Start/End dates
   - Sprint assignment
3. Blocking links are created between subtasks matching the department dependencies

## Example Scenarios

### Scenario 1: Simple Chain
```
Dependency: UI/UX -> Frontend
Timeline: 10 Nov - 17 Nov
Estimates: UI/UX=24h, Frontend=24h

Result:
- UI/UX: 10 Nov - 13 Nov (3 days)
- Frontend: 14 Nov - 17 Nov (3 days)
```

### Scenario 2: Parallel + Sequential
```
Dependency: Backend -> Frontend
Timeline: 10 Nov - 17 Nov
Estimates: Backend=24h, Frontend=24h, AI=24h

Result:
- Backend: 10 Nov - 13 Nov (3 days) → blocks Frontend
- AI: 10 Nov - 13 Nov (3 days) → independent, parallel
- Frontend: 14 Nov - 17 Nov (3 days) → depends on Backend
```

### Scenario 3: Multiple Blockers
```
Dependency: UI/UX -> Frontend, Backend -> Frontend
Timeline: 10 Nov - 20 Nov
Estimates: UI/UX=24h, Backend=24h, Frontend=32h

Result:
- UI/UX: 10 Nov - 13 Nov (3 days) → blocks Frontend
- Backend: 10 Nov - 13 Nov (3 days) → blocks Frontend
- Frontend: 14 Nov - 20 Nov (4 days) → starts after both complete
```

### Scenario 4: No Dependencies
```
Dependency: (empty)
Timeline: 10 Nov - 17 Nov
Estimates: UI/UX=24h, Frontend=24h, Backend=24h

Result:
- All departments work in parallel
- All start: 10 Nov
- All end: 13 Nov (based on their individual estimates)
```

## Jira Integration

### Subtask Creation
When a feature is synced to Jira:
1. A parent story is created in the Developer Board
2. For each assignee/department:
   - A subtask is created
   - The subtask is assigned to the team member
   - Start/end dates are set based on dependencies
   - Story points (hours) are assigned

### Blocking Links
Jira issue links of type "Blocks" are created:
```
UI/UX Subtask ──[blocks]──► Frontend Subtask
```

This ensures:
- Visual dependency representation in Jira
- Workflow enforcement (can't close Frontend before UI/UX)
- Proper Gantt chart visualization

### Updates
When dependencies change in the Google Sheet:
1. The system recalculates all department dates
2. Subtask dates are updated
3. Blocking links are recreated
4. Assignees are notified of date changes

## Troubleshooting

### Common Issues

**Q: Frontend starts the same day as UI/UX**
- **Cause**: No dependency specified in "Department Deps" column
- **Fix**: Add `UI/UX -> Frontend` to the column

**Q: Task dates don't respect Friday weekend**
- **Cause**: Holiday calculation issue
- **Fix**: Check Jira holiday settings in your configuration

**Q: Subtasks overlap when they shouldn't**
- **Cause**: Incorrect dependency format
- **Fix**: Ensure format is `Blocker -> Blocked` (e.g., `UI/UX -> Frontend`)

**Q: AI department has wrong dates**
- **Cause**: AI might have an unintended dependency
- **Fix**: If AI should be independent, ensure it's not listed in "Department Deps"

## Configuration

### Settings (synth_pm_settings.py)
- `developer_board_project_key`: Jira project for developer tasks
- `developer_board_worksheet_name`: Google Sheet worksheet name
- Holiday settings inherited from Jira configuration

### Column Mapping (synth_pm_repository.py)
The system maps Google Sheet columns:
- "Department Deps" → `department_deps` field
- "ETA(h)" → individual department hours
- "Deadline" → feature deadline
- Component columns (AI, Backend, Frontend, etc.) → department flags

## Best Practices

1. **Always specify direction**: Use `Blocker -> Blocked` format
2. **Keep dependencies simple**: Avoid circular dependencies
3. **Verify dates**: Check calculated dates in Jira after sync
4. **Update estimates**: If hours change, resync to recalculate dates
5. **Document complex chains**: Add notes for multi-level dependencies

## Future Enhancements

Potential improvements:
- Support for percentage-based dependencies (start Frontend at 80% UI/UX completion)
- Parallel partial work (Frontend starts after UI/UX reaches specific milestone)
- Resource leveling (distribute work based on team capacity)
- Dependency visualization in Telegram notifications
- Automatic adjustment when deadlines shift

---

**Last Updated**: November 2025  
**Version**: 1.0  
**Related Files**:
- `jira_telegram_bot/entities/synth_pm/department_dependency_calculator.py`
- `jira_telegram_bot/adapters/repositories/synth_pm_repository.py`
- `jira_telegram_bot/use_cases/synth_pm_usecase.py`
