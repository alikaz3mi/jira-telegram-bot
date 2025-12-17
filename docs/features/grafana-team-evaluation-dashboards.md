# Grafana Dashboard for Team Evaluation Metrics

This document provides SQL queries and visualization guidance for creating comprehensive Grafana dashboards based on the team evaluation system.

## Overview

The team evaluation system now supports a **dual scoring model**:
- **System Score (70%)**: Automatically calculated based on deadline adherence, worklog, priority tasks, and quality
- **Manager Score (30%)**: Manual evaluation by managers for collaboration, alignment, and soft skills
- **Final Score**: Weighted combination of both scores

## Database Schema

### Main Table: `team_evaluation`

Key columns:
- `sprint_name`: Sprint identifier
- `developer_name`: Developer's name
- `department`: Team/department (Backend, Frontend, AI, etc.)
- `project`: Project name
- `system_score`: Calculated score (0-100+)
- `manager_evaluation_score`: Manager's evaluation (0-100)
- `final_score`: Combined score (system * 0.7 + manager * 0.3)
- `created_at`: Evaluation timestamp

## Grafana Variables

Add these variables to your dashboard (Dashboard Settings → Variables):

### Variable: `$sprint`
```sql
SELECT DISTINCT sprint_name 
FROM team_evaluation 
ORDER BY created_at DESC
LIMIT 20;
```

### Variable: `$department`
```sql
SELECT DISTINCT department 
FROM team_evaluation 
ORDER BY department;
```

### Variable: `$developer`
```sql
SELECT DISTINCT developer_name 
FROM team_evaluation 
WHERE department IN ($department)
ORDER BY developer_name;
```

---

## Dashboard Layout

### Row 1: Overview KPIs (Stat Panels)

#### Panel 1.1: Average Team Score
```sql
SELECT 
    ROUND(AVG(final_score), 1) as average_score
FROM team_evaluation
WHERE sprint_name IN ($sprint)
AND department IN ($department)
AND $__timeFilter(created_at);
```

**Visualization**: Stat / Gauge
- **Thresholds**: 
  - Red: < 60
  - Yellow: 60-79
  - Green: ≥ 80

---

#### Panel 1.2: Top Performer
```sql
SELECT 
    developer_name,
    final_score
FROM team_evaluation
WHERE sprint_name IN ($sprint)
AND department IN ($department)
ORDER BY final_score DESC
LIMIT 1;
```

**Visualization**: Stat
- Display developer name
- Show score as secondary value

---

#### Panel 1.3: Total Development Hours
```sql
SELECT 
    ROUND(SUM(development_hours), 1) as total_hours
FROM team_evaluation
WHERE sprint_name IN ($sprint)
AND department IN ($department);
```

**Visualization**: Stat

---

#### Panel 1.4: System vs Manager Alignment
```sql
SELECT 
    ROUND(
        AVG(ABS(
            ROUND(system_score * 0.7) - ROUND(manager_evaluation_score * 0.3)
        )), 
        1
    ) as alignment_gap
FROM team_evaluation
WHERE sprint_name IN ($sprint)
AND department IN ($department)
AND manager_evaluation_score IS NOT NULL;
```

**Visualization**: Stat
- **Interpretation**: Lower = better alignment between system and manager
- **Thresholds**:
  - Green: < 10
  - Yellow: 10-20
  - Red: > 20

---

### Row 2: Detailed Performance Table

#### Panel 2.1: Team Performance Table

```sql
WITH score_components AS (
    SELECT 
        developer_name,
        department,
        sprint_name,
        
        -- Raw scores
        COALESCE(system_score, quality_score) as system_score,
        manager_evaluation_score,
        COALESCE(final_score, quality_score) as final_score,
        
        -- Score breakdown (approximate from available data)
        ROUND(
            CASE 
                WHEN avg_deadline_delivery_days ~ '^-?[0-9]+\.?[0-9]*d?$' 
                THEN 100 - (CAST(REGEXP_REPLACE(avg_deadline_delivery_days, 'd', '') AS NUMERIC) * 2)
                ELSE 100
            END
        ) as deadline_score,
        
        ROUND((registered_hours_week / NULLIF(expected_hours_week, 0)) * 100) as worklog_score,
        
        ROUND(
            CASE 
                WHEN high_priority_count > 0 
                THEN (high_priority_completed_count::NUMERIC / high_priority_count) * 100
                ELSE 100
            END
        ) as priority_score,
        
        ROUND(100 - (avg_support_bugs_per_story * 30) - (avg_tester_bugs_per_story * 30)) as quality_component,
        
        -- Task metrics
        high_priority_completed_count,
        high_priority_count,
        development_delivered_count,
        registered_hours_week,
        expected_hours_week
        
    FROM team_evaluation
    WHERE sprint_name IN ($sprint)
    AND department IN ($department)
    AND $__timeFilter(created_at)
)

SELECT 
    developer_name as "Developer",
    department as "Department",
    sprint_name as "Sprint",
    system_score as "System Score",
    manager_evaluation_score as "Manager Score",
    final_score as "Final Score",
    deadline_score as "Deadline",
    worklog_score as "Worklog",
    priority_score as "Priority",
    quality_component as "Quality",
    high_priority_completed_count || '/' || high_priority_count as "High Priority",
    ROUND(registered_hours_week, 1) || '/' || ROUND(expected_hours_week, 1) as "Hours"
FROM score_components
ORDER BY final_score DESC;
```

