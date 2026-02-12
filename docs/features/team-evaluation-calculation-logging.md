# Team Evaluation Calculation Logging

## Overview

The Team Evaluation Calculation Logging feature provides a comprehensive audit trail for all score calculations in the sprint-based team evaluation system. This feature enables Product Owners and team leads to provide detailed proof and transparency when developers ask about their evaluation scores.

## Purpose

When team members question their evaluation scores, this feature allows you to:
- Show exactly how each metric was calculated
- Provide detailed formulas and intermediate values
- Demonstrate the weight and contribution of each component
- Build trust through transparency in the scoring process

## Architecture

The feature follows Clean Architecture principles with clear separation of concerns:

```
entities/
  └── team_evaluation_calculation_log.py     # Data model

use_cases/
  ├── interfaces/
  │   └── team_evaluation_calculation_log_repository_interface.py  # Contract
  └── team_evaluation/
      ├── calculation_logger.py               # Helper for creating logs
      └── sprint_closed_team_evaluation_use_case.py  # Integration

adapters/
  └── repositories/
      └── postgres/
          ├── team_evaluation_calculation_log_repository.py  # Implementation
          └── database/
              └── migrations/
                  └── migration_006_add_team_evaluation_calculation_log.py
```

## Database Schema

### Table: `team_evaluation_calculation_log`

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PRIMARY KEY | Auto-incrementing ID |
| `sprint_id` | INTEGER | Sprint identifier |
| `sprint_name` | VARCHAR(255) | Sprint name (e.g., "MYPROJECT SPRINT 50") |
| `developer_name` | VARCHAR(255) | Developer name |
| `department` | VARCHAR(255) | Department (AI, DevOps, Backend, etc.) |
| `project` | VARCHAR(255) | Project code (MYPROJECT, PROJ6, PROJ3, etc.) |
| `calculation_type` | VARCHAR(50) | Type: metric, score_component, penalty, bonus, final_score |
| `metric_name` | VARCHAR(255) | Metric identifier (e.g., "development_task_count") |
| `metric_value` | FLOAT | Calculated value |
| `calculation_formula` | TEXT | Formula used for calculation |
| `calculation_details` | TEXT | Detailed explanation |
| `weight` | FLOAT | Weight in final score (nullable) |
| `contribution_to_total` | FLOAT | Contribution to total score (nullable) |
| `evaluation_id` | INTEGER | Link to team_evaluation table (nullable) |
| `timestamp` | TIMESTAMP | When calculation was performed |
| `created_at` | TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | Record update time |

### Indexes

- `idx_calc_log_sprint_developer` on `(sprint_id, developer_name)` - For querying all logs for a developer in a sprint
- `idx_calc_log_evaluation_id` on `(evaluation_id)` - For querying logs by evaluation record

## Calculation Types

### 1. Metric
Basic counting and aggregation metrics:
- `development_task_count` - Number of development tasks
- `bug_task_count` - Number of bug fixes
- `support_task_count` - Number of support tasks
- `high_priority_task_count` - Number of high-priority tasks
- `registered_hours_total` - Total hours logged
- `expected_hours_total` - Expected working hours
- `development_hours` - Hours on development
- `bug_hours` - Hours on bugs
- `support_hours` - Hours on support

### 2. Score Component
Individual score calculations with weights:
- `deadline_score` - Deadline compliance score (0-100)
- `worklog_score` - Time logging completeness score (0-100)
- `high_priority_score` - High-priority task completion score (0-100)
- `defect_score` - Code quality/defect score (0-100)

### 3. Penalty
Score deductions:
- Deadline penalties
- Quality penalties

### 4. Bonus
Score additions:
- Early delivery bonuses
- Quality bonuses

### 5. Final Score
Composite calculation:
- `quality_score_total` - Final weighted score

## Usage Examples

### Example 1: Querying Logs for a Developer

To see all calculation details for a developer in a specific sprint:

```python
from jira_telegram_bot.adapters.repositories.postgres.team_evaluation_calculation_log_repository import (
    PostgreSQLTeamEvaluationCalculationLogRepository
)

# Get logs
logs = repo.get_logs_by_sprint_and_developer(
    sprint_id=123,
    developer_name="کاظمی"
)

# Display to developer
for log in logs:
    print(f"{log.metric_name}: {log.metric_value}")
    print(f"Formula: {log.calculation_formula}")
    print(f"Details: {log.calculation_details}")
    if log.weight:
        print(f"Weight: {log.weight}, Contribution: {log.contribution_to_total}")
    print("---")
```

