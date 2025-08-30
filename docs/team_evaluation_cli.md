# Team Evaluation CLI

The Team Evaluation CLI allows you to compute developer performance metrics for Jira sprint closures and write them to Google Sheets.

## Quick Start

```bash
# Basic usage with sprint ID
python scripts/run_team_evaluation.py \
    --sprint-id 123 \
    --project-keys "PARSCHAT" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --dry-run

# Using sprint name instead of ID
python scripts/run_team_evaluation.py \
    --sprint-name "Sprint 47" \
    --project-keys "PARSCHAT,PROJ2" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs"
```

## Prerequisites

1. **Environment Setup**: Create a `.env` file or set environment variables:
   ```env
   GOOGLE_SHEETS_CREDENTIALS_PATH=./parschat-684f8662ca98.json
   JIRA_SERVER=https://your-company.atlassian.net
   JIRA_USERNAME=your-email@company.com
   JIRA_API_TOKEN=your-jira-api-token
   DATABASE_URL=postgresql://user:pass@localhost/db
   ```

2. **Google Sheets API**: Ensure your credentials file has access to the target sheet.

3. **Jira Access**: Your API token must have permissions to read sprints, issues, and worklogs.

## Command-Line Options

### Required Arguments

- `--sprint-id SPRINT_ID` OR `--sprint-name SPRINT_NAME`: Identify the sprint to evaluate
- `--project-keys PROJECT_KEYS`: Comma-separated list of Jira project keys (e.g., "PROJ1,PROJ2")
- `--sheet-id SHEET_ID`: Google Sheet ID to write results to

### Optional Configuration

- `--tab-name TAB_NAME`: Target tab name (default: "Team Evaluation")
- `--weekly-hours HOURS`: Expected weekly work hours (default: 46)
- `--workdays DAYS`: Working days as comma-separated numbers (default: "6,0,1,2,3,4" for Sat-Thu)
- `--dept-inference STRATEGY`: Department detection strategy: component|label|user_config (default: component)
- `--expected-hours-mode MODE`: weekly|total (default: weekly)
- `--timezone TIMEZONE`: IANA timezone (default: Asia/Tehran)
- `--dry-run`: Compute metrics but don't write to Google Sheets
- `--verbose, -v`: Enable verbose logging

### Advanced Configuration

- `--score-weights JSON`: Score weighting configuration
  ```json
  {"deadline": 0.35, "worklog": 0.25, "high_priority": 0.20, "defects": 0.20}
  ```

- `--defect-thresholds JSON`: Defect penalty thresholds
  ```json
  {"support_per_story": 0.3, "tester_per_story": 0.4, "max_penalty": 60}
  ```

## Examples

### 1. Basic Sprint Evaluation

```bash
python scripts/run_team_evaluation.py \
    --sprint-id 123 \
    --project-keys "PARSCHAT" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --dry-run
```

### 2. Multi-Project Sprint

```bash
python scripts/run_team_evaluation.py \
    --sprint-name "Sprint 47" \
    --project-keys "PARSCHAT,BACKEND,FRONTEND" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --tab-name "Q4 Evaluation"
```

### 3. Custom Work Schedule (Mon-Fri, 40 hours)

```bash
python scripts/run_team_evaluation.py \
    --sprint-id 123 \
    --project-keys "PARSCHAT" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --weekly-hours 40 \
    --workdays "1,2,3,4,5" \
    --timezone "America/New_York"
```

### 4. Custom Scoring Weights

```bash
python scripts/run_team_evaluation.py \
    --sprint-id 123 \
    --project-keys "PARSCHAT" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --score-weights '{"deadline": 0.4, "worklog": 0.3, "high_priority": 0.2, "defects": 0.1}' \
    --defect-thresholds '{"support_per_story": 0.2, "tester_per_story": 0.3, "max_penalty": 50}'
```

### 5. Debugging Mode

```bash
python scripts/run_team_evaluation.py \
    --sprint-id 123 \
    --project-keys "PARSCHAT" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --verbose \
    --dry-run
```

## Output

The CLI computes 24 performance metrics for each developer and writes them to Google Sheets with Persian headers:

1. **توسعه دهنده** - Developer name
2. **دپارتمان** - Department(s)
3. **پروژه** - Project name
4. **اسپرینت** - Sprint name
5. **توسعه** - Development tasks count
6. **باگ** - Bug count
7. **پشتیبانی** - Support tasks count
8. **تسکهای اولویت بالا** - High priority tasks count
9. **زمان ثبت شده هفته** - Weekly logged hours
10. **زمان انتظاری هفته** - Expected weekly hours
... (and 14 more metrics)

## Error Handling

The CLI provides detailed error messages for common issues:

- **Configuration errors**: Missing environment variables, invalid JSON
- **Jira API errors**: Authentication issues, sprint not found
- **Google Sheets errors**: Permission issues, sheet not found
- **Validation errors**: Invalid arguments, missing data

Use `--verbose` for detailed debugging information.

## Integration with Webhook

This CLI functionality is also available as a webhook endpoint that automatically triggers when sprints are closed in Jira. The webhook uses the same logic but with settings from the application configuration.

## Dry Run Mode

Always test with `--dry-run` first to see what would be computed without writing to Google Sheets:

```bash
python scripts/run_team_evaluation.py \
    --sprint-id 123 \
    --project-keys "PARSCHAT" \
    --sheet-id "1-TLlnTLfK0qKU2XNr0TgFT96-mNzJoSYgLuLlnPNdJs" \
    --dry-run \
    --verbose
```

Remove `--dry-run` when you're ready to write the actual data.
