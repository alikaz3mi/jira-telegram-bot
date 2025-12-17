# Manager Evaluation System - Implementation Summary

## Overview

The Manager Evaluation system has been fully implemented to support:
- **Multiple managers** evaluating each developer
- **Two-table architecture** for clean data separation
- **Complete integration** with existing team evaluation flow
- **30% manager score** combined with 70% system score for final evaluation

---

## Database Schema

### 1. `manager_developer_assignments` Table
Tracks which managers are authorized to evaluate which developers.

```sql
CREATE TABLE manager_developer_assignments (
    id SERIAL PRIMARY KEY,
    manager_name VARCHAR(255) NOT NULL,
    developer_name VARCHAR(255) NOT NULL,
    department VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(manager_name, developer_name)
);
```

**Indexes:**
- `idx_manager_assignments_manager` on `manager_name` (WHERE is_active = TRUE)
- `idx_manager_assignments_developer` on `developer_name` (WHERE is_active = TRUE)

### 2. `manager_evaluations` Table
Stores individual manager evaluations for developers.

```sql
CREATE TABLE manager_evaluations (
    id SERIAL PRIMARY KEY,
    sprint_id BIGINT NOT NULL,
    developer_name VARCHAR(255) NOT NULL,
    manager_name VARCHAR(255) NOT NULL,
    evaluation_month VARCHAR(7) NOT NULL,  -- Format: YYYY-MM
    collaboration_score INTEGER CHECK (collaboration_score >= 0 AND collaboration_score <= 100),
    alignment_score INTEGER CHECK (alignment_score >= 0 AND alignment_score <= 100),
    total_manager_score INTEGER CHECK (total_manager_score >= 0 AND total_manager_score <= 100),
    comments TEXT,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sprint_id, developer_name, manager_name)
);
```

**Indexes:**
- `idx_manager_evaluations_sprint_dev` on `(sprint_id, developer_name)`
- `idx_manager_evaluations_month` on `evaluation_month`
- `idx_manager_evaluations_manager` on `manager_name`

---

## Score Calculation

### Manager Score Components (30% of Final Score)

1. **Collaboration Score (15%)**: Cooperation with tech lead and delivery commitment
2. **Alignment Score (15%)**: Alignment with company strategic goals

**Formula:**
```
total_manager_score = (collaboration_score * 0.5) + (alignment_score * 0.5)
```

### Final Score Integration

When a sprint is evaluated:
```
system_score = 70% weight  (deadline + worklog + priority + quality)
manager_score = 30% weight  (average of all manager evaluations)
final_score = (system_score * 0.70) + (manager_score * 0.30)
```

**Multiple Manager Support:**
- If 3 managers evaluate the same developer, their scores are averaged
- Example: Manager A=85, Manager B=90, Manager C=80 → Average=85

---

## Implementation Files

### Entities
- **`jira_telegram_bot/entities/manager_evaluation.py`**
  - `ManagerDeveloperAssignment`: Assignment of manager to developer
  - `ManagerEvaluation`: Individual evaluation record
  - `DeveloperPerformanceData`: Data shown to managers for evaluation

### Repository
- **`jira_telegram_bot/adapters/repositories/postgres/manager_evaluation_repository.py`**
  - `assign_manager_to_developer()`: Create assignment
  - `get_developers_for_manager()`: Get assigned developers
  - `save_evaluation()`: Save/update evaluation
  - `get_average_manager_score()`: Calculate average for final score
  - `get_evaluations_for_developer()`: Get all evaluations for a developer

### Use Cases
- **`jira_telegram_bot/use_cases/team_evaluation/get_developer_performance_for_evaluation.py`**
  - Shows performance data + stories/features to managers
  - Helps managers make informed evaluations
  
- **`jira_telegram_bot/use_cases/team_evaluation/submit_manager_evaluation.py`**
  - Validates manager authorization
  - Calculates total manager score
  - Saves evaluation

### Integration
- **`jira_telegram_bot/use_cases/team_evaluation/sprint_closed_team_evaluation_use_case.py`**
  - Updated to fetch manager scores
  - Calculates final_score = (system * 0.70) + (manager * 0.30)
  - Populates `TeamEvaluationRow` with all scores

### Database
- **Migration 008**: `migration_008_add_manager_evaluation_tables.py`
  - Creates both tables
  - Creates all indexes
  - Applied successfully ✅

---

## Usage Examples

### 1. Assign Manager to Developers

```python
from jira_telegram_bot.adapters.repositories.postgres.manager_evaluation_repository import ManagerEvaluationRepository

manager_repo = ManagerEvaluationRepository(session)

# Assign a manager to evaluate developers
manager_repo.assign_manager_to_developer(
    manager_name="علی کاظمی",
    developer_name="محمد موسوی",
    department="AI"
)
```

### 2. Submit Manager Evaluation

```python
from jira_telegram_bot.use_cases.team_evaluation.submit_manager_evaluation import SubmitManagerEvaluation
from jira_telegram_bot.entities.manager_evaluation import ManagerEvaluation

submit_use_case = SubmitManagerEvaluation(manager_repo)

evaluation = submit_use_case.execute(
    sprint_id=98649059,
    developer_name="محمد موسوی",
    manager_name="علی کاظمی",
    evaluation_month="2025-12",
    collaboration_score=85,
    alignment_score=90,
    comments="عملکرد عالی در همکاری با تیم"
)
```

