from __future__ import annotations

import urllib

import pandas as pd
from sqlalchemy import Column
from sqlalchemy import create_engine
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraRepository
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.settings import POSTGRES_SETTINGS

DB_USER = POSTGRES_SETTINGS.db_user
DB_PASSWORD = POSTGRES_SETTINGS.db_password
DB_HOST = POSTGRES_SETTINGS.db_host
DB_PORT = POSTGRES_SETTINGS.db_port
DB_NAME = POSTGRES_SETTINGS.db_name

encoded_password = urllib.parse.quote_plus(DB_PASSWORD)

DATABASE_URL = (
    f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

Base = declarative_base()


def ensure_schema_updates():
    """
    Dynamically adds the new columns to the 'jira_tasks' table if they
    do not exist already. This way, we avoid manual migration steps.
    """
    with engine.begin() as conn:
        # Add 'release' (array of text) if not exists
        conn.execute(
            text("ALTER TABLE jira_tasks ADD COLUMN IF NOT EXISTS release text[];"),
        )
        # Add 'original_estimate' (text) if not exists
        conn.execute(
            text(
                "ALTER TABLE jira_tasks ADD COLUMN IF NOT EXISTS original_estimate text;",
            ),
        )
        # Add 'remaining_estimate' (text) if not exists
        conn.execute(
            text(
                "ALTER TABLE jira_tasks ADD COLUMN IF NOT EXISTS remaining_estimate text;",
            ),
        )


class Task(Base):
    """
    SQLAlchemy ORM model for Jira tasks.
    The Jira `key` is the primary key, so duplicates will be updated.
    """

    __tablename__ = "jira_tasks"

    key = Column(String, primary_key=True)
    summary = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    epic_name = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)
    task_type = Column(String, nullable=True)
    assignee = Column(String, nullable=True)
    reporter = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    target_start = Column(DateTime, nullable=True)
    target_end = Column(DateTime, nullable=True)
    story_points = Column(Float, nullable=True)
    components = Column(ARRAY(String), nullable=True)
    labels = Column(ARRAY(String), nullable=True)
    last_sprint = Column(String, nullable=True)
    sprint_repeats = Column(Integer, nullable=True)

    # Newly added columns:
    release = Column(ARRAY(String), nullable=True)
    original_estimate = Column(Text, nullable=True)
    remaining_estimate = Column(Text, nullable=True)


# 1. Ensure the existing table has the new columns (migration in code)
ensure_schema_updates()

# 2. Reflect updated metadata & create any missing tables
#    (If the table doesn't exist at all, this will create it; if it does, we're good)
Base.metadata.create_all(engine)

jira_repository = JiraRepository(settings=JIRA_SETTINGS)


