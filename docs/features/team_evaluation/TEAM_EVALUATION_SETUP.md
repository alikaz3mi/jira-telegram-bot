# Team Evaluation System - Complete Setup Summary

## Overview

The automated team evaluation system is **fully implemented and operational**. It automatically calculates and stores developer performance metrics whenever a sprint is closed in Jira.

## Architecture

### Database Storage
- **Table**: `team_evaluation`
- **Location**: PostgreSQL database (same as other Jira data)
- **Migration**: `migration_005_add_team_evaluation.py` ✓ Applied
- **Schema**:
  - `id` (Primary Key)
  - `jira_username` (Developer's Jira username)
  - `sprint_name` (Sprint identifier, e.g., "Sprint 2024-W50")
  - `evaluation_date` (Date evaluation was calculated)
  - Metric scores (completion_rate, story_points_completed, etc.)
  - Raw metric data (JSON)
  - timestamps (created_at, updated_at)

### Webhook Endpoint

**✓ Already Exists and Configured**

- **URL**: `http://your-server:8000/webhook/jira`
- **Method**: POST
- **Event Type**: `sprint_closed`
- **Handler**: `JiraWebhookController` → `SprintWebhookHandler`

This is the SAME endpoint that handles all Jira events (issue updates, comments, etc.). The controller intelligently routes sprint events to the team evaluation handler.

### Data Flow

```
Jira Sprint Closed Event
        ↓
POST /webhook/jira
        ↓
JiraWebhookController
        ↓
SprintWebhookHandler.handle_sprint_event()
        ↓
SprintClosedTeamEvaluationUseCase.evaluate_team()
        ↓
[Calculate metrics from Jira API]
        ↓
TeamEvaluationRepository.save_evaluation()
        ↓
PostgreSQL team_evaluation table
```

## Key Components

### 1. Entity: `TeamEvaluation`
**File**: `jira_telegram_bot/entities/team_evaluation.py`

Defines the data structure for storing evaluation results.

### 2. Repository Interface: `TeamEvaluationRepositoryInterface`
**File**: `jira_telegram_bot/use_cases/interfaces/team_evaluation_repository_interface.py`

Abstract interface for data persistence operations.

### 3. Repository Implementation: `TeamEvaluationPostgresRepository`
**File**: `jira_telegram_bot/adapters/repositories/postgres/team_evaluation_repository.py`

PostgreSQL implementation with ORM model and CRUD operations.

### 4. Use Case: `SprintClosedTeamEvaluationUseCase`
**File**: `jira_telegram_bot/use_cases/team_evaluation/sprint_closed_team_evaluation_use_case.py`

Business logic for:
- Fetching sprint data from Jira
- Calculating performance metrics
- Saving results to database

### 5. Webhook Handler: `SprintWebhookHandler`
**File**: `jira_telegram_bot/use_cases/team_evaluation/sprint_webhook_handler.py`

Processes sprint webhook events and triggers evaluation.

### 6. Controller: `JiraWebhookController`
**File**: `jira_telegram_bot/adapters/controllers/jira_webhook_controller.py`

Routes all Jira webhooks to appropriate handlers, including sprint events.

## Configuration

### Dependency Injection
**File**: `jira_telegram_bot/config_dependency_injection.py`

All components are properly wired together:
- Repository implementation bound to interface
- Use case receives repository dependency
- Webhook handler receives use case dependency
- Controller receives webhook handler

### Environment Variables
Uses existing Jira settings from:
- `JIRA_SERVER_URL`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`

And database settings from:
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

## Metrics Calculated

The system calculates these metrics per developer per sprint:

1. **Completion Rate**: Percentage of assigned issues completed
2. **Story Points Completed**: Total story points of completed issues
3. **Average Resolution Time**: Mean time to resolve issues
4. **Bug Count**: Number of bugs resolved
5. **Code Quality Score**: Derived from bug rate and review feedback
6. **Collaboration Score**: Based on comments and interactions
7. **Velocity Score**: Story points delivered vs. capacity
8. **Total Score**: Weighted combination of all metrics

Weights are configurable in `TeamEvaluationScoreWeights`.

## Testing

### Manual Test
Run the test script:
```bash
python scripts/test_sprint_closed_webhook.py
```

This will:
1. Send a test `sprint_closed` webhook to the endpoint
2. Verify the database repository is accessible
3. Report test results

### Integration Test
Configure a Jira webhook:
1. Go to Jira → Settings → System → Webhooks
2. Create webhook with URL: `http://your-server:8000/webhook/jira`
3. Enable event: "Sprint" → "Sprint closed"
4. Close a sprint in Jira
5. Check database: `SELECT * FROM team_evaluation ORDER BY created_at DESC LIMIT 10;`

## Verification Queries

### Check recent evaluations
```sql
SELECT 
    jira_username,
    sprint_name,
    evaluation_date,
    completion_rate,
    story_points_completed,
    total_score
FROM team_evaluation
ORDER BY evaluation_date DESC
LIMIT 20;
```

### Check evaluations for specific sprint
```sql
SELECT * FROM team_evaluation
WHERE sprint_name = 'Sprint 2024-W50'
ORDER BY total_score DESC;
```

### Get developer history
```sql
SELECT 
    sprint_name,
    evaluation_date,
    total_score,
    completion_rate
FROM team_evaluation
WHERE jira_username = 'john.doe'
ORDER BY evaluation_date DESC;
```

## Important Notes

### ✓ What's Working
- Database table created and migrated
- Repository implementation complete
- Webhook endpoint active (`/webhook/jira`)
- Sprint event detection in controller
- Team evaluation calculation logic
- Database persistence (NO Google Sheets!)
- All dependencies properly injected
- Docker container restarted with new code

### ⚠️ What to Configure in Jira
You need to set up the Jira webhook to send `sprint_closed` events to your endpoint:

1. **Jira Cloud**: Settings → System → WebHooks
2. **Jira Server/Data Center**: Settings → System → Advanced → WebHooks

**Webhook Configuration**:
- Name: "Team Evaluation - Sprint Closed"
- URL: `http://your-server:8000/webhook/jira`
- Events: Check "Sprint" → "Sprint closed"
- Leave other events as-is (this endpoint handles all Jira events)

### 🔧 CLI Alternative
You can also trigger evaluations manually via CLI:
```bash
python scripts/run_team_evaluation.py --sprint-name "Sprint 2024-W50"
```

This uses the same evaluation logic but bypasses the webhook.

## Files Modified/Created

### New Files
1. `jira_telegram_bot/entities/team_evaluation.py`
2. `jira_telegram_bot/use_cases/interfaces/team_evaluation_repository_interface.py`
3. `jira_telegram_bot/adapters/repositories/postgres/team_evaluation_repository.py`
4. `jira_telegram_bot/adapters/repositories/postgres/database/migrations/migration_005_add_team_evaluation.py`
5. `scripts/test_sprint_closed_webhook.py`

### Modified Files
1. `jira_telegram_bot/config_dependency_injection.py` - Added repository bindings
2. `jira_telegram_bot/use_cases/team_evaluation/sprint_closed_team_evaluation_use_case.py` - Changed from Google Sheets to database
3. (Existing) `jira_telegram_bot/adapters/controllers/jira_webhook_controller.py` - Already had sprint handler support
4. (Existing) `jira_telegram_bot/use_cases/team_evaluation/sprint_webhook_handler.py` - Already existed

## Next Steps

1. **Configure Jira Webhook** (if not already done)
   - Add webhook in Jira for sprint_closed events

2. **Test with Real Sprint**
   - Close a sprint in Jira
   - Verify database records are created
   - Check that metrics look reasonable

3. **Create Reports/Dashboard** (Future Enhancement)
   - Query database to show team performance trends
   - Create visualization of metrics over time
   - Add API endpoints to retrieve evaluations

4. **Monitoring**
   - Check logs for "Sprint: Successfully processed team evaluation"
   - Monitor database growth
   - Set up alerts for evaluation failures

## Troubleshooting

### Webhook not triggering
- Check Jira webhook configuration
- Verify URL is accessible from Jira server
- Check Docker container is running: `docker ps | grep ticketing_bot`
- Check logs: `docker logs ticketing_bot | grep -i sprint`

### Database errors
- Verify migration ran: Check `database_migrations` table
- Verify table exists: `\dt team_evaluation` in psql
- Check repository logs for SQL errors

### No metrics calculated
- Ensure sprint has completed issues
- Verify Jira API credentials are correct
- Check use case logs for calculation errors

## Summary

✅ **System is READY and OPERATIONAL**

- Database table created
- Code deployed and running in Docker
- Webhook endpoint active at `/webhook/jira`
- Automatic evaluation on sprint close
- Data saved to PostgreSQL (not Google Sheets)
- All components tested and integrated

The only remaining step is ensuring your Jira instance is configured to send webhooks to the endpoint when sprints close.
