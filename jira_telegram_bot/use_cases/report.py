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
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.jira_server_repository import JiraRepository
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


class Task(Base):
    """
    SQLAlchemy ORM model for Jira tasks.
    The Jira `key` is now the primary key, so duplicates will be updated.
    """

    __tablename__ = "jira_tasks"

    # Make `key` the primary key
    key = Column(String, primary_key=True)  # <--- Primary key

    # Other fields
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


# Create the table if it doesn't exist
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
        for comment in issue.fields.comment.comments:
            commenter = comment.author.displayName
            if commenter != issue.fields.reporter.displayName:
                comments_text.append(f"{commenter}: {comment.body}")

        # Extract sprint information
        sprint_field = getattr(issue.fields, "customfield_10104", None)
        if sprint_field and len(sprint_field) > 0:
            sprint_str = str(sprint_field[-1])
            name_start = sprint_str.find("name=") + 5
            name_end = sprint_str.find(",startDate")
            last_sprint_name = sprint_str[name_start:name_end]
        else:
            last_sprint_name = "Backlog"
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
            "components": [c.name for c in issue.fields.components]
            if issue.fields.components
            else [],
            "labels": issue.fields.labels if issue.fields.labels else [],
            "last_sprint": last_sprint_name,
            "sprint_repeats": sprint_count,
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

        # Create a Task object
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
        )

        # Merge will insert if the primary key doesn't exist,
        # or update if it does exist
        session.merge(task_obj)

    session.commit()
    LOGGER.info(f"Upserted {len(tasks)} tasks into the database.")


if __name__ == "__main__":
    # 1. Fetch tasks from PARSCHAT
    parschat_tasks = get_tasks_info("PARSCHAT")

    # 2. Fetch tasks from PCT
    pct_tasks = get_tasks_info("PCT")

    # Combine them into one list if you like
    all_tasks = parschat_tasks + pct_tasks

    # 3. Convert to DataFrame (for debugging or exporting)
    df = pd.DataFrame(all_tasks)

    # If needed, ensure date/datetime columns are properly converted for the DataFrame
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
            # Format for external usage (e.g., CSV/Excel)
            df[col] = df[col].apply(
                lambda x: x.strftime("%Y-%m-%d %H:%M:%S%z") if pd.notnull(x) else None,
            )

    # 5. Store in PostgreSQL via SQLAlchemy (upsert)
    store_tasks_in_db(all_tasks)
    LOGGER.info("Tasks have been stored (upserted) in the PostgreSQL database.")
