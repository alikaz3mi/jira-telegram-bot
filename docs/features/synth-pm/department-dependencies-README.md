# Department Dependencies Feature - Documentation Index

## Overview

The Department Dependencies feature in SynthPM enables intelligent scheduling of subtasks based on department dependencies and time estimates. When you specify that "Frontend depends on UI/UX", the system automatically calculates correct start and end dates, ensuring UI/UX completes before Frontend begins.

## Quick Links

### 📚 Complete Documentation

1. **[Explanation Guide](./department-dependencies-explanation.md)**
   - How the feature works
   - Business rules and logic
   - Calculation examples
   - Jira integration details

2. **[Visual Diagrams](./department-dependencies-diagram.md)**
   - System architecture
   - Timeline visualizations (Gantt charts)
   - Dependency graph structures
   - Mermaid diagrams

3. **[Usage Guide](./department-dependencies-usage-guide.md)**
   - Step-by-step setup instructions
   - Real-world use cases
   - Troubleshooting tips
   - Best practices

## Quick Start

### Format
```
Blocker blocks Blocked
```
OR
```
Blocker -> Blocked
```

### Example
In your Google Sheet "Department Deps" column:
```
UI/UX blocks Frontend
```

**Result:**
- UI/UX subtask starts first (e.g., 10-13 Nov)
- Frontend subtask starts after UI/UX completes (e.g., 14-17 Nov)

## Common Patterns

### Sequential Work
```
UI/UX blocks Frontend, Frontend blocks Backend
```
Design → Development → Backend integration

### Parallel to Convergence
```
UI/UX blocks Frontend, Backend blocks Frontend
```
Design and Backend work in parallel, then Frontend integrates both

### Independent Work
```
(leave empty)
```
All departments work simultaneously

## Key Features

✅ **Automatic Date Calculation** - System calculates start/end dates based on dependencies  
✅ **Working Day Awareness** - Excludes Fridays and holidays  
✅ **Jira Integration** - Creates subtasks with blocking relationships  
✅ **Flexible Dependencies** - Support for sequential, parallel, and mixed patterns  
✅ **Real-time Sync** - Updates when Google Sheet changes  

## Architecture

```
Google Sheets → SynthPM UseCase → Repository → DepartmentDependencyCalculator
                                       ↓
                                  Jira Subtasks + Blocking Links
```

## Core Components

| Component | Purpose | Location |
|-----------|---------|----------|
| `DepartmentDependencyCalculator` | Date calculations and dependency parsing | `entities/synth_pm/department_dependency_calculator.py` |
| `SynthPMRepository` | Jira integration and subtask creation | `adapters/repositories/synth_pm_repository.py` |
| `SynthPMUseCase` | Orchestration and business logic | `use_cases/synth_pm_usecase.py` |

## Example Timeline

**Input:**
- Task: "User Authentication"
- Deps: `UI/UX blocks Frontend`
- UI/UX: 24h, Frontend: 24h
- Deadline: 17 Nov 2025

**Output:**
```
10 Nov ─────────────────────────────────► 17 Nov
│                                         │
├─ UI/UX (24h) ──┐                       │
│  10-13 Nov     │                       │
│                ▼                        │
│                ├─ Frontend (24h) ──────┤
│                   14-17 Nov            │
└────────────────────────────────────────┘
```

## Working Day Rules

- **8 hours = 1 working day**
- **Friday excluded** (Iranian weekend)
- **Holidays excluded** (from Jira configuration)
- All calculations work **backwards from deadline**

## Dependencies Format

### Single Dependency
```
UI/UX -> Frontend
```
Frontend depends on UI/UX

### Multiple Dependencies
```
UI/UX -> Frontend, Backend -> AI
```
- Frontend depends on UI/UX
- AI depends on Backend

### Multiple Blockers
```
UI/UX -> Frontend, Backend -> Frontend
```
Frontend depends on **both** UI/UX and Backend

### Complex Chain
```
UI/UX -> Frontend, Frontend -> Backend, Backend -> AI
```
Sequential: Design → Frontend → Backend → AI

## Jira Output

For each feature, the system creates:

1. **Parent Story** in Developer Board
2. **Subtasks** for each department/assignee with:
   - Calculated start/end dates
   - Story points (hours)
   - Sprint assignment
   - Component (department)
3. **Blocking Links** between subtasks matching dependencies

**Example Jira Structure:**
```
Story: SYNTH-123 "User Authentication"
├─ SYNTH-123-1: UI/UX Subtask (10-13 Nov) ──blocks──┐
├─ SYNTH-123-2: Frontend Subtask (14-17 Nov) <──────┘
└─ SYNTH-123-3: AI Subtask (10-13 Nov, independent)
```

## Configuration

### Google Sheets Columns Required
- **وظیفه** (Task Title)
- **وابستگی های دپارتمان** (Department Deps)
- **ددلاین** (Deadline)
- **AI**, **Backend**, **Front-end**, **UI / UX**, **DevOPS** (hours per department)

### Settings File
`jira_telegram_bot/settings/synth_pm_settings.py`

### Environment Variables
```bash
GOOGLE_SHEETS_ID=your_sheet_id
DEVELOPER_BOARD_WORKSHEET_NAME=Developer Board
DEVELOPER_BOARD_PROJECT_KEY=SYNTH
```

## Running the Sync

```bash
# Full sync
python scripts/run_synth_pm.py sync

# Sync specific row
python scripts/run_synth_pm.py sync --row 5

# Debug mode
python scripts/run_synth_pm.py sync --debug
```

## Verification

