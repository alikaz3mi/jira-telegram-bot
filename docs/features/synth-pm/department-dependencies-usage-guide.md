# Department Dependencies - Usage Guide

## Quick Start

### Basic Setup in Google Sheets

Your Google Sheet should have these columns:

| Column Name | Example Value | Description |
|------------|---------------|-------------|
| وظیفه (Task Title) | User Authentication | Task name |
| Department Deps | UI/UX -> Frontend | Dependency chain |
| ETA(h) | 72 | Total hours estimate |
| AI | 24 | AI department hours |
| Backend | 0 | Backend hours (0 if not involved) |
| Frontend | 24 | Frontend hours |
| UI / UX | 24 | UI/UX hours |
| Deadline | 1404/08/26 | Persian date deadline |

### Dependency Syntax

**Preferred Format:**
```
Blocking Department blocks Blocked Department
```

**Alternative Format:**
```
Blocking Department -> Blocked Department
```

**Rules:**
- Use exact department names: `UI/UX`, `Frontend`, `Backend`, `AI`, `DevOps`
- Separate multiple dependencies with commas
- Direction is **Blocker blocks Blocked** (the blocker comes first)
- Both formats can be mixed in the same string

---

## Common Use Cases

### Case 1: Frontend Depends on Design

**Scenario:** Frontend team needs designs before starting development

**Setup:**
- Task Title: "Implement Dashboard UI"
- Department Deps: `UI/UX blocks Frontend`
- UI/UX Hours: 16
- Frontend Hours: 32
- Deadline: 1404/08/26 (17 Nov 2025)

**Result:**
```
UI/UX Subtask:
  Start: 10 Nov 2025
  End: 12 Nov 2025
  Assignee: Designer

Frontend Subtask:
  Start: 13 Nov 2025
  End: 17 Nov 2025
  Assignee: Frontend Developer
  Blocks: UI/UX -> Frontend
```

### Case 2: Backend API Before Frontend Integration

**Scenario:** Frontend needs backend API endpoints ready

**Setup:**
- Task Title: "User Profile API & UI"
- Department Deps: `Backend blocks Frontend`
- Backend Hours: 24
- Frontend Hours: 24
- Deadline: 1404/08/26

**Result:**
```
Backend Subtask:
  Start: 10 Nov
  End: 13 Nov

Frontend Subtask:
  Start: 14 Nov
  End: 17 Nov
```

### Case 3: Complete Design → Dev → AI Flow

**Scenario:** Design must be ready, then development, then AI integration

**Setup:**
- Task Title: "Smart Search Feature"
- Department Deps: `UI/UX blocks Frontend, Frontend blocks AI`
- UI/UX Hours: 16
- Frontend Hours: 24
- AI Hours: 16
- Deadline: 1404/08/30 (21 Nov 2025)

**Result:**
```
UI/UX:     10-12 Nov  ──┐
                        ├→ Frontend: 13-16 Nov ──→ AI: 19-21 Nov
                        │                           (skip Fri 17)
                        └→ (blocks Frontend)
```

### Case 4: Parallel Work with Convergence

**Scenario:** UI/UX and Backend work in parallel, then Frontend integrates both

**Setup:**
- Task Title: "Payment Gateway"
- Department Deps: `UI/UX blocks Frontend, Backend blocks Frontend`
- UI/UX Hours: 24
- Backend Hours: 32
- Frontend Hours: 24
- Deadline: 1404/08/30

**Result:**
```
UI/UX:    10-13 Nov  ──┐
Backend:  10-17 Nov  ──┴→ Frontend: 18-21 Nov
                         (waits for BOTH)
```

### Case 5: Independent Parallel Work

**Scenario:** Teams work independently (no dependencies)

**Setup:**
- Task Title: "Multi-component Feature"
- Department Deps: *(leave empty)*
- UI/UX Hours: 24
- Backend Hours: 24
- AI Hours: 24
- Deadline: 1404/08/26

**Result:**
```
All departments start together:
UI/UX:   10-13 Nov
Backend: 10-13 Nov
AI:      10-13 Nov

(All complete before deadline)
```

---

## Step-by-Step Examples

### Example A: Simple Two-Step Dependency

#### Google Sheet Entry:
```
Row 5:
┌──────────────────────┬──────────────────┬─────────┬───────┬────────┬──────────┬────────┐
│ Task Title           │ Department Deps  │ UI/UX   │ Front │ Backend│ Deadline │ ETA(h) │
├──────────────────────┼──────────────────┼─────────┼───────┼────────┼──────────┼────────┤
│ Login Page           │ UI/UX -> Frontend│   16    │  32   │   0    │1404/08/26│   48   │
└──────────────────────┴──────────────────┴─────────┴───────┴────────┴──────────┴────────┘
```

#### Processing Steps:

1. **Parse Dependencies:**
   ```python
   dept_deps = {"Frontend": ["UI/UX"]}
   ```

2. **Extract Hours:**
   ```python
   department_hours = {
       "UI/UX": 16,      # 2 working days
       "Frontend": 32    # 4 working days
   }
   ```