**Visualization**: Table
- **Column Overrides**:
  - `Final Score`: Cell background color gradient (red → yellow → green)
  - `System Score`: Bold text
  - `Manager Score`: Editable (if using Grafana 9.0+ with editable tables)

---

### Row 3: Score Composition Analysis

#### Panel 3.1: Score Breakdown (Stacked Bar Chart)

```sql
WITH score_breakdown AS (
    SELECT 
        developer_name,
        
        -- Weighted components (showing their actual contribution to final score)
        ROUND(
            CASE 
                WHEN avg_deadline_delivery_days ~ '^-?[0-9]+\.?[0-9]*d?$' 
                THEN (100 - (CAST(REGEXP_REPLACE(avg_deadline_delivery_days, 'd', '') AS NUMERIC) * 2)) * 0.25
                ELSE 25
            END
        ) as deadline_contribution,
        
        ROUND((registered_hours_week / NULLIF(expected_hours_week, 0)) * 100 * 0.20) as worklog_contribution,
        
        ROUND(
            CASE 
                WHEN high_priority_count > 0 
                THEN (high_priority_completed_count::NUMERIC / high_priority_count) * 100 * 0.40
                ELSE 40
            END
        ) as priority_contribution,
        
        ROUND((100 - (avg_support_bugs_per_story * 30) - (avg_tester_bugs_per_story * 30)) * 0.15) as quality_contribution
        
    FROM team_evaluation
    WHERE sprint_name IN ($sprint)
    AND department IN ($department)
)

SELECT 
    developer_name as "Developer",
    deadline_contribution as "Deadline (25%)",
    worklog_contribution as "Worklog (20%)",
    priority_contribution as "Priority (40%)",
    quality_contribution as "Quality (15%)"
FROM score_breakdown
ORDER BY (deadline_contribution + worklog_contribution + priority_contribution + quality_contribution) DESC;
```

**Visualization**: Bar Chart (Stacked)
- **Purpose**: Shows which component is dragging down or boosting the score

---

#### Panel 3.2: System vs Manager Comparison (Grouped Bar)

```sql
SELECT 
    developer_name as "Developer",
    COALESCE(system_score, quality_score) as "System Score (70%)",
    COALESCE(manager_evaluation_score, 0) as "Manager Score (30%)"
FROM team_evaluation
WHERE sprint_name IN ($sprint)
AND department IN ($department)
ORDER BY COALESCE(final_score, quality_score) DESC;
```

**Visualization**: Bar Chart (Grouped)
- **Purpose**: Identify discrepancies between automated and manual evaluation

---

### Row 4: Historical Trends

#### Panel 4.1: Developer Score Over Time (Time Series)

```sql
SELECT 
    created_at as time,
    developer_name,
    final_score
FROM team_evaluation
WHERE developer_name IN ($developer)
AND $__timeFilter(created_at)
ORDER BY created_at;
```

**Visualization**: Time Series / Line Chart
- **Legend**: Show all developers
- **Purpose**: Track improvement or decline over sprints

---

#### Panel 4.2: Department Average Trend

```sql
SELECT 
    created_at as time,
    department,
    AVG(final_score) as avg_score
FROM team_evaluation
WHERE department IN ($department)
AND $__timeFilter(created_at)
GROUP BY created_at, department
ORDER BY created_at;
```

**Visualization**: Time Series
- **Purpose**: Compare department performance over time

---

### Row 5: Manager Evaluation Insights

#### Panel 5.1: Manager Evaluation Distribution (Histogram)

```sql
SELECT 
    FLOOR(manager_evaluation_score / 10) * 10 as score_range,
    COUNT(*) as count
FROM team_evaluation
WHERE sprint_name IN ($sprint)
AND manager_evaluation_score IS NOT NULL
GROUP BY score_range
ORDER BY score_range;
```

**Visualization**: Bar Chart
- **Purpose**: See if manager scores are normally distributed or skewed

---

#### Panel 5.2: Developers Needing Manager Review