def get_tasks_info(project_key: str) -> list[dict]:
    """
    Retrieve tasks for a given Jira project.
    """
    LOGGER.info(f"Fetching issues for project: {project_key}")
    start_at = 0
    max_results = 100
    issues = []

    while True:
        # Adjust your JQL to filter as needed
        batch = jira_repository.jira.search_issues(
            f"project = {project_key}",
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
    LOGGER.info(f"Found {len(issues)} issues for project {project_key}")
    epics = {}

    # First pass: store epic names
    for issue in issues:
        if issue.fields.issuetype.name == "Epic":
            epics[issue.key] = issue.fields.summary

    # Second pass: gather tasks
    for issue in tqdm(issues, desc=f"Processing {project_key} issues"):
        if issue.fields.issuetype.name == "Epic":
            continue

        # Gather comments
        comments_text = []
        if issue.fields.comment:
            for comment in issue.fields.comment.comments:
                commenter = comment.author.displayName
                if commenter != issue.fields.reporter.displayName:
                    comments_text.append(f"{commenter}: {comment.body}")

        # Extract sprint info
        sprint_field = getattr(issue.fields, "customfield_10104", None)
        if sprint_field and len(sprint_field) > 0:
            sprint_str = str(sprint_field[-1])
            name_start = sprint_str.find("name=") + 5
            name_end = sprint_str.find(",startDate")
            last_sprint_name = sprint_str[name_start:name_end]
        else:
            last_sprint_name = "Backlog"
        sprint_count = len(sprint_field) if sprint_field else 0

        # Extract story points
        story_points = getattr(issue.fields, "customfield_10106", None)

        # Extract fixVersions -> store as "release"
        fix_versions = issue.fields.fixVersions
        release_list = [fv.name for fv in fix_versions] if fix_versions else []

        # Extract time-tracking estimates
        # Note: 'originalEstimate' or 'remainingEstimate' might be None or strings like "2h", "3d", etc.
        timetracking = getattr(issue.fields, "timetracking", None)
        if timetracking:
            original_estimate = getattr(timetracking, "originalEstimate", None)
            remaining_estimate = getattr(timetracking, "remainingEstimate", None)
        else:
            original_estimate = None
            remaining_estimate = None

        task_info = {
            "key": issue.key,
            "summary": issue.fields.summary,
            "description": issue.fields.description or "",
            "epic_name": epics.get(issue.fields.customfield_10100),
            "comments": "\n".join(comments_text),
            "task_type": issue.fields.issuetype.name,
            "assignee": (
                issue.fields.assignee.displayName if issue.fields.assignee else None
            ),
            "reporter": issue.fields.reporter.displayName,
            "priority": (issue.fields.priority.name if issue.fields.priority else None),
            "status": issue.fields.status.name,
            "created_at": issue.fields.created,
            "updated_at": issue.fields.updated,
            "resolved_at": issue.fields.resolutiondate,
            "target_start": getattr(issue.fields, "customfield_10109", None),
            "target_end": getattr(issue.fields, "customfield_10110", None),
            "story_points": story_points,
            "components": (
                [c.name for c in issue.fields.components]
                if issue.fields.components
                else []
            ),
            "labels": issue.fields.labels if issue.fields.labels else [],
            "last_sprint": last_sprint_name,
            "sprint_repeats": sprint_count,
            "release": release_list,  # new field
            "original_estimate": original_estimate,  # new field
            "remaining_estimate": remaining_estimate,  # new field
        }
        tasks_info.append(task_info)

    return tasks_info


def store_tasks_in_db(tasks: list[dict]):
    """
    Upsert the list of task dicts into the database:
    - If the `key` already exists, update that row.
    - Otherwise, insert a new row.
    """
    for t in tasks:
        # Convert string datetimes to Python datetime objects if needed
        for time_field in [
            "created_at",
            "updated_at",
            "resolved_at",
            "target_start",
            "target_end",
        ]:
            if t[time_field]:
                try:
                    t[time_field] = pd.to_datetime(t[time_field])
                except Exception:
                    t[time_field] = None

        # Build the Task object
        task_obj = Task(
            key=t["key"],
            summary=t["summary"],
            description=t["description"],
            epic_name=t["epic_name"],
            comments=t["comments"],
            task_type=t["task_type"],
            assignee=t["assignee"],
            reporter=t["reporter"],
            priority=t["priority"],
            status=t["status"],
            created_at=t["created_at"],
            updated_at=t["updated_at"],
            resolved_at=t["resolved_at"],
            target_start=t["target_start"],
            target_end=t["target_end"],
            story_points=t["story_points"],
            components=t["components"],
            labels=t["labels"],
            last_sprint=t["last_sprint"],
            sprint_repeats=t["sprint_repeats"],
            release=t["release"],
            original_estimate=t["original_estimate"],
            remaining_estimate=t["remaining_estimate"],
        )

        # Merge = insert if new, update if primary key exists
        session.merge(task_obj)

    session.commit()
    LOGGER.info(f"Upserted {len(tasks)} tasks into the database.")


if __name__ == "__main__":
    # Example usage:
    parschat_tasks = get_tasks_info("PARSCHAT")

    pct_tasks = get_tasks_info("PCT")

    all_tasks = parschat_tasks + pct_tasks

    df = pd.DataFrame(all_tasks)
    LOGGER.info(f"DataFrame shape: {df.shape}")

    store_tasks_in_db(all_tasks)
    LOGGER.info("Tasks have been stored (upserted) in the PostgreSQL database.")
