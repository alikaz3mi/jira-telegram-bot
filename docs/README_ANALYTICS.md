# Documentation Index

Welcome to the Jira Telegram Bot documentation!

## 📊 Analytics & Reporting

### [Grafana Dashboard Queries](./grafana-queries.md)
15 pre-built SQL queries for PM/PO dashboards:
- **Cycle Time & Lead Time** - Measure delivery speed
- **Bug Root Cause Analysis** - Identify quality issues
- **Sprint Burndown** - Track sprint progress
- **Team Workload** - Balance capacity
- **Quality Metrics** - Monitor reopened issues, resolution rates

### [Database Synchronization Guide](./database-sync-guide.md)
Keep your dashboards current with three sync methods:
- **Real-time Webhooks** (recommended) - Instant updates
- **Scheduled Incremental Sync** - Every 5-15 minutes
- **Manual Full Sync** - On-demand complete refresh

## 🗄️ Database Schema

### Main Tables
- **`jira_tasks_enhanced`** - All issue data with metadata
- **`jira_status_history`** - Status change tracking for cycle time metrics
- **`sync_status`** - Synchronization tracking and health

### Key Fields Added
- `root_cause` - Bug categorization
- `fix_versions` - Release tracking
- `affected_versions` - Version impact
- Status history with timestamps for accurate metrics

## 🚀 Quick Start

### 1. Initial Data Sync (First Time)
```bash
python scripts/sync_projects.py
```
Expected time: 3-4 minutes for full historical sync

### 2. Connect Grafana to PostgreSQL
- **Host:** `postgres:5432` (Docker network) or `127.0.0.1:57235` (host)
- **Database:** `jira_telegram_bot`
- **User:** `grafana_user`
- **Password:** `sdl@sxcvbio32490@ydf`
- **SSL Mode:** `disable`

### 3. Create Dashboard Panels
Copy queries from [grafana-queries.md](./grafana-queries.md) and create:
- Time series graphs for trends
- Pie charts for distributions
- Tables for detailed views
- Stat panels for KPIs

### 4. Setup Automated Updates
Follow [database-sync-guide.md](./database-sync-guide.md#recommended-setup):
```bash
# Option 1: Enable webhooks for real-time updates
# Option 2: Add scheduled sync service to docker-compose.yml
# Option 3: Setup cron for weekly full sync
```

## 📐 Architecture Flow

```
┌─────────────┐
│  Jira API   │
└──────┬──────┘
       │ Fetch issues + changelog
       ↓
┌─────────────────────┐
│ JiraDataService     │ Extract: status changes, worklogs,
│                     │          components, versions, etc.
└──────┬──────────────┘
       │
       ↓
┌──────────────────────────┐
│ SyncJiraIssueUseCase     │ Sync logic (full/incremental)
└──────┬───────────────────┘
       │
       ↓
┌───────────────────────────┐
│ JiraReportRepository      │ Store in PostgreSQL
│ (PostgreSQL)              │
└──────┬────────────────────┘
       │
       ↓
┌────────────────────┐
│  Grafana           │ Visualize with dashboards
│  (grafana_user)    │
└────────────────────┘
```

## 📚 Additional Documentation

- [Test Summaries](./TEST_FINAL_SUMMARY.md) - Unit & integration test coverage
- [Features](./features/) - Detailed feature documentation
- [Infrastructure](./infrastructure/) - Setup and deployment guides
- [Video Upload Guide](./VIDEO_UPLOAD_FIX.md) - Media handling documentation

## 🔍 Monitoring & Maintenance

### Check Sync Status
```sql
SELECT * FROM sync_status ORDER BY last_full_sync DESC;
```

### Verify Data Freshness
```sql
SELECT 
    project,
    MAX(updated_at) as last_update,
    COUNT(*) as total_issues
FROM jira_tasks_enhanced
GROUP BY project;
```

### View Status History
```sql
SELECT 
    COUNT(*) as total_changes,
    COUNT(DISTINCT issue_key) as tracked_issues,
    MAX(changed_at) as last_change
FROM jira_status_history;
```

## 🆘 Troubleshooting

### No Data in Grafana
1. Check database connection
2. Verify sync completed: `SELECT * FROM sync_status;`
3. Check time range in Grafana dashboard

### Sync Errors
```bash
# View sync logs
docker logs jira_sync_service

# Test database connection
docker exec jira-telegram-bot-postgres psql -U jira_bot -d jira_telegram_bot -c "SELECT 1;"

# Manual sync
python scripts/sync_projects.py
```

### Slow Queries
```sql
-- Verify indexes exist
\d jira_tasks_enhanced
\d jira_status_history

-- Rebuild if needed
REINDEX TABLE jira_tasks_enhanced;
REINDEX TABLE jira_status_history;
```

## 📊 Dashboard Examples

**Bug Tracking:**
- Root cause breakdown (pie chart)
- Resolution time by cause (bar gauge)
- Bug arrival vs resolution rate (line chart)
- Fix version progress (horizontal bar gauge)

**Feature Delivery:**
- Sprint burndown with ideal line
- Completion rate with sparkline
- Component performance table
- Cycle time trends (dual-axis line chart)

**Combined:**
- Team workload distribution
- WIP over time (area chart)
- Status distribution heatmap
- Priority age matrix

## 🎯 Key Metrics Reference

| Metric | Definition | Target |
|--------|------------|--------|
| **Cycle Time** | In Progress → Done | <7 days |
| **Lead Time** | Created → Done | <14 days |
| **Throughput** | Items completed/week | >20 |
| **WIP** | Currently in progress | <15 |
| **Bug Resolution** | Creation → Resolution | <5 days |
| **Completion Rate** | % stories done on time | >80% |

---

For detailed query syntax and visualization settings, see [grafana-queries.md](./grafana-queries.md).

For sync setup and automation, see [database-sync-guide.md](./database-sync-guide.md).
