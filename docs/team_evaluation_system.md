# Team Evaluation System

## Overview

The Team Evaluation system automatically computes per-developer performance metrics when a Jira sprint is closed and writes them to a Google Sheets document. This provides comprehensive insights into team productivity, quality, and deadline adherence.

## Features

### Automated Metrics Calculation
- **Issue Classification**: Automatically categorizes issues as Development, Bug, or Support
- **Department Detection**: Infers developer departments from issue components, labels, or user config
- **Worklog Analysis**: Tracks time spent by issue type and calculates expected vs. actual hours
- **Quality Scoring**: Computes composite quality scores based on multiple factors
- **Deadline Tracking**: Monitors delivery performance against due dates

### Comprehensive Reporting
- **Persian Headers**: Google Sheets with Farsi column headers for local teams
- **Upsert Logic**: Updates existing rows or inserts new ones based on developer/project/sprint
- **Real-time Updates**: Triggered automatically when sprints are closed via webhook

## Architecture

### Core Components

1. **Entities** (`entities/team_evaluation.py`)
   - `TeamEvaluationRow`: Main data structure for sheet rows
   - `SprintClosedEvent`: Event model for sprint closure
   - `IssueSnapshot`: Minimal issue representation
   - `WorklogSlice`: Worklog entry model
   - `ChangeLogEvent`: Status change tracking

2. **Services** (`use_cases/team_evaluation/services/`)
   - `ClassificationService`: Issue type and department classification
   - `CalendarService`: Working hours and holiday calculations
   - `DeadlineService`: Deadline performance analysis
   - `DefectService`: Bug and defect rate calculations
   - `ScoreService`: Composite quality score computation

3. **Use Cases** (`use_cases/team_evaluation/`)
   - `SprintClosedTeamEvaluationUseCase`: Main business logic
   - `SprintWebhookHandler`: Webhook event processing

4. **Adapters**
   - `TeamEvaluationGoogleSheetGateway`: Google Sheets integration
   - `JsonCalendarRepository`: Calendar data storage
   - `JsonLeaveRepository`: Leave data management (stub)

## Configuration

### Environment Variables

```bash
# Required: Google Sheet ID
TEAM_EVALUATION_SHEET_ID=your_google_sheet_id_here

# Optional: Customize behavior
TEAM_EVALUATION_TAB_NAME=Team Evaluation
TEAM_EVALUATION_WEEKLY_HOURS=46.0
TEAM_EVALUATION_EXPECTED_HOURS_MODE=weekly
TEAM_EVALUATION_DEPT_INFERENCE=component
TEAM_EVALUATION_TIMEZONE=Asia/Tehran
TEAM_EVALUATION_DRY_RUN=false

# Score weights (must sum to 1.0)
TEAM_EVALUATION_SCORE_WEIGHTS__DEADLINE=0.35
TEAM_EVALUATION_SCORE_WEIGHTS__WORKLOG=0.25
TEAM_EVALUATION_SCORE_WEIGHTS__HIGH_PRIORITY=0.20
TEAM_EVALUATION_SCORE_WEIGHTS__DEFECTS=0.20
```

### Calendar Data

Create calendar files in `data/storage/YYYY.json` format:

```json
{
  "year": 2024,
  "months": {
    "1": {
      "month": 1,
      "name": "فروردین",
      "total_days": 31,
      "working_days": 22,
      "days": {
        "1": {
          "is_holiday": true,
          "description": "نوروز"
        }
      }
    }
  }
}
```

## Google Sheets Output

The system writes data to Google Sheets with the following columns (in Farsi):