```sql
SELECT 
    developer_name as "Developer",
    department as "Department",
    sprint_name as "Sprint",
    system_score as "System Score",
    CASE 
        WHEN manager_evaluation_score IS NULL THEN 'PENDING'
        ELSE CAST(manager_evaluation_score AS TEXT)
    END as "Manager Score",
    created_at as "Evaluation Date"
FROM team_evaluation
WHERE manager_evaluation_score IS NULL
AND sprint_name IN ($sprint)
ORDER BY created_at DESC;
```

**Visualization**: Table
- **Purpose**: Action list for managers to complete evaluations

---

## Advanced Queries

### Query 1: Top 5 Performers (All Time)

```sql
SELECT 
    developer_name,
    department,
    COUNT(*) as sprint_count,
    ROUND(AVG(final_score), 1) as avg_final_score,
    ROUND(AVG(system_score), 1) as avg_system_score,
    ROUND(AVG(manager_evaluation_score), 1) as avg_manager_score,
    MAX(final_score) as best_score,
    MIN(final_score) as worst_score
FROM team_evaluation
WHERE manager_evaluation_score IS NOT NULL
GROUP BY developer_name, department
HAVING COUNT(*) >= 3
ORDER BY avg_final_score DESC
LIMIT 5;
```

---

### Query 2: Improvement Leaders (Trend Analysis)

```sql
WITH sprint_scores AS (
    SELECT 
        developer_name,
        sprint_name,
        final_score,
        ROW_NUMBER() OVER (PARTITION BY developer_name ORDER BY created_at) as sprint_num,
        LAG(final_score) OVER (PARTITION BY developer_name ORDER BY created_at) as prev_score
    FROM team_evaluation
)

SELECT 
    developer_name as "Developer",
    sprint_name as "Latest Sprint",
    final_score as "Current Score",
    prev_score as "Previous Score",
    (final_score - prev_score) as "Improvement"
FROM sprint_scores
WHERE prev_score IS NOT NULL
AND sprint_num = (SELECT MAX(sprint_num) FROM sprint_scores s WHERE s.developer_name = sprint_scores.developer_name)
ORDER BY (final_score - prev_score) DESC
LIMIT 10;
```

---

### Query 3: Manager Score Variance Analysis

```sql
SELECT 
    department,
    ROUND(AVG(manager_evaluation_score), 1) as avg_manager_score,
    ROUND(STDDEV(manager_evaluation_score), 1) as score_stddev,
    MIN(manager_evaluation_score) as min_score,
    MAX(manager_evaluation_score) as max_score,
    COUNT(*) as evaluation_count
FROM team_evaluation
WHERE manager_evaluation_score IS NOT NULL
AND sprint_name IN ($sprint)
GROUP BY department
ORDER BY avg_manager_score DESC;
```

**Purpose**: Check if managers are calibrated (similar scoring standards across departments)

---

## Alerting Rules

### Alert 1: Low Score Alert
**Condition**: Final score < 40 for any developer
```sql
SELECT COUNT(*) 
FROM team_evaluation 
WHERE final_score < 40 
AND sprint_name = (SELECT sprint_name FROM team_evaluation ORDER BY created_at DESC LIMIT 1);
```

### Alert 2: Missing Manager Evaluations
**Condition**: Evaluations > 7 days old without manager score
```sql
SELECT COUNT(*) 
FROM team_evaluation 
WHERE manager_evaluation_score IS NULL 
AND created_at < NOW() - INTERVAL '7 days';
```

---

## Tips for Dashboard Design

1. **Use Template Variables**: Make dashboards reusable across sprints/departments
2. **Color Coding**: 
   - Green: ≥80 (Excellent)
   - Yellow: 60-79 (Good)
   - Red: <60 (Needs improvement)
3. **Manager Review Workflow**: Create a dedicated row for pending evaluations
4. **Time Range**: Default to "Last 3 months" to show trends
5. **Refresh Rate**: Set to 5 minutes for live updates during sprint reviews

---

## Example Dashboard JSON (Panel Configuration)

```json
{
  "panels": [
    {
      "title": "Average Team Score",
      "type": "stat",
      "targets": [
        {
          "rawSql": "SELECT ROUND(AVG(final_score), 1) FROM team_evaluation WHERE sprint_name IN ($sprint)"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "thresholds": {
            "steps": [
              { "color": "red", "value": 0 },
              { "color": "yellow", "value": 60 },
              { "color": "green", "value": 80 }
            ]
          }
        }
      }
    }
  ]
}
```

---

## Updating Manager Scores

Use the provided script:
```bash
# Interactive mode
python scripts/update_manager_scores.py

# Command line
python scripts/update_manager_scores.py list 50
python scripts/update_manager_scores.py update <eval_id> <score>
```

---

## Migration

Run the migration to add the new columns:
```bash
python scripts/run_migrations.py
```

This will add:
- `manager_evaluation_score` (0-100)
- `system_score` (calculated)
- `final_score` (weighted combination)
