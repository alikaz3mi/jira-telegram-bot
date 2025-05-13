#!/usr/bin/env python
# reports_full.py
from __future__ import annotations

import re
from datetime import datetime

import pandas as pd
from tqdm import tqdm

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraServerRepository
from jira_telegram_bot.settings import JIRA_SETTINGS


jira_repository = JiraServerRepository(settings=JIRA_SETTINGS)


def remove_illegal_chars(value):
    """
    Remove or replace characters that are illegal in XML (and thus in XLSX).
    Specifically remove ASCII control characters 0-8, 11-12, 14-31, 127-159.
    """
    if isinstance(value, str):
        return re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]", "", value)
    return value


def sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply 'remove_illegal_chars' to every object (string) column in the DataFrame.
    This avoids openpyxl illegal character errors.
    """
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(remove_illegal_chars)
    return df


def get_tasks_info():
    """
    Fetch tasks from Jira and return as a list of dictionaries,
    including Sprint data, Epic references, etc.
    """
    start_at = 0
    max_results = 100
    issues = []
    while True:
        batch = jira_repository.jira.search_issues(
            "project = PARSCHAT",
            startAt=start_at,
            maxResults=max_results,
        )
        if not batch:
            break
        issues.extend(batch)
        if len(batch) < max_results:
            break
        start_at += max_results

    LOGGER.info(f"Found {len(issues)} issues")

    tasks_info = []
    epics = {}

    # Collect epics in a dict for referencing
    for issue in issues:
        if issue.fields.issuetype.name == "Epic":
            epics[issue.key] = issue.fields.summary

    # Build task info list
    for issue in tqdm(issues):
        if issue.fields.issuetype.name == "Epic":
            continue

        # Gather comments that are not from the reporter
        comments_text = []
        if issue.fields.comment and issue.fields.comment.comments:
            for comment in issue.fields.comment.comments:
                commenter = comment.author.displayName
                if commenter != issue.fields.reporter.displayName:
                    comments_text.append(f"{commenter}: {comment.body}")

        # Get sprint info
        sprint_field = getattr(issue.fields, "customfield_10104", None)
        if sprint_field and len(sprint_field) > 0:
            sprint_str = str(sprint_field[-1])
            # Extract name between "name=" and ",startDate"
            name_start = sprint_str.find("name=") + 5
            name_end = sprint_str.find(",startDate")
            last_sprint_name = sprint_str[name_start:name_end]
            sprint_count = len(sprint_field)
        else:
            last_sprint_name = None
            sprint_count = 0

        # Story points
        story_points = getattr(issue.fields, "customfield_10106", None)

        task_info = {
            "key": issue.key,
            "summary": issue.fields.summary,
            "description": issue.fields.description or "",
            "epic_name": epics.get(issue.fields.customfield_10100),
            "comments": "\n".join(comments_text),
            "task_type": issue.fields.issuetype.name,
            "assignee": issue.fields.assignee.displayName
            if issue.fields.assignee
            else None,
            "reporter": issue.fields.reporter.displayName
            if issue.fields.reporter
            else None,
            "priority": issue.fields.priority.name if issue.fields.priority else None,
            "status": issue.fields.status.name,
            "created_at": issue.fields.created,
            "updated_at": issue.fields.updated,
            "resolved_at": issue.fields.resolutiondate,
            "target_start": getattr(issue.fields, "customfield_10109", None),
            "target_end": getattr(issue.fields, "customfield_10110", None),
            "story_points": story_points,
            "components": "{"
            + ",".join([c.name for c in issue.fields.components])
            + "}"
            if issue.fields.components
            else "{}",
            "labels": "{" + ",".join(issue.fields.labels) + "}"
            if issue.fields.labels
            else "{}",
            "last_sprint": last_sprint_name,
            "sprint_repeats": sprint_count,
        }
        tasks_info.append(task_info)

    return tasks_info


def create_sprint_progress_dashboard(df: pd.DataFrame):
    """
    Create data frames for the overall Sprint Progress Dashboard:
      1. Sprint Completion Rate (overall)
      2. Task Status Breakdown (overall)
      3. High-Priority Blockers (overall)
      4. Burn-down Placeholder (overall)
    Returns a dict of DataFrames to be written to Excel sheets.
    """

    # -- 1. Overall Sprint Completion Rate -----------------------------------
    sprint_df = df[df["last_sprint"].notnull()].copy()
    planned_tasks = len(sprint_df)
    completed_tasks = len(
        sprint_df[sprint_df["status"].str.lower().str.contains("done", na=False)],
    )
    sprint_completion_rate = (
        (completed_tasks / planned_tasks * 100) if planned_tasks > 0 else 0
    )

    sprint_completion_data = {
        "Metric": ["Planned Tasks", "Completed Tasks", "Completion Rate (%)"],
        "Value": [planned_tasks, completed_tasks, round(sprint_completion_rate, 2)],
    }
    sprint_completion_df = pd.DataFrame(sprint_completion_data)

    # -- 2. Task Status Breakdown (overall) ----------------------------------
    task_status_breakdown = df.groupby("status")["key"].count().reset_index()
    task_status_breakdown.columns = ["Status", "Count"]

    # -- 3. High-Priority Blockers (overall) ---------------------------------
    blockers_df = df[
        (df["priority"].isin(["High", "Highest", "Critical"]))
        & (~df["status"].str.lower().str.contains("done", na=False))
    ].copy()

    # -- 4. Burn-down Placeholder (overall) ----------------------------------
    burn_down_data = {
        "Day": ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5"],
        "Remaining Tasks": [40, 30, 25, 10, 0],
    }
    burn_down_df = pd.DataFrame(burn_down_data)

    return {
        "Sprint_Completion": sprint_completion_df,
        "Task_Status_Breakdown": task_status_breakdown,
        "High_Priority_Blockers": blockers_df,
        "Burn_Down_Placeholder": burn_down_df,
    }


def create_sprint_progress_dashboard_by_sprint(df: pd.DataFrame):
    """
    Create data frames for *each* sprint, excluding High Priority Blockers.
    We compute:
      - Sprint Completion Rate (per sprint)
      - Task Status Breakdown (per sprint)
      - Burn-down Placeholder (per sprint)

    Returns a dict of 3 DataFrames:
      1. Completion_by_Sprint
      2. Task_Status_by_Sprint
      3. BurnDown_by_Sprint
    """
    # Get all distinct sprint names (ignore null)
    sprints = df["last_sprint"].dropna().unique()

    # 1. Completion by Sprint
    completion_rows = []
    for sprint in sprints:
        sprint_tasks = df[df["last_sprint"] == sprint]
        planned = len(sprint_tasks)
        completed = len(
            sprint_tasks[
                sprint_tasks["status"].str.lower().str.contains("done", na=False)
            ],
        )
        rate = (completed / planned * 100) if planned else 0
        completion_rows.append(
            {
                "Sprint": sprint,
                "Planned Tasks": planned,
                "Completed Tasks": completed,
                "Completion Rate (%)": round(rate, 2),
            },
        )
    completion_df = pd.DataFrame(completion_rows)

    # 2. Task Status Breakdown by Sprint
    status_rows = []
    for sprint in sprints:
        sprint_tasks = df[df["last_sprint"] == sprint]
        grouped = sprint_tasks.groupby("status")["key"].count()
        for status_val, count_val in grouped.items():
            status_rows.append(
                {
                    "Sprint": sprint,
                    "Status": status_val,
                    "Count": count_val,
                },
            )
    status_df = pd.DataFrame(status_rows)

    # 3. Burn-down Placeholder by Sprint
    #    We'll produce the same fixed Day/Remaining pattern for each sprint,
    #    just to demonstrate how you'd structure it for each sprint.
    burndown_rows = []
    for sprint in sprints:
        for day, remaining in zip(
            ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5"],
            [40, 30, 25, 10, 0],
        ):
            burndown_rows.append(
                {
                    "Sprint": sprint,
                    "Day": day,
                    "Remaining Tasks": remaining,
                },
            )
    burndown_df = pd.DataFrame(burndown_rows)

    return {
        "Completion_by_Sprint": completion_df,
        "Task_Status_by_Sprint": status_df,
        "BurnDown_by_Sprint": burndown_df,
    }


def create_team_productivity_workload_dashboard(df: pd.DataFrame):
    """
    Create data frames/tables for:
      1. Average Task Completion Time (Days)
      2. Developer Workload (Task count per assignee)
      3. Bug vs. Feature Ratio
    """

    # -- 1. Average Task Completion Time -------------------------------------
    done_df = df[
        df["status"].str.lower().str.contains("done", na=False)
        & df["resolved_at"].notnull()
    ].copy()

    # Ensure columns are datetime (already done in main, but just in case).
    if done_df["created_at"].dtype == object:
        done_df["created_at"] = pd.to_datetime(
            done_df["created_at"],
            utc=True,
            errors="coerce",
        )
    if done_df["resolved_at"].dtype == object:
        done_df["resolved_at"] = pd.to_datetime(
            done_df["resolved_at"],
            utc=True,
            errors="coerce",
        )

    # Calculate the difference in days
    done_df["completion_days"] = (
        done_df["resolved_at"] - done_df["created_at"]
    ).dt.days
    avg_completion_time = done_df["completion_days"].mean() if not done_df.empty else 0

    avg_completion_data = {
        "Metric": ["Average Task Completion Time (days)"],
        "Value": [round(avg_completion_time, 2)],
    }
    avg_completion_df = pd.DataFrame(avg_completion_data)

    # -- 2. Developer Workload (Task count per assignee) ---------------------
    workload_df = df.groupby("assignee")["key"].count().reset_index()
    workload_df.columns = ["Assignee", "Task Count"]

    # -- 3. Bug vs. Feature Ratio --------------------------------------------
    bug_count = len(df[df["task_type"].str.lower() == "bug"])
    feature_count = len(df[df["task_type"].str.lower().isin(["story", "task"])])

    bug_vs_feature = {
        "Type": ["Bug", "Feature"],
        "Count": [bug_count, feature_count],
    }
    bug_vs_feature_df = pd.DataFrame(bug_vs_feature)

    return {
        "Avg_Completion_Time": avg_completion_df,
        "Developer_Workload": workload_df,
        "Bug_vs_Feature": bug_vs_feature_df,
    }


def main():
    # 1) Fetch tasks from Jira
    tasks = get_tasks_info()
    df = pd.DataFrame(tasks)

    # 2) Convert date columns to datetime with UTC
    datetime_columns = [
        "created_at",
        "updated_at",
        "resolved_at",
        "target_start",
        "target_end",
    ]
    for col in datetime_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    # 3) Build the dashboards (overall + per-sprint)
    sprint_progress_data = create_sprint_progress_dashboard(df)
    sprint_progress_per_sprint = create_sprint_progress_dashboard_by_sprint(df)
    team_productivity_data = create_team_productivity_workload_dashboard(df)

    # 4) Strip timezone (Excel doesn't allow TZ-aware datetimes)
    for col in datetime_columns:
        if col in df.columns and pd.api.types.is_datetime64tz_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

    # Also remove timezone in each sub-DataFrame
    for subdata in sprint_progress_data.values():
        for col in subdata.columns:
            if pd.api.types.is_datetime64tz_dtype(subdata[col]):
                subdata[col] = subdata[col].dt.tz_localize(None)

    for subdata in sprint_progress_per_sprint.values():
        for col in subdata.columns:
            if pd.api.types.is_datetime64tz_dtype(subdata[col]):
                subdata[col] = subdata[col].dt.tz_localize(None)

    for subdata in team_productivity_data.values():
        for col in subdata.columns:
            if pd.api.types.is_datetime64tz_dtype(subdata[col]):
                subdata[col] = subdata[col].dt.tz_localize(None)

    # 5) Sanitize string columns to remove illegal XML characters
    df = sanitize_dataframe(df)
    for key, sdf in sprint_progress_data.items():
        sprint_progress_data[key] = sanitize_dataframe(sdf)
    for key, sdf in sprint_progress_per_sprint.items():
        sprint_progress_per_sprint[key] = sanitize_dataframe(sdf)
    for key, sdf in team_productivity_data.items():
        team_productivity_data[key] = sanitize_dataframe(sdf)

    # 6) Write everything to Excel (multiple sheets)
    current_date = datetime.now().strftime("%Y-%m-%d")
    filename = f"jira_tasks_{current_date}.xlsx"

    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        # -- Sheet: Raw Data (All Tasks)
        df.to_excel(writer, sheet_name="All_Tasks", index=False)

        # -- Overall Sprint Progress Dashboard
        sprint_progress_data["Sprint_Completion"].to_excel(
            writer,
            sheet_name="Sprint_Completion",
            index=False,
        )
        sprint_progress_data["Task_Status_Breakdown"].to_excel(
            writer,
            sheet_name="Status_Breakdown",
            index=False,
        )
        sprint_progress_data["High_Priority_Blockers"].to_excel(
            writer,
            sheet_name="High_Priority_Blockers",
            index=False,
        )
        sprint_progress_data["Burn_Down_Placeholder"].to_excel(
            writer,
            sheet_name="BurnDown_Placeholder",
            index=False,
        )

        # -- Per-Sprint Dashboard (no High Priority Blockers)
        sprint_progress_per_sprint["Completion_by_Sprint"].to_excel(
            writer,
            sheet_name="Completion_by_Sprint",
            index=False,
        )
        sprint_progress_per_sprint["Task_Status_by_Sprint"].to_excel(
            writer,
            sheet_name="Task_Status_by_Sprint",
            index=False,
        )
        sprint_progress_per_sprint["BurnDown_by_Sprint"].to_excel(
            writer,
            sheet_name="BurnDown_by_Sprint",
            index=False,
        )

        # -- Team Productivity & Workload
        team_productivity_data["Avg_Completion_Time"].to_excel(
            writer,
            sheet_name="Avg_Completion_Time",
            index=False,
        )
        team_productivity_data["Developer_Workload"].to_excel(
            writer,
            sheet_name="Developer_Workload",
            index=False,
        )
        team_productivity_data["Bug_vs_Feature"].to_excel(
            writer,
            sheet_name="Bug_vs_Feature_Ratio",
            index=False,
        )

    LOGGER.info(f"Report generated: {filename}")


if __name__ == "__main__":
    main()