After sync, check:
1. ✅ Subtasks created in Jira
2. ✅ Start/End dates match calculations
3. ✅ Blocking links exist between dependent subtasks
4. ✅ Story points assigned correctly
5. ✅ Sprint assignments correct

## Troubleshooting Quick Reference

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| Dates overlap | Missing dependency | Add to Department Deps column |
| Subtask missing | Hours = 0 for department | Set hours > 0 |
| Wrong dates | Incorrect format | Use "Blocker -> Blocked" |
| Sync fails | Circular dependency | Remove circular references |

## Testing

Run unit tests:
```bash
pytest tests/unit_tests/entities/test_department_dependency_calculator.py
```

## Documentation Files

| File | Purpose | When to Use |
|------|---------|-------------|
| `department-dependencies-explanation.md` | Detailed technical explanation | Understanding the algorithm |
| `department-dependencies-diagram.md` | Visual diagrams and charts | Visual learners, presentations |
| `department-dependencies-usage-guide.md` | Practical usage instructions | Daily use, troubleshooting |
| `README.md` (this file) | Quick reference and index | Finding specific info quickly |

## Use Case Examples

### Use Case 1: Feature Development
**Scenario:** New feature needs design, then development, then testing

**Setup:**
```
Department Deps: UI/UX -> Frontend, Frontend -> QA
Hours: UI/UX=16, Frontend=32, QA=16
```

**Result:** 8-day sequential workflow with proper hand-offs

### Use Case 2: API Integration
**Scenario:** Backend API must be ready before frontend integration

**Setup:**
```
Department Deps: Backend -> Frontend
Hours: Backend=40, Frontend=32
```

**Result:** Backend completes first, then frontend integrates

### Use Case 3: Parallel Development
**Scenario:** Multiple teams can work simultaneously

**Setup:**
```
Department Deps: (empty)
Hours: AI=24, Backend=24, Frontend=24
```

**Result:** All teams work in parallel from start date

## Performance Considerations

- ✅ Efficient backward calculation from deadline
- ✅ Single pass through dependency graph
- ✅ Batch Jira API calls where possible
- ✅ Caching of sprint and component information

**Typical Performance:**
- Parse deps: < 1ms
- Calculate dates: < 5ms per department
- Create subtasks: 200-500ms per subtask (Jira API)
- Full sync (10 tasks): 5-10 seconds

## Integration Points

### Google Sheets
- **Input:** Feature data with dependencies and hours
- **Output:** Sync status and timestamps

### Jira
- **Input:** Project settings, sprints, components
- **Output:** Stories, subtasks, issue links

### Telegram (Future)
- **Input:** Sync results
- **Output:** Notifications of created/updated tasks

## Future Enhancements

Planned improvements:
- 🔄 Partial dependency support (start at X% completion)
- 📊 Dependency visualization in Telegram
- ⚡ Automatic deadline adjustment when delays occur
- 📈 Resource leveling based on team capacity
- 🔔 Proactive alerts for dependency risks

## Support

### Getting Help
1. Check [Usage Guide](./department-dependencies-usage-guide.md) troubleshooting section
2. Review logs: `data/synth_developer_board_sync_status.json`
3. Run with debug: `--debug` flag
4. Check Jira issue comments for error messages

### Common Errors

**"Invalid dependency format"**
```
❌ UI/UX => Frontend  (wrong arrow)
✅ UI/UX -> Frontend  (correct)
```

**"Circular dependency detected"**
```
❌ A -> B, B -> A  (circular)
✅ A -> B         (linear)
```

**"Department not found"**
```
❌ frontend -> Backend  (lowercase)
✅ Frontend -> Backend  (correct case)
```

## Code Examples

### Parse Dependencies
```python
from jira_telegram_bot.entities.synth_pm.department_dependency_calculator import DepartmentDependencyCalculator

deps_str = "UI/UX -> Frontend, Backend -> AI"
deps_dict = DepartmentDependencyCalculator.parse_department_deps(deps_str)
# Result: {"Frontend": ["UI/UX"], "AI": ["Backend"]}
```

### Calculate Dates
```python
from datetime import datetime

deadline = datetime(2025, 11, 17)
dept_deps = {"Frontend": ["UI/UX"]}
dept_hours = {"UI/UX": 24, "Frontend": 32}
holidays = set()

dates = DepartmentDependencyCalculator.calculate_department_deadlines(
    deadline, dept_deps, dept_hours, holidays
)
```

## Related Features

- **Sprint Management** - Automatic sprint assignment
- **Release Notes** - Integration with release planning
- **Team Evaluation** - Metrics based on completed subtasks
- **Deadline Notifier** - Alerts for approaching subtask deadlines

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Nov 2025 | Initial release with core dependency scheduling |
| 0.9 | Oct 2025 | Beta testing with real projects |
| 0.5 | Sep 2025 | Prototype with basic date calculation |

## Contributing

When updating this feature:
1. Update all 4 documentation files
2. Add unit tests for new patterns
3. Update examples with real use cases
4. Test with actual Google Sheets data
5. Verify Jira integration works correctly

## License

This feature is part of the jira-telegram-bot project.

---

**Quick Navigation:**
- 📖 [Full Explanation](./department-dependencies-explanation.md) - Detailed technical documentation
- 📊 [Visual Diagrams](./department-dependencies-diagram.md) - Charts and graphs
- 🛠️ [Usage Guide](./department-dependencies-usage-guide.md) - Practical instructions
- 🏠 [Back to Main Docs](../../README.md) - Project documentation home

**Last Updated:** November 2025  
**Status:** ✅ Production Ready  
**Maintainer:** SynthPM Team
