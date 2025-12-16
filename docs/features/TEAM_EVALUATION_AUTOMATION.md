# Team Evaluation Automation

## Overview

The team evaluation system automatically calculates and stores developer metrics when sprints close in Jira. Scores are saved to the PostgreSQL database in the `team_evaluations` table.

## Architecture

### Database Schema

**Table: `team_evaluations`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PRIMARY KEY | Auto-incrementing ID |
| `sprint_id` | INTEGER | Jira sprint ID |
| `sprint_name` | VARCHAR | Sprint name |
| `jira_username` | VARCHAR | Developer's Jira username |
| `score` | FLOAT | Overall evaluation score (0-100) |
| `score_breakdown` | JSONB | Detailed score components |
| `metrics` | JSONB | Raw metrics data |
| `evaluated_at` | TIMESTAMP | When evaluation was calculated |
| `created_at` | TIMESTAMP | Record creation timestamp |

**Indexes:**
- `idx_team_evaluations_sprint` on (`sprint_id`)
- `idx_team_evaluations_user` on (`jira_username`)
- `idx_team_evaluations_sprint_user` on (`sprint_id`, `jira_username`)

### Components

#### 1. Entity Layer
- **`TeamEvaluation`** (`entities/team_evaluation.py`): Core domain model
- **`TeamEvaluationScoreWeights`**: Score calculation weights configuration

#### 2. Repository Layer
- **`TeamEvaluationRepositoryInterface`** (`use_cases/interfaces/`): Repository contract
- **`PostgresTeamEvaluationRepository`** (`adapters/repositories/postgres/`): PostgreSQL implementation

#### 3. Use Case Layer
- **`SprintClosedTeamEvaluationUseCase`** (`use_cases/team_evaluation/`): Evaluation calculation logic
- **`SprintWebhookHandler`** (`use_cases/team_evaluation/`): Sprint event orchestrator

#### 4. Framework Layer
- **`JiraWebhookController`** (`adapters/controllers/`): Routes webhook events
- **`MetricsWebhookEndpoint`** (`frameworks/api/endpoints/metrics/`): API endpoint

## How It Works

### Automatic Evaluation Flow

```
Jira Sprint Closed
       ↓
POST /api/v1/metrics/jira
       ↓
MetricsWebhookEndpoint
       ↓
JiraWebhookController.process_webhook()
       ↓
SprintWebhookHandler.handle_sprint_event()
       ↓
SprintClosedTeamEvaluationUseCase.execute()
       ↓
PostgresTeamEvaluationRepository.save()
       ↓
team_evaluations table
```

### Event Processing

1. **Webhook Reception**: Jira sends `sprint_closed` event to `/api/v1/metrics/jira`
2. **Event Routing**: `JiraWebhookController` detects sprint event and routes to `SprintWebhookHandler`
3. **Data Extraction**: Handler extracts sprint ID, name, and project keys
4. **Metric Calculation**: `SprintClosedTeamEvaluationUseCase` computes scores for each developer
5. **Database Storage**: Evaluations saved to `team_evaluations` table
6. **Background Processing**: Runs asynchronously to avoid blocking webhook response

## Webhook Configuration

### Jira Webhook Setup

Configure Jira to send webhooks for sprint events:

**URL:** `https://your-domain.com/api/v1/metrics/jira`

**Events to subscribe:**
- Sprint closed
- Sprint started (optional, for future features)
- Sprint updated (optional, for future features)

**Payload Example:**
```json
{
  "webhookEvent": "sprint_closed",
  "sprint": {
    "id": 123,
    "name": "Sprint 47",
    "state": "closed",
    "originBoardId": 1,
    "completeDate": "2025-12-14T10:00:00.000Z"
  }
}
```

## Score Calculation

### Metrics Tracked

1. **Task Completion**: Story points completed vs. committed
2. **Quality**: Bug count, code review feedback
3. **Velocity**: Story points per working day
4. **Timeliness**: On-time vs. late completions
5. **Collaboration**: Code reviews given, pair programming

### Score Weights

Default weights (configurable in `TeamEvaluationSettings`):

```python
{
    "completion_rate": 0.30,     # 30%
    "quality_score": 0.25,       # 25%
    "velocity": 0.20,            # 20%
    "timeliness": 0.15,          # 15%
    "collaboration": 0.10        # 10%
}
```

### Calculation Formula

```
Overall Score = Σ(metric_score × weight)
```

Where each metric_score is normalized to 0-100 scale.

## Usage

### Automatic (Production)

1. **Configure Jira webhook** (one-time setup)
2. **Evaluations run automatically** when sprints close
3. **Query results** from `team_evaluations` table

### Manual Execution (CLI)

