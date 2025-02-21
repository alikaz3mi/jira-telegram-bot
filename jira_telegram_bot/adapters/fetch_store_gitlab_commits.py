from __future__ import annotations

import re
import urllib.parse
from datetime import datetime
from datetime import timedelta

import gitlab
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import create_engine
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings import GITLAB_SETTINGS
from jira_telegram_bot.settings import POSTGRES_SETTINGS

Base = declarative_base()


def is_conventional_commit(message: str) -> bool:
    """
    Return True if the commit message follows Conventional Commits format.
    e.g., feat: fix: docs: style: refactor: perf: test: build: ci: chore: revert:
    optionally with (scope).
    """
    pattern = r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(\S+\))?: .{1,}"
    return re.match(pattern, message) is not None


class GitCommit(Base):
    """
    SQLAlchemy model for storing commit information in the 'git_commit' table.
    commit_id (the SHA) is the primary key.
    """

    __tablename__ = "git_commit"

    commit_id = Column(String, primary_key=True)
    repository = Column(String, nullable=False)
    committer_email = Column(String, nullable=False)
    committer_name = Column(String, nullable=True)
    commit_time = Column(DateTime, nullable=False)
    message = Column(Text, nullable=True)
    is_conventional = Column(Boolean, default=False)
    python_lines_changed = Column(Integer, default=0)  # total lines (+/-) in *.py files
    lines_added = Column(Integer, default=0)
    lines_removed = Column(Integer, default=0)
    # Add any other fields you deem important, e.g., commit.author_name, etc.


def create_db_session():
    """
    Creates a SQLAlchemy session based on PostgresSettings from .env
    """
    pg_settings = POSTGRES_SETTINGS
    encoded_password = urllib.parse.quote_plus(pg_settings.db_password)

    database_url = (
        f"postgresql://{pg_settings.db_user}:{encoded_password}"
        f"@{pg_settings.db_host}:{pg_settings.db_port}/{pg_settings.db_name}"
    )

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)  # create table(s) if not exist
    return Session()


def calculate_python_lines_changed(commit_obj) -> int:
    """
    Calculate how many lines are changed in .py files for a given commit.
    This function returns the total lines changed (sum of additions + deletions)
    for all Python files in this commit.
    """
    python_lines_changed = 0
    try:
        diffs = commit_obj.diff(get_all=True)
        for diff_item in diffs:
            new_path = diff_item.get("new_path", "")
            if new_path.endswith(".py"):
                # Count lines that start with '+' or '-', ignoring the diff headers
                diff_text = diff_item.get("diff", "")
                # A naive approach is to count lines starting with '+' or '-'
                # but skipping the lines that start with '+++ ' or '--- '
                lines = diff_text.split("\n")
                for line in lines:
                    if line.startswith("+++") or line.startswith("---"):
                        continue
                    if line.startswith("+") or line.startswith("-"):
                        python_lines_changed += 1
    except Exception as e:
        LOGGER.info(f"Error calculating python lines changed: {e}")
    return python_lines_changed


def fetch_and_store_commits():
    """
    Main function to:
    1. Connect to GitLab using settings from gitlab_settings.py
    2. Fetch commits from the last 3 months for all projects
    3. Store (upsert) them in the 'git_commit' table
    """
    session = create_db_session()
    gl_settings = GITLAB_SETTINGS

    # Connect to GitLab
    gl = gitlab.Gitlab(url=gl_settings.url, private_token=gl_settings.access_token)

    # We'll fetch commits since 3 months ago
    three_months_ago = datetime.utcnow() - timedelta(days=1)

    projects = gl.projects.list(all=True)
    LOGGER.info(
        f"Found {len(projects)} projects. Fetching commits since {three_months_ago.date()}...",
    )

    for project in tqdm(projects):
        if not (
            "parschat" in project.name.lower()
            or "schedule" in project.name.lower()
            or "auth" in project.name.lower()
        ):
            continue

        try:
            project_name = project.name
            # Use `query_parameters` to fetch commits since 3 months ago
            # `all=True` may return a large list, so consider paginating if needed
            commits = project.commits.list(
                all=True,
                query_parameters={
                    "since": three_months_ago.isoformat(),
                },
            )

            for c in commits:
                commit_id = c.id
                commit_time = datetime.fromisoformat(c.created_at)

                message = c.message
                email = c.author_email
                name = c.author_name
                conventional = is_conventional_commit(message)

                # lines added/removed from commit.stats
                # stats is an API call, so do c.stats if not already included
                full_commit = project.commits.get(c.id)
                c_stats = full_commit.stats or {}
                lines_added = c_stats.get("additions", 0)
                lines_removed = c_stats.get("deletions", 0)

                # Calculate Python lines changed
                python_lines_changed = calculate_python_lines_changed(c)

                git_commit_record = GitCommit(
                    commit_id=commit_id,
                    repository=project_name,
                    committer_email=email,
                    committer_name=name,
                    commit_time=commit_time,
                    message=message,
                    is_conventional=conventional,
                    python_lines_changed=python_lines_changed,
                    lines_added=lines_added,
                    lines_removed=lines_removed,
                )

                # Upsert (merge) by primary key (commit_id)
                session.merge(git_commit_record)
        except Exception as e:
            LOGGER.error(f"Error fetching commits for project {project_name}: {e}")

    session.commit()
    session.close()
    LOGGER.info("Done storing GitLab commits into the 'git_commit' table.")


if __name__ == "__main__":
    fetch_and_store_commits()
