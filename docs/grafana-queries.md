# Grafana Dashboard Queries for Project Management

This document contains SQL queries for monitoring Jira projects in Grafana.

## Table of Contents
- [Setup](#setup)
- [Key Metrics](#key-metrics)
- [Time Trends](#time-trends)
- [Feature Delivery](#feature-delivery)
- [Bug Analysis](#bug-analysis)
- [Work Distribution](#work-distribution)
- [Team & Capacity](#team--capacity)
- [Quality Indicators](#quality-indicators)
- [Dashboard Layout](#dashboard-layout)

---

## Setup

### Database Connection
- **Host:** `postgres:5432` (from within Docker network)
- **Database:** `jira_telegram_bot`
- **User:** `grafana_user`
- **Password:** `sdl@sxcvbio32490@ydf`
- **SSL Mode:** `disable`

### Variables
Create these variables in Grafana:

1. **$project** - Project filter
   ```sql
   SELECT DISTINCT project FROM jira_tasks_enhanced ORDER BY project;
   ```
   - Type: Query
   - Multi-value: Yes
   - Include All option: Yes

2. **Time Range** - Use Grafana's built-in `$__timeFrom()` and `$__timeTo()`

---

## Key Metrics

### 1. Cycle Time Analysis (In Progress → Done)
**Purpose:** Measure how long tasks take to complete once started

**Query:**
```sql
WITH in_progress_times AS (
    SELECT 
        issue_key,
        MIN(changed_at) as started_at
    FROM jira_status_history
    WHERE to_status = 'In Progress'
        AND changed_at >= $__timeFrom()
        AND changed_at <= $__timeTo()
    GROUP BY issue_key
),
done_times AS (
    SELECT 
        issue_key,
        MIN(changed_at) as completed_at
    FROM jira_status_history
    WHERE to_status IN ('Done', 'Closed', 'Resolved')
    GROUP BY issue_key
)
SELECT 
    DATE_TRUNC('week', d.completed_at) as time,
    t.project,
    AVG(EXTRACT(EPOCH FROM (d.completed_at - ip.started_at)) / 86400) as avg_cycle_time_days,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (d.completed_at - ip.started_at)) / 86400) as median_cycle_time_days,
    COUNT(*) as completed_tasks
FROM jira_tasks_enhanced t
INNER JOIN in_progress_times ip ON t.key = ip.issue_key
INNER JOIN done_times d ON t.key = d.issue_key
WHERE d.completed_at > ip.started_at
    AND t.project = $project
    AND d.completed_at >= $__timeFrom()
    AND d.completed_at <= $__timeTo()
GROUP BY time, t.project
ORDER BY time;
```

**Visualization:**
- Panel Type: Graph (Time series)
- Y-Axis: Dual axis (avg_cycle_time_days, median_cycle_time_days)
- Legend: Bottom
- Format: Days with 1 decimal

---

### 2. Lead Time Analysis (Created → Done)
**Purpose:** Measure total time from issue creation to completion

**Query:**
```sql
WITH done_times AS (
    SELECT 
        issue_key,
        MIN(changed_at) as completed_at
    FROM jira_status_history
    WHERE to_status IN ('Done', 'Closed', 'Resolved')
    GROUP BY issue_key
)
SELECT 
    DATE_TRUNC('week', d.completed_at) as time,
    t.project,
    t.task_type,
    AVG(EXTRACT(EPOCH FROM (d.completed_at - t.created_at)) / 86400) as avg_lead_time_days,
    COUNT(*) as count
FROM jira_tasks_enhanced t
INNER JOIN done_times d ON t.key = d.issue_key
WHERE d.completed_at >= $__timeFrom()
    AND d.completed_at <= $__timeTo()
    AND t.project = $project
GROUP BY time, t.project, t.task_type
ORDER BY time;
```

**Visualization:**
- Panel Type: Bar chart
- Stacking: Normal
- Group by: task_type
- Format: Days with 1 decimal

---

### 3. Throughput (Completed Items per Week)
**Purpose:** Track team velocity and delivery rate

**Query:**
```sql
SELECT 
    DATE_TRUNC('week', changed_at) as time,
    h.project,
    COUNT(DISTINCT h.issue_key) as completed_issues
FROM jira_status_history h
WHERE to_status IN ('Done', 'Closed', 'Resolved')
    AND changed_at >= $__timeFrom()
    AND changed_at <= $__timeTo()
    AND project = $project
GROUP BY time, h.project
ORDER BY time;
```

**Visualization:**
- Panel Type: Graph (Time series with bars)
- Display: Both lines and bars
- Legend: Bottom

---

### 4. Work in Progress (WIP) Over Time
**Purpose:** Monitor bottlenecks and workflow health

**Query:**
```sql
SELECT 
    DATE_TRUNC('day', changed_at) as time,
    project,
    COUNT(DISTINCT issue_key) as wip_count
FROM (
    SELECT 
        issue_key,
        project,
        changed_at,
        to_status,
        LEAD(to_status) OVER (PARTITION BY issue_key ORDER BY changed_at) as next_status
    FROM jira_status_history
    WHERE changed_at >= $__timeFrom()
        AND changed_at <= $__timeTo()
) sub
WHERE to_status = 'In Progress'
    AND (next_status IS NULL OR next_status != 'Done')
    AND project = $project
GROUP BY time, project
ORDER BY time;
```

**Visualization:**
- Panel Type: Graph (Area chart)
- Fill opacity: 30%
- Thresholds: Green <10, Yellow 10-20, Red >20

---

## Bug Analysis

### 5. Bug Root Cause Analysis
**Purpose:** Identify systemic quality issues

**Query:**
```sql
SELECT 
    COALESCE(root_cause, 'Not Specified') as metric,
    COUNT(*) as value
FROM jira_tasks_enhanced
WHERE project = $project
    AND task_type = 'Bug'
    AND created_at >= $__timeFrom()
    AND created_at <= $__timeTo()
GROUP BY root_cause
ORDER BY value DESC;
```

**Visualization:**
- Panel Type: Pie chart
- Display labels: Name and percent
- Legend: Right side

---

### 6. Bug Resolution Time by Root Cause
**Purpose:** Understand which bug types take longest to fix

**Query:**
```sql
WITH done_times AS (
    SELECT 
        issue_key,
        MIN(changed_at) as completed_at
    FROM jira_status_history
    WHERE to_status IN ('Done', 'Closed', 'Resolved')
    GROUP BY issue_key
)
SELECT 
    COALESCE(t.root_cause, 'Not Specified') as root_cause,
    AVG(EXTRACT(EPOCH FROM (d.completed_at - t.created_at)) / 86400) as avg_days,
    COUNT(*) as bug_count
FROM jira_tasks_enhanced t
INNER JOIN done_times d ON t.key = d.issue_key
WHERE t.project = $project
    AND t.task_type = 'Bug'
    AND t.created_at >= $__timeFrom()
    AND t.created_at <= $__timeTo()
GROUP BY root_cause
ORDER BY avg_days DESC;
```

**Visualization:**
- Panel Type: Bar gauge (Horizontal)
- Display mode: Gradient
- Thresholds: Green <3, Yellow 3-7, Red >7 days

---

## Feature Delivery

### 7. Sprint Burndown
**Purpose:** Track sprint progress

**Query:**
```sql
SELECT 
    DATE_TRUNC('day', h.changed_at) as time,
    COUNT(DISTINCT CASE WHEN h.to_status IN ('Done', 'Closed', 'Resolved') THEN h.issue_key END) as completed,
    COUNT(DISTINCT t.key) - COUNT(DISTINCT CASE WHEN h.to_status IN ('Done', 'Closed', 'Resolved') THEN h.issue_key END) as remaining
FROM jira_tasks_enhanced t
LEFT JOIN jira_status_history h ON t.key = h.issue_key 
    AND h.changed_at >= $__timeFrom()
    AND h.changed_at <= $__timeTo()
WHERE t.project = $project
    AND t.last_sprint != 'Backlog'
    AND t.created_at <= $__timeTo()
GROUP BY time
ORDER BY time;
```

**Visualization:**
- Panel Type: Graph (Line chart)
- Add ideal burndown line manually
- Legend: Bottom

---

### 10. Feature Completion Rate
**Purpose:** Track feature delivery percentage

**Query:**
```sql
SELECT 
    DATE_TRUNC('week', h.changed_at) as time,
    COUNT(DISTINCT t.key) FILTER (WHERE h.to_status IN ('Done', 'Closed', 'Resolved')) as completed,
    COUNT(DISTINCT t.key) as total,
    (COUNT(DISTINCT t.key) FILTER (WHERE h.to_status IN ('Done', 'Closed', 'Resolved'))::float / 
     NULLIF(COUNT(DISTINCT t.key), 0) * 100) as completion_percentage
FROM jira_tasks_enhanced t
LEFT JOIN jira_status_history h ON t.key = h.issue_key
WHERE t.project = $project
    AND t.task_type IN ('Story', 'Feature')
    AND t.created_at >= $__timeFrom()
    AND t.created_at <= $__timeTo()
GROUP BY time
ORDER BY time;
```

**Visualization:**
- Panel Type: Stat
- Unit: Percent (0-100)
- Show sparkline graph below
- Thresholds: Red <50, Yellow 50-80, Green >80

---

### 11. Bug Arrival Rate vs Resolution Rate
**Purpose:** Monitor quality trends

**Query:**
```sql
SELECT 
    DATE_TRUNC('day', created_at) as time,
    'Created' as metric,
    COUNT(*) as value
FROM jira_tasks_enhanced
WHERE project = $project
    AND task_type = 'Bug'
    AND created_at >= $__timeFrom()
    AND created_at <= $__timeTo()
GROUP BY time

UNION ALL

SELECT 
    DATE_TRUNC('day', h.changed_at) as time,
    'Resolved' as metric,
    COUNT(DISTINCT h.issue_key) as value
FROM jira_status_history h
INNER JOIN jira_tasks_enhanced t ON h.issue_key = t.key
WHERE h.to_status IN ('Done', 'Closed', 'Resolved')
    AND t.project = $project
    AND t.task_type = 'Bug'
    AND h.changed_at >= $__timeFrom()
    AND h.changed_at <= $__timeTo()
GROUP BY time

ORDER BY time;
```

**Visualization:**
- Panel Type: Graph (Line chart)
- Two lines: Created and Resolved
- Alert if Created > Resolved consistently

---

### 12. Component Performance
**Purpose:** Identify slow-moving components

**Query:**
```sql
WITH done_times AS (
    SELECT 
        issue_key,
        MIN(changed_at) as completed_at
    FROM jira_status_history
    WHERE to_status IN ('Done', 'Closed', 'Resolved')
    GROUP BY issue_key
)
SELECT 
    UNNEST(t.components) as component,
    COUNT(*) as total_tasks,
    AVG(EXTRACT(EPOCH FROM (d.completed_at - t.created_at)) / 86400) as avg_lead_time_days,
    SUM(COALESCE(t.story_points, 0)) as total_story_points
FROM jira_tasks_enhanced t
LEFT JOIN done_times d ON t.key = d.issue_key
WHERE t.project = $project
    AND t.created_at >= $__timeFrom()
    AND t.created_at <= $__timeTo()
    AND array_length(t.components, 1) > 0
GROUP BY component
ORDER BY avg_lead_time_days DESC;
```

**Visualization:**
- Panel Type: Table
- Column thresholds on avg_lead_time_days: Green <5, Yellow 5-10, Red >10
- Sort by avg_lead_time_days DESC

---

## Work Distribution

### 8. Status Distribution Heatmap
**Purpose:** Visualize where work is stuck

**Query:**
```sql
SELECT 
    t.status as metric,
    t.project,
    COUNT(*) as value
FROM jira_tasks_enhanced t
WHERE t.status NOT IN ('Done', 'Closed', 'Resolved')
    AND t.project = $project
GROUP BY t.status, t.project
ORDER BY value DESC;
```

**Visualization:**
- Panel Type: Bar chart (Grouped)
- Group by: project
- Orientation: Vertical

---

### 13. Priority Distribution & Age
**Purpose:** Ensure high-priority items are addressed

**Query:**
```sql
SELECT 
    t.priority,
    t.status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - t.created_at)) / 86400) as avg_age_days
FROM jira_tasks_enhanced t
WHERE t.status NOT IN ('Done', 'Closed', 'Resolved')
    AND t.project = $project
GROUP BY t.priority, t.status
ORDER BY 
    CASE t.priority 
        WHEN 'Highest' THEN 1 
        WHEN 'High' THEN 2 
        WHEN 'Medium' THEN 3 
        WHEN 'Low' THEN 4 
        ELSE 5 
    END;
```

**Visualization:**
- Panel Type: Heatmap
- X-axis: status
- Y-axis: priority
- Color: avg_age_days (Red = older)

---

## Team & Capacity

### 9. Assignee Workload
**Purpose:** Balance team capacity

**Query:**
```sql
SELECT 
    t.assignee as metric,
    t.project,
    COUNT(*) as active_tasks,
    SUM(CASE WHEN t.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
    SUM(COALESCE(t.story_points, 0)) as total_points
FROM jira_tasks_enhanced t
WHERE t.status NOT IN ('Done', 'Closed', 'Resolved')
    AND t.assignee IS NOT NULL
    AND t.project = $project
GROUP BY t.assignee, t.project
ORDER BY total_points DESC;
```

**Visualization:**
- Panel Type: Table
- Cell thresholds:
  - active_tasks: Green <5, Yellow 5-10, Red >10
  - total_points: Green <20, Yellow 20-40, Red >40
- Enable sorting on all columns

---

## Quality Indicators

### 14. Reopened Issues Trend
**Purpose:** Track quality and requirement clarity

**Query:**
```sql
SELECT 
    DATE_TRUNC('week', changed_at) as time,
    project,
    COUNT(DISTINCT issue_key) as reopened_count
FROM jira_status_history
WHERE to_status IN ('Reopened', 'To Do', 'In Progress')
    AND from_status IN ('Done', 'Closed', 'Resolved')
    AND changed_at >= $__timeFrom()
    AND changed_at <= $__timeTo()
    AND project = $project
GROUP BY time, project
ORDER BY time;
```

**Visualization:**
- Panel Type: Graph (Line chart)
- Alert if trend increasing
- Thresholds: Green <3, Yellow 3-7, Red >7 per week

---

### 15. Fix Version Progress
**Purpose:** Track release readiness

**Query:**
```sql
SELECT 
    UNNEST(fix_versions) as version,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status IN ('Done', 'Closed', 'Resolved')) as completed,
    (COUNT(*) FILTER (WHERE status IN ('Done', 'Closed', 'Resolved'))::float / 
     NULLIF(COUNT(*), 0) * 100) as completion_percentage
FROM jira_tasks_enhanced
WHERE project = $project
    AND array_length(fix_versions, 1) > 0
GROUP BY version
ORDER BY completion_percentage ASC;
```

**Visualization:**
- Panel Type: Bar gauge (Horizontal)
- Unit: Percent (0-100)
- Thresholds: Red <50, Yellow 50-90, Green >90

---

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│  DASHBOARD: Project Health Overview                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [Time Range Picker: Last 30 days / Last Quarter / Custom] │
│  [Project Variable: ALL / PROJECT1 / PROJECT2]                   │
│                                                              │
├──────────────────────┬──────────────────────┬───────────────┤
│ Row 1: Key Metrics (Stat Panels)                            │
├──────────────────────┼──────────────────────┼───────────────┤
│  Avg Cycle Time     │  Throughput/Week    │  WIP Count    │
│    [#1]              │    [#3]              │   [#4]        │
│  7.2 days ↓         │    23 items ↑        │   15 items    │
└──────────────────────┴──────────────────────┴───────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Row 2: Time Trends                                          │
├──────────────────────────────────────┬──────────────────────┤
│  Cycle Time Trend [#1]               │  Lead Time [#2]      │
│  (Line graph - dual axis)            │  (Bar chart)         │
│                                       │                      │
└──────────────────────────────────────┴──────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Row 3: Feature Delivery                          │
├──────────────────────────────────────┬──────────────────────┤
│  Sprint Burndown [#7]                │  Completion Rate[#10]│
│  (Line chart with ideal line)        │  (Stat with trend)   │
│                                       │                      │
├──────────────────────────────────────┴──────────────────────┤
│  Component Performance [#12]                                │
│  (Table with conditional formatting)                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Row 4: Bug Analysis                                   │
├───────────────────────┬─────────────────────┬───────────────┤
│  Root Cause [#5]     │  Resolution Time[#6]│ Arrival vs    │
│  (Pie chart)         │  (Bar gauge)        │ Resolution[#11]│
│                      │                      │ (Line chart)  │
└───────────────────────┴─────────────────────┴───────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Row 5: Work Distribution                                    │
├──────────────────────────────────────┬──────────────────────┤
│  Status Heatmap [#8]                 │  Priority Grid [#13] │
│  (Grouped bar chart)                 │  (Heatmap)           │
└──────────────────────────────────────┴──────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Row 6: Team & Capacity                                      │
├──────────────────────────────────────────────────────────────┤
│  Assignee Workload [#9]                                     │
│  (Table with thresholds: green<5, yellow 5-10, red>10)     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Row 7: Quality Indicators                                   │
├──────────────────────────────────────┬──────────────────────┤
│  Reopened Issues [#14]               │  Fix Version [#15]   │
│  (Line chart)                        │  (Bar gauge)         │
└──────────────────────────────────────┴──────────────────────┘
```

---

## Best Practices

1. **Refresh Rate:** Set auto-refresh to 5-10 minutes for live dashboards
2. **Time Ranges:** Use relative ranges (Last 7 days, Last 30 days, Last quarter)
3. **Alerts:** Configure alerts on key metrics (WIP >20, Reopened issues >5/week)
4. **Decimals:** Use 0 for counts, 1 for days/percentages
5. **Legends:** Place legends at the bottom or right to maximize chart space
6. **Mobile:** Test dashboard on mobile devices for on-the-go monitoring

---

## Troubleshooting

### No Data Showing
1. Check time range - ensure it covers period with data
2. Verify `jira_status_history` table has data:
   ```sql
   SELECT COUNT(*) FROM jira_status_history;
   ```
3. Check project filter variable

### Slow Queries
1. Ensure indexes exist on `jira_status_history`:
   - `idx_status_history_issue_key`
   - `idx_status_history_to_status`
   - `idx_status_history_changed_at`

2. Verify indexes on `jira_tasks_enhanced`:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_jira_tasks_project ON jira_tasks_enhanced(project);
   CREATE INDEX IF NOT EXISTS idx_jira_tasks_status ON jira_tasks_enhanced(status);
   CREATE INDEX IF NOT EXISTS idx_jira_tasks_created_at ON jira_tasks_enhanced(created_at);
   ```

### Connection Issues
- Verify Grafana container is on `jira-telegram-bot-network`
- Check database credentials
- Test connection with:
  ```bash
  docker exec grafana_container_name ping postgres
  ```