3. **Calculate Dates (backwards from 17 Nov):**
   ```
   Feature Deadline: 17 Nov
   
   Frontend (blocked):
     - Must end: 17 Nov
     - Duration: 4 days
     - Calculated: 13-17 Nov (skip Fri 14th: Sun-Mon-Wed-Thu)
   
   UI/UX (blocker):
     - Must end before Frontend starts: < 13 Nov
     - End: 12 Nov
     - Duration: 2 days
     - Calculated: 10-12 Nov
   ```

4. **Create Jira Subtasks:**
   ```
   Story: "Login Page" (SYNTH-123)
   
   Subtask 1: "Login Page - UI/UX"
     - Assignee: @designer
     - Story Points: 16
     - Start: 10 Nov
     - End: 12 Nov
   
   Subtask 2: "Login Page - Frontend"
     - Assignee: @frontend_dev
     - Story Points: 32
     - Start: 13 Nov
     - End: 17 Nov
     - Blocked by: Subtask 1
   ```

### Example B: Three-Department Complex Dependency

#### Google Sheet Entry:
```
Row 7:
┌──────────────────────────────────────┬──────────────────────────┬─────────┬───────┬────────┬──────┬──────────┬────────┐
│ Task Title                           │ Department Deps          │ UI/UX   │ Front │ Backend│ AI   │ Deadline │ ETA(h) │
├──────────────────────────────────────┼──────────────────────────┼─────────┼───────┼────────┼──────┼──────────┼────────┤
│ Smart Recommendation System          │ Backend -> AI, AI -> Front│   0    │  24   │   32   │  16  │1404/09/05│   72   │
└──────────────────────────────────────┴──────────────────────────┴─────────┴───────┴────────┴──────┴──────────┴────────┘
```

#### Processing Steps:

1. **Parse Dependencies:**
   ```python
   dept_deps = {
       "AI": ["Backend"],
       "Frontend": ["AI"]
   }
   ```

2. **Build Dependency Graph:**
   ```
   Backend → AI → Frontend
   ```

3. **Calculate Dates (backwards from 26 Nov):**
   ```
   Deadline: 26 Nov (Thursday)
   
   Frontend (end of chain):
     - End: 26 Nov
     - Duration: 24h = 3 days
     - Start: 23 Nov (Sun-Mon-Wed, skip Fri 24)
   
   AI (middle):
     - End before Frontend: < 23 Nov
     - End: 22 Nov
     - Duration: 16h = 2 days
     - Start: 20 Nov
   
   Backend (start of chain):
     - End before AI: < 20 Nov
     - End: 19 Nov
     - Duration: 32h = 4 days
     - Start: 15 Nov (skip Fri 17)
   ```

4. **Timeline View:**
   ```
   15-19 Nov: Backend Development
   20-22 Nov: AI Model Integration
   23-26 Nov: Frontend Implementation
   ```

---

## Google Sheets Column Reference

### Required Columns

| Persian Name | English Name | Format | Example |
|-------------|--------------|--------|---------|
| وظیفه | Task Title | Text | "User Dashboard" |
| وابستگی های دپارتمان | Department Deps | Text | "UI/UX -> Frontend" |
| ددلاین | Deadline | Persian Date | 1404/08/26 |
| ETA(h) | Total Hours | Number | 72 |

### Department Hour Columns

| Column Name | Description |
|------------|-------------|
| AI | Hours for AI department |
| Backend | Hours for Backend team |
| Front-end | Hours for Frontend team |
| UI / UX | Hours for Design team |
| DevOPS | Hours for DevOps team |

**Note:** If a department has 0 hours, it won't get a subtask.

---

## Dependency Patterns

### Pattern 1: Sequential (Waterfall)
```
Deps: A -> B, B -> C, C -> D

A ──→ B ──→ C ──→ D
```
**Use When:** Each phase must complete before next starts

### Pattern 2: Parallel to Single
```
Deps: A -> C, B -> C

A ──┐
B ──┴→ C
```
**Use When:** Multiple teams feed into integration team

### Pattern 3: Single to Parallel
```
Deps: A -> B, A -> C

     ┌→ B
A ──┤
     └→ C
```
**Use When:** Design/API ready, then parallel implementation

### Pattern 4: Diamond
```
Deps: A -> B, A -> C, B -> D, C -> D

     ┌→ B ──┐
A ──┤       ├→ D
     └→ C ──┘
```
**Use When:** Complex integration with parallel then convergence

### Pattern 5: Independent
```
Deps: (empty)

A
B
C
D
```
**Use When:** No dependencies, all work in parallel

---

## Working with Persian Dates

### Input Format
```
Persian (Jalali): 1404/08/26
Converts to Gregorian: 2025-11-17
```

### Date Handling
- System converts Persian → Gregorian automatically
- Calculations use Gregorian calendar
- Friday (جمعه) is excluded
- Holidays loaded from Jira configuration

### Example Conversion
```
Input:  1404/08/20 to 1404/08/27
Output: 2025-11-11 to 2025-11-18 (Gregorian)
Days:   8 calendar days = 6 working days (2 Fridays excluded)
```

---

