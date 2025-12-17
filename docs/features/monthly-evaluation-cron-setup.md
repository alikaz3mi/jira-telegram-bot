# Cron Job Examples for Monthly Evaluation Creation

## Overview

These cron jobs automatically create monthly evaluation records at the end of each Jalali month.

## Setup

### 1. Install the Cron Jobs

Add these entries to your crontab:

```bash
# Edit crontab
crontab -e

# Add one of the following schedules
```

### 2. Cron Schedule Options

#### Option A: Run on the 29th of Every Month (Recommended)
```cron
# At 23:00 on the 29th of every month
0 23 29 * * cd /home/alikazemi/project/jira-telegram-bot && /home/alikazemi/miniconda3/bin/python scripts/run_monthly_evaluation_creation.py >> /var/log/monthly_evaluation_creation.log 2>&1
```

#### Option B: Run on Specific Jalali Month Ends
Since Jalali and Gregorian calendars don't align perfectly, you can schedule for specific Gregorian dates that correspond to Jalali month ends:

```cron
# For months with 30 days - runs on approximate Jalali month end dates
0 23 20 3,6,9,12 * cd /home/alikazemi/project/jira-telegram-bot && /home/alikazemi/miniconda3/bin/python scripts/run_monthly_evaluation_creation.py
0 23 21 1,4,7,10 * cd /home/alikazemi/project/jira-telegram-bot && /home/alikazemi/miniconda3/bin/python scripts/run_monthly_evaluation_creation.py
0 23 19 2,5,8,11 * cd /home/alikazemi/project/jira-telegram-bot && /home/alikazemi/miniconda3/bin/python scripts/run_monthly_evaluation_creation.py
```

#### Option C: Run Last Day of Every Gregorian Month
```cron
# At 23:00 on the last day of every month
0 23 28-31 * * [ "$(date +\%d -d tomorrow)" = "01" ] && cd /home/alikazemi/project/jira-telegram-bot && /home/alikazemi/miniconda3/bin/python scripts/run_monthly_evaluation_creation.py
```

### 3. Manual Execution

You can also run the script manually:

```bash
# Create records for next month (automatic)
python scripts/run_monthly_evaluation_creation.py

# Create for specific month
python scripts/run_monthly_evaluation_creation.py --month 2025-01

# Dry run to preview what would be created
python scripts/run_monthly_evaluation_creation.py --dry-run
```

## What the Job Does

1. **Fetches Active Assignments**: Gets all active manager-developer assignments from `manager_developer_assignments` table
2. **Finds Sprints**: Identifies all sprints in the target month
3. **Creates Placeholder Records**: For each assignment × sprint combination:
   - Creates a record in `manager_evaluations` table
   - Sets `collaboration_score`, `alignment_score`, and `total_manager_score` to NULL
   - Records are ready for managers to fill in
4. **Skips Duplicates**: Won't create records if they already exist

## Monitoring

### Check Logs

```bash
# View recent logs
tail -f /var/log/monthly_evaluation_creation.log

# View last run
tail -100 /var/log/monthly_evaluation_creation.log
```

### Verify Records Were Created

```sql
-- Check records for current month
SELECT 
    manager_name, 
    developer_name, 
    sprint_id,
    evaluation_month,
    created_at
FROM manager_evaluations
WHERE evaluation_month = '2025-01'
AND collaboration_score IS NULL
ORDER BY created_at DESC;
```

## Troubleshooting

### No Records Created

**Possible causes:**

1. **No Active Assignments**: Check if there are active assignments in `manager_developer_assignments`:
   ```sql
   SELECT * FROM manager_developer_assignments WHERE is_active = TRUE;
   ```

2. **No Sprints Found**: Verify sprints exist for the target month:
   ```sql
   SELECT sprint_id, sprint_name, created_at 
   FROM jira_tasks_enhanced 
   WHERE DATE_TRUNC('month', created_at) = '2025-01-01'::date
   GROUP BY sprint_id, sprint_name, created_at;
   ```

3. **Records Already Exist**: Check if placeholder records were already created

### Script Fails to Run

1. **Check Python Environment**: Ensure conda environment is activated
2. **Check Database Connection**: Verify database is accessible
3. **Check Permissions**: Ensure log file is writable

## Example Output

```
============================================================
Starting Monthly Evaluation Record Creation
============================================================
Month: 1403-10 (Jalali)
Gregorian Month: 2025-01
Records Created: 45
Assignments Processed: 45

Detailed Results:
------------------------------------------------------------
✓ Created: Manager1 → Developer1 (Sprint 123)
✓ Created: Manager1 → Developer2 (Sprint 123)
✓ Created: Manager2 → Developer3 (Sprint 124)
✗ Skipped: Manager3 → Developer4 (Sprint 125) (Already exists)
...
============================================================
Completed! 45 records created.
============================================================
```

## Integration with Admin Panel

Once created, these placeholder records will appear in the admin panel where managers can:

1. View their assigned developers
2. See performance metrics for each developer
3. Fill in collaboration_score and alignment_score
4. Submit evaluations

## Related Files

- Script: [`scripts/run_monthly_evaluation_creation.py`](../../scripts/run_monthly_evaluation_creation.py)
- Use Case: [`jira_telegram_bot/use_cases/team_evaluation/create_monthly_evaluation_records.py`](../../jira_telegram_bot/use_cases/team_evaluation/create_monthly_evaluation_records.py)
- Repository: [`jira_telegram_bot/adapters/repositories/postgres/manager_evaluation_repository.py`](../../jira_telegram_bot/adapters/repositories/postgres/manager_evaluation_repository.py)