### Example 2: Sample Output for a Developer

When a developer asks "Why is my score 73.5?", you can show:

```
=== Task Classification ===
development_task_count: 8
Formula: COUNT(issues WHERE type='Story/Task')
Details: Counted all Story and Task issues completed in sprint

bug_task_count: 2
Formula: COUNT(issues WHERE type='Bug')
Details: Counted all Bug issues completed in sprint

=== Score Components ===
deadline_score: 85.5
Formula: MAX(0, 100 - (avg_delay_days * penalty_per_day))
Details: Average delay: 2.3 days, Penalty rate: 6.3 per day, Tasks: 8, Penalty: 14.5
Weight: 0.35
Contribution: 29.93

worklog_score: 90.91
Formula: (registered_hours / expected_hours) * 100
Details: Registered: 40.0h, Expected: 44.0h
Weight: 0.25
Contribution: 22.73

high_priority_score: 75.0
Formula: (completed_required / total_required) * 100
Details: Completed: 6, Required: 8
Weight: 0.20
Contribution: 15.00

defect_score: 80.0
Formula: Based on support_bug_ratio and tester_bug_ratio vs thresholds
Details: Support bugs per story: 0.2 (threshold: 0.3), Tester bugs: 0.15 (threshold: 0.2)
Weight: 0.20
Contribution: 16.00

=== Final Score ===
quality_score_total: 73.5
Formula: composite_score - penalties + bonuses
Details: Composite: 83.66, Penalties: 5.0, Bonuses: 0.0
```

## Database Migration

### Applying the Migration

```bash
# Run migration script
python scripts/run_migrations.py
```

The migration creates:
1. The `team_evaluation_calculation_log` table
2. Required indexes for efficient querying
3. Automatic timestamp columns

### Rolling Back

```bash
# If needed, rollback removes the table
# (Migration system supports down() method)
```

## Integration with Team Evaluation

The calculation logging is integrated into `SprintClosedTeamEvaluationUseCase`:

```python
# Logs are automatically created during evaluation
await use_case.execute(
    sprint_id=123,
    project="MYPROJECT",
    dry_run=False
)

# Logs include:
# - Task classification metrics (4 logs)
# - Time tracking metrics (5 logs)
# - Deadline score calculation (1 log)
# - Worklog score calculation (1 log)
# - High priority score calculation (1 log)
# - Defect score calculation (1 log)
# - Final score calculation (1 log)
# Total: ~14 logs per developer per sprint
```

## Configuration

### Dry Run Mode

When `dry_run=True`, calculation logs are **not** saved to the database:

```python
# No logs saved
await use_case.execute(sprint_id=123, dry_run=True)

# Logs saved
await use_case.execute(sprint_id=123, dry_run=False)
```

### Score Weights

Weights are configurable in `TeamEvaluationSettings`:

```python
score_weights:
  deadline: 0.35      # 35% of final score
  worklog: 0.25       # 25% of final score
  high_priority: 0.20 # 20% of final score
  defects: 0.20       # 20% of final score
```

## Testing

Comprehensive test coverage (27 tests, all passing):

### Unit Tests
- **Entity Tests** (5 tests): Data structure validation
- **Repository Tests** (8 tests): Database operations
- **Logger Tests** (9 tests): Log creation logic

### Integration Tests (5 tests)
- End-to-end logging flow
- Dry run behavior
- Error handling
- Helper methods

Run tests:
```bash
pytest tests/unit_tests/entities/test_team_evaluation_calculation_log.py -v
pytest tests/unit_tests/adapters/repositories/test_team_evaluation_calculation_log_repository.py -v
pytest tests/unit_tests/use_cases/team_evaluation/test_calculation_logger.py -v
pytest tests/integration/test_calculation_logging_integration.py -v
```

## API Reference

### CalculationLogger Helper

Static methods for creating standardized log entries:

```python
from jira_telegram_bot.use_cases.team_evaluation.calculation_logger import CalculationLogger

# Task classification (returns 4 logs)
logs = CalculationLogger.log_task_classification(
    sprint_id=123,
    sprint_name="MYPROJECT SPRINT 50",
    developer_name="کاظمی",
    department="DevOps",
    project="MYPROJECT",
    dev_count=8,
    bug_count=2,
    support_count=1,
    high_priority_count=4
)

# Time metrics (returns 5 logs)
logs = CalculationLogger.log_time_metrics(...)

# Score components (returns 1 log each)
log = CalculationLogger.log_deadline_score(...)
log = CalculationLogger.log_worklog_score(...)
log = CalculationLogger.log_high_priority_score(...)
log = CalculationLogger.log_defect_score(...)

# Final score (returns 1 log)
log = CalculationLogger.log_final_score(...)
```

