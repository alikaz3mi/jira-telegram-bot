from __future__ import annotations

from datetime import datetime

import pandas as pd
from tqdm import tqdm

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.jira_server_repository import JiraRepository
from jira_telegram_bot.settings import JIRA_SETTINGS

jira_repository = JiraRepository(settings=JIRA_SETTINGS)


def format_datetime(value):
    """Convert Jira datetime to PostgreSQL-compatible format."""
    if value:
        return pd.to_datetime(value).strftime("%Y-%m-%d %H:%M:%S%z")
    return None


def get_tasks_info():
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
    tasks_info = []
    LOGGER.info(f"Found {len(issues)} issues")
    epics = {}

    for issue in issues:
        if issue.fields.issuetype.name == "Epic":
            epics[issue.key] = issue.fields.summary
    for issue in tqdm(issues):
        if issue.fields.issuetype.name == "Epic":
            continue
        comments_text = []
        for comment in issue.fields.comment.comments:
            commenter = comment.author.displayName
            if commenter != issue.fields.reporter.displayName:
                comments_text.append(f"{commenter}: {comment.body}")

        # Get sprint information
        sprint_field = getattr(issue.fields, "customfield_10104", None)
        # Extract sprint information from the string representation
        if sprint_field and len(sprint_field) > 0:
            sprint_str = str(sprint_field[-1])
            # Extract name between name= and ,startDate
            name_start = sprint_str.find("name=") + 5
            name_end = sprint_str.find(",startDate")
            last_sprint_name = sprint_str[name_start:name_end]
        else:
            last_sprint_name = None
        sprint_count = len(sprint_field) if sprint_field else 0

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
            "reporter": issue.fields.reporter.displayName,
            "priority": issue.fields.priority.name if issue.fields.priority else None,
            "status": issue.fields.status.name,
            "created_at": issue.fields.created,
            "updated_at": issue.fields.updated,
            "resolved_at": issue.fields.resolutiondate,
            "target_start": getattr(issue.fields, "customfield_10109", None),
            "target_end": getattr(issue.fields, "customfield_10110", None),
            "story_points": story_points,
            # 'components': [c.name for c in issue.fields.components],
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


if __name__ == "__main__":
    tasks = get_tasks_info()
    df = pd.DataFrame(tasks)
    datetime_columns = [
        "created_at",
        "updated_at",
        "resolved_at",
        "target_start",
        "target_end",
    ]
    for col in datetime_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df[col] = df[col].apply(
                lambda x: x.strftime("%Y-%m-%d %H:%M:%S%z") if pd.notnull(x) else None,
            )

    current_date = datetime.now().strftime("%Y-%m-%d")
    filename = f"jira_tasks_{current_date}.csv"

    df.to_excel("jira_tasks.xlsx", sheet_name="tasks", index=False)
    LOGGER.info(f"Tasks exported to {filename}")