For testing or historical data:

```bash
# Run evaluation for specific sprint
python scripts/run_team_evaluation.py \
  --sprint-id 123 \
  --project-keys PROJ1,PROJ2 \
  --sheet-id dummy_id \
  --dry-run

# Using sprint name
python scripts/run_team_evaluation.py \
  --sprint-name "Sprint 47" \
  --project-keys PARSCHAT \
  --sheet-id dummy_id
```

**Note:** The `--sheet-id` parameter is required by CLI but not used (legacy from Google Sheets integration).

## Database Queries

### Get latest evaluation for a developer

```sql
SELECT 
    sprint_name,
    score,
    score_breakdown,
    evaluated_at
FROM team_evaluations
WHERE jira_username = 'john.doe'
ORDER BY evaluated_at DESC
LIMIT 1;
```

### Get all evaluations for a sprint

```sql
SELECT 
    jira_username,
    score,
    score_breakdown->'completion_rate' as completion,
    score_breakdown->'quality_score' as quality,
    score_breakdown->'velocity' as velocity
FROM team_evaluations
WHERE sprint_id = 123
ORDER BY score DESC;
```

### Average score per developer (last 5 sprints)

```sql
SELECT 
    jira_username,
    AVG(score) as avg_score,
    COUNT(*) as sprint_count
FROM (
    SELECT DISTINCT ON (sprint_id, jira_username)
        jira_username,
        score,
        evaluated_at
    FROM team_evaluations
    ORDER BY sprint_id, jira_username, evaluated_at DESC
) recent
GROUP BY jira_username
ORDER BY avg_score DESC;
```

## Migration

The database table was created by migration `006_add_team_evaluation_table.py`:

```bash
# Run migration
python scripts/run_migrations.py
```

## Testing

### Test Webhook Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/metrics/jira \
  -H "Content-Type: application/json" \
  -d '{
    "webhookEvent": "sprint_closed",
    "sprint": {
      "id": 123,
      "name": "Test Sprint",
      "state": "closed"
    }
  }'
```

### Verify Data

```bash
# Connect to PostgreSQL
docker exec -it ticketing_bot_db psql -U jira_user -d jira_telegram_bot

# Query evaluations
SELECT sprint_name, jira_username, score, evaluated_at 
FROM team_evaluations 
ORDER BY evaluated_at DESC 
LIMIT 10;
```

## Configuration

### Environment Variables

Set in `.env` or Docker environment:

```env
# Database (already configured)
DATABASE_HOST=localhost
DATABASE_PORT=57235
DATABASE_NAME=jira_telegram_bot
DATABASE_USER=jira_user
DATABASE_PASSWORD=your_password

# Team Evaluation Settings
TEAM_EVALUATION_WEEKLY_HOURS=40
TEAM_EVALUATION_WORKDAYS=1,2,3,4,5
```

### Score Weights

Customize in `settings/team_evaluation_settings.py`:

```python
class TeamEvaluationSettings(BaseSettings):
    score_weights: TeamEvaluationScoreWeights = TeamEvaluationScoreWeights(
        completion_rate=0.30,
        quality_score=0.25,
        velocity=0.20,
        timeliness=0.15,
        collaboration=0.10
    )
```

## Troubleshooting

### No evaluations created

**Check:**
1. Jira webhook is configured and firing
2. Sprint event reaches `/api/v1/metrics/jira`
3. Logs show `SprintWebhookHandler` processing
4. Database connection is working

**Debug logs:**
```bash
docker logs -f ticketing_bot | grep -i "sprint\|evaluation"
```

### Scores seem incorrect

**Verify:**
1. Metrics data is available in Jira
2. Score weights sum to 1.0
3. Check `score_breakdown` JSONB field for component details
4. Review calculation logic in `SprintClosedTeamEvaluationUseCase`

### Webhook not firing

**Test manually:**
```bash
# Simulate sprint closed event
curl -X POST http://localhost:8000/api/v1/metrics/jira \
  -H "Content-Type: application/json" \
  -d @test_sprint_closed_payload.json
```

## Future Enhancements

- [ ] Real-time dashboard for team metrics
- [ ] Historical trend analysis
- [ ] Comparison across sprints/teams
- [ ] Automatic report generation
- [ ] Email notifications for low scores
- [ ] Integration with performance review systems
- [ ] ML-based anomaly detection
- [ ] Peer review feedback integration

## Related Documentation

- [Team Evaluation Use Case](../use_cases/team_evaluation/)
- [Database Migrations](../infrastructure/migrations.md)
- [Webhook Configuration](../infrastructure/webhooks.md)
- [API Documentation](http://localhost:8000/api/v1/docs)
