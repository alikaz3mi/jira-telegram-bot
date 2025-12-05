# Database Synchronization Guide

This guide explains how to keep your PostgreSQL database synchronized with Jira for Grafana dashboards.

## Overview

The system syncs data from Jira to PostgreSQL in two ways:
1. **Manual Full Sync** - Sync all historical data
2. **Automated Updates** - Keep data current via webhooks or scheduled jobs

---

## Manual Full Sync

### When to Use
- Initial setup
- After adding new projects
- After data corruption or loss
- When you need to backfill historical data

### How to Run

```bash
python scripts/sync_projects.py
```

This will sync all configured projects defined in `SYNC_PROJECT_KEYS` environment variable.

**Configuration:** Set environment variables in `docker/.env`:
```bash
# List of Jira project keys to synchronize (JSON array format)
SYNC_PROJECT_KEYS=["PROJECT1","PROJECT2","PROJECT3"]

# Interval between sync operations (in minutes)
SYNC_INTERVAL_MINUTES=10

# Whether to perform full sync (true) or incremental sync (false)
SYNC_FULL_SYNC=true
```

### What Gets Synced
- All issues (bugs, stories, tasks, etc.)
- Issue metadata (assignee, priority, status, components, etc.)
- Worklogs
- Linked issues
- Status change history
- Root cause (for bugs)
- Fix versions
- Affected versions

### Expected Duration
- Typical project (~1000 issues): ~60 seconds
- Large project (~2500 issues): ~180 seconds
- Duration depends on issue count and network speed

---

## Automated Updates

You have **three options** for keeping data current:

### Option 1: Jira Webhooks (Real-time) ⭐ **RECOMMENDED**

**Pros:**
- Real-time updates (instant)
- No resource overhead
- Most accurate

**Cons:**
- Requires Jira webhook configuration
- Only captures changes, not new issues from other sources

**Setup:**

1. **Verify webhook handler is running:**
   ```bash
   docker ps | grep ticketing_bot
   ```
   Should show `ticketing_bot` container running on port 2315.

2. **Update webhook handler** to use `SyncJiraIssueUseCase`:
   
   The webhook already exists but needs to call the sync use case. Update `./jira_telegram_bot/use_cases/handle_jira_webhook_usecase.py`:

   ```python
   from jira_telegram_bot.use_cases.sync_jira_issue_use_case import SyncJiraIssueUseCase
   
   class HandleJiraWebhookUseCase:
       def __init__(
           self,
           # ... existing dependencies
           sync_use_case: SyncJiraIssueUseCase,
       ):
           # ... existing code
           self._sync_use_case = sync_use_case
       
       async def process_event(self, event: dict):
           # ... existing code
           
           # Add this after processing:
           if issue_key:
               await self._sync_use_case.sync_issue_from_webhook(
                   issue_key=issue_key,
                   event_type=event.get('webhookEvent', 'issue_updated')
               )
   ```

3. **Configure Jira webhook:**
   - Go to Jira → Settings → System → Webhooks
   - URL: `https://your-domain.com/webhook/jira`
   - Events: Issue Created, Updated, Deleted, Commented
   - JQL Filter (optional): `project IN (PROJECT1, PROJECT2)` (use your project keys)

4. **Restart the service:**
   ```bash
   docker restart ticketing_bot
   ```

---

### Option 2: Scheduled Sync (Every 5-15 minutes) ⭐ **EASIEST**

**Pros:**
- Automatic
- Captures all changes
- Uses existing `sync_projects.py` script
- Simple to set up

**Cons:**
- 5-15 minute delay
- Runs full sync each time (slower than incremental)

**Setup Using Existing Script:**

**Option A - Run as Docker Service:**

1. **Add to `docker-compose.yml`:**

   ```yaml
   jira-sync-service:
     build:
       context: .
       dockerfile: Dockerfile
     container_name: jira_sync_service
     image: jira_telegram_bot:v3
     volumes:
       - .:/app
     command: >
       bash -c "while true; do python3 scripts/sync_projects.py; sleep 600; done"
     restart: always
     networks:
       - jira-telegram-bot-network
   ```