| Column | Description | Formula/Logic |
|--------|-------------|---------------|
| توسعه دهنده | Developer Name | Jira assignee |
| دپارتمان | Department | From components/labels/config |
| پروژه | Project | Jira project key |
| اسپرینت | Sprint | Sprint name |
| توسعه | Development Count | Tasks/Improvements assigned |
| باگ | Bug Count | Bug issues assigned |
| پشتیبانی | Support Count | Support-labeled issues |
| تسکهای اولویت بالا | High Priority Count | Highest priority issues |
| زمان ثبت شده هفته | Registered Hours Week | Sum of logged hours |
| زمان انتظاری هفته | Expected Hours Week | Working days × daily hours |
| زمان باگ | Bug Hours | Hours logged on bug issues |
| زمان توسعه | Development Hours | Hours logged on dev issues |
| زمان پشتیبانی | Support Hours | Hours logged on support |
| میانگین ددلاین دلیوری | Avg Deadline Delivery | Average hours early/late |
| بازگشت از مرور به بک لاگ | Review Back Count | Review→Backlog transitions |
| تسکهای اولویت بالا تکمیل شده | High Priority Completed | Done high priority issues |
| میانگین باگهای پشتیبانی | Avg Support Bugs/Story | Support bugs per story |
| میانگین باگهای تستر | Avg Tester Bugs/Story | Tester bugs per story |
| توسعه تحویل داده شده | Development Delivered | Done development issues |
| باگ تحویل داده شده | Bug Delivered | Done bug issues |
| پشتیبانی تحویل داده شده | Support Delivered | Done support issues |
| درصد حسن انجام کار | Quality Score | Composite 0-100 score |

## Quality Score Calculation

The composite quality score (درصد حسن انجام کار) combines four weighted factors:

1. **Deadline Performance (35%)**: Penalty for late deliveries
2. **Worklog Compliance (25%)**: Ratio of logged vs. expected hours
3. **High Priority Completion (20%)**: Success rate on critical tasks
4. **Defect Rate (20%)**: Penalty for bugs introduced

Formula:
```
Score = (0.35 × DeadlineScore) + (0.25 × WorklogScore) + 
        (0.20 × HighPriorityScore) + (0.20 × DefectScore)
```

## Webhook Integration

The system automatically processes sprint closure events when received via Jira webhooks:

1. **Event Detection**: Identifies `sprint_closed` webhook events
2. **Data Collection**: Fetches sprint issues, worklogs, and changelogs
3. **Computation**: Calculates metrics per developer per project
4. **Sheet Update**: Upserts data to Google Sheets using (developer, project, sprint) as unique key

## Usage

### Manual Testing

```bash
# Test the system with a specific sprint
python scripts/test_team_evaluation.py
```

### Webhook Setup

Configure Jira to send sprint events to your webhook endpoint:
- Event: Sprint closed
- URL: `https://your-domain/api/jira/webhook`

### Monitoring

Check logs for processing status:
```bash
tail -f logs.log | grep "team_evaluation\|sprint_closed"
```

## Customization

### Issue Classification

Modify `ClassificationService` to adjust how issues are categorized:
- Development: Task, Sub-task, Improvement
- Bug: Bug issue type
- Support: Issues with "Support" label or in "پشتیبانی" epic

### Department Detection

Choose detection strategy via `TEAM_EVALUATION_DEPT_INFERENCE`:
- `component`: Use Jira component names
- `label`: Extract from issue labels
- `user_config`: Get from user configuration

### Score Weights

Adjust the relative importance of different quality factors via environment variables.

## Troubleshooting

### Common Issues

1. **No data in sheets**: Check Google Sheets permissions and `TEAM_EVALUATION_SHEET_ID`
2. **Missing sprint data**: Verify webhook configuration and sprint ID format
3. **Incorrect departments**: Review department inference strategy
4. **Calendar errors**: Ensure calendar JSON files exist for relevant years

### Debug Mode

Enable dry run mode for testing:
```bash
TEAM_EVALUATION_DRY_RUN=true
```

This will log what would be written without actually updating sheets.

### Logs

Monitor these log patterns:
- `Processing sprint closed event`: Event received
- `Found X issues in sprint`: Data collection
- `Successfully processed X evaluation rows`: Completion
- `DRY RUN: Would write X rows`: Dry run mode