### 3. Get Performance Data for Evaluation

```python
from jira_telegram_bot.use_cases.team_evaluation.get_developer_performance_for_evaluation import GetDeveloperPerformanceForEvaluation

get_performance_use_case = GetDeveloperPerformanceForEvaluation(
    db_connection, task_manager_repo, manager_repo
)

performance_data = get_performance_use_case.execute(
    sprint_id=98649059,
    developer_name="محمد موسوی"
)

print(f"System Score: {performance_data.system_score}")
print(f"Stories: {performance_data.stories_worked_on}")
print(f"Features: {performance_data.features_delivered}")
```

### 4. Bulk Submit Evaluations

```python
evaluations = [
    {
        "sprint_id": 98649059,
        "developer_name": "محمد موسوی",
        "evaluation_month": "2025-12",
        "collaboration_score": 85,
        "alignment_score": 90,
        "comments": "عملکرد عالی"
    },
    {
        "sprint_id": 98649059,
        "developer_name": "حسین آدابی",
        "evaluation_month": "2025-12",
        "collaboration_score": 75,
        "alignment_score": 80,
    }
]

results = submit_use_case.bulk_submit_evaluations(
    evaluations=evaluations,
    manager_name="علی کاظمی"
)
```

---

## Next Steps (For Admin Panel)

### Required FastAPI Endpoints

1. **GET `/api/manager-evaluation/developers`**
   - Returns list of developers assigned to the manager
   - Query params: `manager_name`, `month`

2. **GET `/api/manager-evaluation/performance/{developer_name}`**
   - Returns developer performance data for a specific sprint
   - Shows system scores, stories, features

3. **POST `/api/manager-evaluation/submit`**
   - Submit evaluation for a developer
   - Body: `{sprint_id, developer_name, collaboration_score, alignment_score, comments}`

4. **GET `/api/manager-evaluation/my-evaluations`**
   - Returns all evaluations submitted by the manager
   - Query params: `manager_name`, `month`

5. **POST `/api/manager-evaluation/assign`**
   - Admin endpoint to assign managers to developers
   - Body: `{manager_name, developer_name, department}`

### Admin Panel Features

1. **Manager Dashboard**
   - List of assigned developers
   - Sprint selector
   - Evaluation status (pending/completed)

2. **Evaluation Form**
   - Developer name + sprint info
   - Performance metrics display (system scores)
   - Stories/features list
   - Collaboration score slider (0-100)
   - Alignment score slider (0-100)
   - Comments textarea
   - Submit button

3. **History View**
   - Past evaluations by the manager
   - Filter by month, developer
   - Edit capability

---

## Data Model

```
TeamEvaluation (team_evaluation table)
├── system_score (70% weight)
│   ├── deadline_score (25%)
│   ├── worklog_score (20%)
│   ├── priority_score (40%)
│   └── quality_score (15%)
├── manager_evaluation_score (30% weight)
│   └── AVG(all manager evaluations for this sprint)
│       ├── Manager A: collaboration + alignment
│       ├── Manager B: collaboration + alignment
│       └── Manager C: collaboration + alignment
└── final_score = (system * 0.70) + (manager * 0.30)
```

---

## Testing

To test the implementation:

```python
# 1. Create assignment
manager_repo.assign_manager_to_developer("manager1", "dev1", "AI")

# 2. Submit evaluation
evaluation = ManagerEvaluation(
    sprint_id=123,
    developer_name="dev1",
    manager_name="manager1",
    evaluation_month="2025-12",
    collaboration_score=85,
    alignment_score=90,
    total_manager_score=87
)
manager_repo.save_evaluation(evaluation)

# 3. Run team evaluation for sprint 123
# The final_score will now include manager evaluation (30%)

# 4. Verify in database
avg_score = manager_repo.get_average_manager_score(123, "dev1")
print(f"Average manager score: {avg_score}")  # Should be 87 if only one manager
```

---

## Migration Status

✅ Migration 008 applied successfully
- Tables created: `manager_developer_assignments`, `manager_evaluations`
- All indexes created
- Ready for use

---

## Configuration

The manager evaluation repository is registered in the DI container:

```python
container[ManagerEvaluationRepository] = Singleton(
    lambda c: ManagerEvaluationRepository(
        session=c[DatabaseConnectionInterface].get_session()
    ),
)
```

It's injected into `SprintClosedTeamEvaluationUseCase` for automatic score aggregation.

---

## Benefits

1. **Multi-Manager Support**: Multiple managers can evaluate the same developer
2. **Historical Tracking**: All evaluations are stored with timestamps
3. **Fair Scoring**: Averages multiple manager opinions
4. **Transparency**: Managers see actual performance metrics when evaluating
5. **Flexibility**: Can deactivate assignments without deleting data
6. **Audit Trail**: Tracks who evaluated whom and when

---

## Future Enhancements

- [ ] Add manager weights (some managers' opinions count more)
- [ ] Add approval workflow (tech lead approval)
- [ ] Add notifications when evaluation is pending
- [ ] Add analytics on manager scoring patterns
- [ ] Add bulk import/export for evaluations