2. **Start the service:**
   ```bash
   docker-compose up -d jira-sync-service
   ```

3. **Monitor logs:**
   ```bash
   docker logs -f jira_sync_service
   ```

## Recommended Setup

For the best balance of real-time data and resource usage:

1. **Use Option 1 (Webhooks)** for real-time critical updates
2. **Add Option 2 (Scheduled sync)** as a safety net (every 1-2 hours)
3. **Run Option 3 (Full sync)** weekly to catch any missed updates

## Monitoring Sync Status

### Check Last Sync Time
```sql
SELECT 
    project_key,
    last_full_sync,
    last_incremental_sync,
    last_sync_status,
    issues_synced,
    issues_failed
FROM sync_status
ORDER BY COALESCE(last_full_sync, last_incremental_sync) DESC;
```

### Check Status History
```sql
SELECT 
    COUNT(*) as total_status_changes,
    COUNT(DISTINCT issue_key) as issues_with_history,
    MAX(changed_at) as last_change
FROM jira_status_history;
```

### Check Recent Issues
```sql
SELECT 
    project,
    COUNT(*) as issue_count,
    MAX(updated_at) as last_updated
FROM jira_tasks_enhanced
GROUP BY project;
```

---

## Troubleshooting

### Sync Takes Too Long
- Use incremental sync instead of full sync
- Increase `max_results` batch size in `JiraDataService`
- Check network latency to Jira

### Missing Data
1. Check sync_status table for errors
2. Verify Jira credentials in `.env`
3. Check Jira API rate limits
4. Review logs for errors

### Database Connection Issues
```bash
# Test PostgreSQL connection
docker exec jira-telegram-bot-postgres psql -U jira_bot -d jira_telegram_bot -c "SELECT 1;"

# Check if sync service can connect
docker logs jira_sync_service | grep "Created PostgreSQL engine"
```

### Webhook Not Working
1. Check if `ticketing_bot` is running: `docker ps | grep ticketing_bot`
2. Verify webhook URL is accessible from Jira
3. Check webhook logs in Jira admin panel
4. Test webhook manually:
   ```bash
   curl -X POST http://localhost:2315/webhook/jira \
     -H "Content-Type: application/json" \
     -d '{"webhookEvent":"jira:issue_updated","issue":{"key":"TEST-123"}}'
   ```

---

## Database Maintenance

### Vacuum Database (Monthly)
```sql
VACUUM ANALYZE jira_tasks_enhanced;
VACUUM ANALYZE jira_status_history;
```

### Rebuild Indexes (If slow)
```sql
REINDEX TABLE jira_tasks_enhanced;
REINDEX TABLE jira_status_history;
```

### Clean Old Status History (Optional - keep last 2 years)
```sql
DELETE FROM jira_status_history 
WHERE changed_at < NOW() - INTERVAL '2 years';
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Full sync | `python scripts/sync_projects.py` |
| Check sync status | `docker exec jira-telegram-bot-postgres psql -U jira_bot -d jira_telegram_bot -c "SELECT * FROM sync_status;"` |
| View sync logs | `docker logs jira_sync_service` |
| Restart webhook | `docker restart ticketing_bot` |
| Test database | `docker exec jira-telegram-bot-postgres psql -U jira_bot -d jira_telegram_bot -c "SELECT COUNT(*) FROM jira_tasks_enhanced;"` |

---

## Summary

- **For immediate setup:** Run manual sync now: `python scripts/sync_projects.py`
- **For ongoing updates:** Set up webhooks (Option 1) + scheduled sync (Option 2)
- **For monitoring:** Check Grafana dashboards and sync_status table
- **For maintenance:** Run weekly full sync via cron

Your dashboards will stay current with minimal manual intervention! 🎉