### Repository Interface

```python
from jira_telegram_bot.use_cases.interfaces.team_evaluation_calculation_log_repository_interface import (
    TeamEvaluationCalculationLogRepositoryInterface
)

# Save single log
repo.save_log(log)

# Save multiple logs efficiently
repo.save_logs_batch(logs)

# Query logs
logs = repo.get_logs_by_sprint_and_developer(sprint_id=123, developer_name="کاظمی")
logs = repo.get_logs_by_evaluation_id(evaluation_id=456)
```

## Benefits

1. **Transparency**: Developers can see exactly how their scores are calculated
2. **Accountability**: Product Owners have proof for scoring decisions
3. **Debugging**: Easy to identify calculation issues or anomalies
4. **Historical Analysis**: Track calculation patterns over time
5. **Trust Building**: Objective, documented scoring process

## Performance Considerations

- **Batch Saving**: Logs are saved in batches for efficiency (~14 logs per developer)
- **Indexed Queries**: Composite indexes enable fast lookups by sprint/developer
- **Asynchronous Operations**: Non-blocking database operations
- **Dry Run Support**: Skip logging during testing/preview

## Error Handling

The logging system is designed to be non-intrusive:

- **Errors Don't Break Evaluation**: If logging fails, evaluation continues
- **Transaction Rollback**: Failed saves are rolled back to maintain consistency
- **Logging**: Errors are logged for monitoring without affecting user experience

```python
try:
    await calculation_log_repo.save_logs_batch(logs)
except Exception as e:
    LOGGER.error(f"Failed to save calculation logs: {e}")
    # Evaluation continues normally
```

## Future Enhancements

Potential improvements:
1. **Web UI**: Dashboard to visualize calculation breakdowns
2. **Comparison Tool**: Compare scores across sprints
3. **Export**: Generate PDF reports with calculation details
4. **Analytics**: Identify trends in scoring patterns
5. **Alerts**: Notify when unusual calculation patterns detected

## Related Documentation

- [Team Evaluation Overview](./team-evaluation.md)
- [Sprint Closed Webhook](./sprint-closed-webhook.md)
- [Database Migrations](../infrastructure/database-migrations.md)
- [Clean Architecture Guide](../infrastructure/clean-architecture.md)

## Troubleshooting

### Issue: No logs appearing for a sprint

**Solution**: Check if dry_run mode was enabled:
```python
# Verify settings
print(use_case.settings.dry_run)  # Should be False
```

### Issue: Missing logs for some developers

**Solution**: Verify the calculation_details dictionary is populated:
```python
# Check that _compute_developer_evaluation populates calculation_details
# and _save_calculation_logs_for_evaluation is called
```

### Issue: Query performance slow

**Solution**: Verify indexes exist:
```sql
-- Check indexes
\d team_evaluation_calculation_log

-- Should show:
-- idx_calc_log_sprint_developer
-- idx_calc_log_evaluation_id
```

## Maintenance

### Archiving Old Logs

Consider archiving logs older than 1 year:

```sql
-- Archive logs from 2023
CREATE TABLE team_evaluation_calculation_log_archive_2023 
AS SELECT * FROM team_evaluation_calculation_log 
WHERE EXTRACT(YEAR FROM created_at) = 2023;

-- Delete archived logs
DELETE FROM team_evaluation_calculation_log 
WHERE EXTRACT(YEAR FROM created_at) = 2023;
```

### Monitoring

Track log volume and query performance:

```sql
-- Log count by sprint
SELECT sprint_id, sprint_name, COUNT(*) as log_count
FROM team_evaluation_calculation_log
GROUP BY sprint_id, sprint_name
ORDER BY sprint_id DESC;

-- Average logs per developer per sprint
SELECT AVG(log_count) as avg_logs_per_dev
FROM (
    SELECT sprint_id, developer_name, COUNT(*) as log_count
    FROM team_evaluation_calculation_log
    GROUP BY sprint_id, developer_name
) subquery;
```

## Version History

- **v1.0** (December 2025): Initial implementation
  - Entity, repository, and migration created
  - Integration with SprintClosedTeamEvaluationUseCase
  - 27 tests with 100% pass rate
  - Support for 5 calculation types and 14+ metrics