## Troubleshooting

### Issue 1: "Dates Not Respecting Dependencies"

**Symptoms:**
- Frontend starts same day as UI/UX
- Subtasks overlap when they shouldn't

**Check:**
1. ✅ Department Deps column has correct format
2. ✅ Department names match exactly (case-sensitive)
3. ✅ Direction is Blocker blocks Blocked (blocker comes first)

**Example Fix:**
```
❌ Wrong: "Frontend blocks UI/UX"  (backwards)
✅ Right: "UI/UX blocks Frontend"

❌ Wrong: "UIUX blocks Frontend"   (space missing in UI/UX)
✅ Right: "UI/UX blocks Frontend"

❌ Wrong: "UI/UX block Frontend"   (missing 's' in blocks)
✅ Right: "UI/UX blocks Frontend"
```

### Issue 2: "Subtask Missing"

**Symptoms:**
- Expected subtask not created

**Check:**
1. ✅ Department has hours > 0
2. ✅ Assignee exists for that department
3. ✅ Component mapping configured

**Example:**
```
If Frontend Hours = 0, no Frontend subtask will be created
```

### Issue 3: "Wrong Start/End Dates"

**Symptoms:**
- Dates don't match expected timeline

**Check:**
1. ✅ Total ETA(h) matches sum of department hours
2. ✅ Deadline is realistic given hours
3. ✅ Holidays configured in Jira

**Calculation:**
```
Total Hours: 72h = 9 working days
With Fridays:  Need ~13 calendar days
Deadline must be at least 13 days from start
```

### Issue 4: "Circular Dependency Error"

**Symptoms:**
- Sync fails with dependency error

**Check:**
```
❌ Wrong: "A -> B, B -> A"  (circular)
✅ Right: "A -> B"         (one direction)
```

---

## Best Practices

### 1. Planning Dependencies
- ✅ Map dependencies before entering data
- ✅ Keep chains simple (max 3-4 levels)
- ✅ Document complex dependencies in task notes

### 2. Time Estimation
- ✅ Be realistic with hours (include buffer)
- ✅ Account for holidays and team availability
- ✅ Update estimates if scope changes

### 3. Team Communication
- ✅ Notify teams of dependencies
- ✅ Share calculated timelines with stakeholders
- ✅ Monitor blocking relationships in Jira

### 4. Maintenance
- ✅ Review dependencies during sprint planning
- ✅ Update Google Sheet when requirements change
- ✅ Resync after major changes

### 5. Quality Checks
```bash
# Verify sync results
python scripts/run_synth_pm.py sync

# Check created subtasks
# Go to Jira → Developer Board → Story → Subtasks
```

---

## Command Reference

### Run Sync
```bash
# Full synchronization
python scripts/run_synth_pm.py sync

# Sync specific feature (by row)
python scripts/run_synth_pm.py sync --row 5
```

### Debug Dependencies
```python
# In Python console
from jira_telegram_bot.entities.synth_pm.department_dependency_calculator import DepartmentDependencyCalculator

deps = DepartmentDependencyCalculator.parse_department_deps("UI/UX -> Frontend, Backend -> AI")
print(deps)
# Output: {'Frontend': ['UI/UX'], 'AI': ['Backend']}
```

### Test Date Calculations
```python
from datetime import datetime
from jira_telegram_bot.entities.synth_pm.department_dependency_calculator import DepartmentDependencyCalculator

deadline = datetime(2025, 11, 17)
dept_deps = {"Frontend": ["UI/UX"]}
dept_hours = {"UI/UX": 24, "Frontend": 32}
holidays = set()

dates = DepartmentDependencyCalculator.calculate_department_deadlines(
    deadline, dept_deps, dept_hours, holidays
)

for dept, dates_dict in dates.items():
    print(f"{dept}: {dates_dict['start'].date()} → {dates_dict['end'].date()}")
```

---

## FAQ

**Q: Can I have multiple teams work on the same task simultaneously?**  
A: Yes, just don't add them to Department Deps. They'll get parallel subtasks.

**Q: What if a dependency changes mid-sprint?**  
A: Update Google Sheet and re-run sync. Dates will recalculate.

**Q: How do I handle partial dependencies (e.g., 50% complete)?**  
A: Currently not supported. Consider breaking into smaller tasks.

**Q: Can I set custom start dates?**  
A: Start dates are calculated automatically. Set the feature start date via earliest department.

**Q: What's the maximum dependency chain length?**  
A: No hard limit, but keep it under 5 levels for clarity.

**Q: How do I represent "can start in parallel after 50% of blocker"?**  
A: Not supported yet. Use full blocking or independent tasks.

---

## Related Documentation

- [Department Dependencies Feature Overview](./department-dependencies-feature.md)
- [Department Dependencies Diagrams](./department-dependencies-diagram.md)
- [Department Dependencies Explanation](./department-dependencies-explanation.md)
- [SynthPM Settings](../../settings/synth_pm_settings.py)

---

**Last Updated:** November 2025  
**Maintainer:** SynthPM Team  
**Questions?** Check logs at `data/synth_developer_board_sync_status.json`
