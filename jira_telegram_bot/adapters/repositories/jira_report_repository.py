"""PostgreSQL repository implementation for Jira report data."""
from __future__ import annotations

import urllib
from datetime import datetime
from typing import List

import pandas as pd
from sqlalchemy import Column
from sqlalchemy import create_engine
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.jira_report import JiraIssueDetail
from jira_telegram_bot.entities.jira_report import LinkedIssue
from jira_telegram_bot.entities.jira_report import ProjectReport
from jira_telegram_bot.entities.jira_report import WorklogEntry
from jira_telegram_bot.settings import POSTGRES_SETTINGS
from jira_telegram_bot.use_cases.interfaces.jira_report_repository_interface import JiraReportRepositoryInterface

Base = declarative_base()


class JiraTaskModel(Base):
    """SQLAlchemy ORM model for Jira tasks with comprehensive fields."""

    __tablename__ = "jira_tasks_enhanced"

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
    release = Column(ARRAY(String), nullable=True)
    original_estimate = Column(Text, nullable=True)
    remaining_estimate = Column(Text, nullable=True)
    worklog_entries = Column(JSON, nullable=True)
    linked_issues = Column(JSON, nullable=True)
    last_synced = Column(DateTime, nullable=True)


class JiraReportRepository(JiraReportRepositoryInterface):
    """PostgreSQL implementation of Jira report repository."""

    def __init__(self) -> None:
        """Initialize the repository with database connection."""
        self._engine = self._create_engine()
        self._session_maker = sessionmaker(bind=self._engine)
        self._ensure_schema_exists()

    def _create_engine(self):
        """Create SQLAlchemy engine with PostgreSQL connection."""
        encoded_password = urllib.parse.quote_plus(POSTGRES_SETTINGS.db_password)
        database_url = (
            f"postgresql://{POSTGRES_SETTINGS.db_user}:"
            f"{encoded_password}@{POSTGRES_SETTINGS.db_host}:"
            f"{POSTGRES_SETTINGS.db_port}/{POSTGRES_SETTINGS.db_name}"
        )
        return create_engine(database_url)

    def _ensure_schema_exists(self) -> None:
        """Ensure the database schema exists and is up to date."""
        try:
            Base.metadata.create_all(self._engine)
            LOGGER.info("Database schema ensured for enhanced Jira tasks")
        except Exception as e:
            LOGGER.error(f"Failed to ensure database schema: {e}")
            raise

    async def store_issues(self, issues: List[JiraIssueDetail]) -> None:
        """Store or update issues in the database.
        
        Args:
            issues: List of Jira issue details to store.
        """
        if not issues:
            return

        session = self._session_maker()
        try:
            for issue in issues:
                task_model = self._convert_to_model(issue)
                session.merge(task_model)
            
            session.commit()
            LOGGER.info(f"Stored {len(issues)} issues in database")
            
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Failed to store issues: {e}")
            raise
        finally:
            session.close()

    async def get_project_report(self, project_key: str) -> ProjectReport:
        """Retrieve a project report.
        
        Args:
            project_key: The Jira project key.
            
        Returns:
            Complete project report with all issues.
        """
        session = self._session_maker()
        try:
            tasks = session.query(JiraTaskModel).filter(
                JiraTaskModel.key.like(f"{project_key}-%")
            ).all()
            
            issues = [self._convert_from_model(task) for task in tasks]
            
            return ProjectReport(
                project_key=project_key,
                generated_at=datetime.now(),
                total_issues=len(issues),
                issues=issues,
            )
            
        except Exception as e:
            LOGGER.error(f"Failed to get project report for {project_key}: {e}")
            raise
        finally:
            session.close()

    async def get_issues_by_keys(self, issue_keys: List[str]) -> List[JiraIssueDetail]:
        """Retrieve specific issues by their keys.
        
        Args:
            issue_keys: List of issue keys to retrieve.
            
        Returns:
            List of matching issue details.
        """
        if not issue_keys:
            return []

        session = self._session_maker()
        try:
            tasks = session.query(JiraTaskModel).filter(
                JiraTaskModel.key.in_(issue_keys)
            ).all()
            
            return [self._convert_from_model(task) for task in tasks]
            
        except Exception as e:
            LOGGER.error(f"Failed to get issues by keys: {e}")
            raise
        finally:
            session.close()

    def _convert_to_model(self, issue: JiraIssueDetail) -> JiraTaskModel:
        """Convert issue entity to SQLAlchemy model.
        
        Args:
            issue: Issue entity to convert.
            
        Returns:
            SQLAlchemy model instance.
        """
        worklog_data = [entry.model_dump() for entry in issue.worklog_entries]
        linked_data = [link.model_dump() for link in issue.linked_issues]

        return JiraTaskModel(
            key=issue.key,
            summary=issue.summary,
            description=issue.description,
            epic_name=issue.epic_name,
            comments=issue.comments,
            task_type=issue.task_type,
            assignee=issue.assignee,
            reporter=issue.reporter,
            priority=issue.priority,
            status=issue.status,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            resolved_at=issue.resolved_at,
            target_start=issue.target_start,
            target_end=issue.target_end,
            story_points=issue.story_points,
            components=issue.components,
            labels=issue.labels,
            last_sprint=issue.last_sprint,
            sprint_repeats=issue.sprint_repeats,
            release=issue.release,
            original_estimate=issue.original_estimate,
            remaining_estimate=issue.remaining_estimate,
            worklog_entries=worklog_data,
            linked_issues=linked_data,
            last_synced=datetime.now(),
        )

    def _convert_from_model(self, model: JiraTaskModel) -> JiraIssueDetail:
        """Convert SQLAlchemy model to issue entity.
        
        Args:
            model: SQLAlchemy model instance.
            
        Returns:
            Issue entity.
        """
        worklog_entries = []
        if model.worklog_entries:
            worklog_entries = [
                WorklogEntry(**entry) for entry in model.worklog_entries
            ]

        linked_issues = []
        if model.linked_issues:
            linked_issues = [
                LinkedIssue(**link) for link in model.linked_issues
            ]

        return JiraIssueDetail(
            key=model.key,
            summary=model.summary or "",
            description=model.description,
            epic_name=model.epic_name,
            comments=model.comments or "",
            task_type=model.task_type or "",
            assignee=model.assignee,
            reporter=model.reporter or "",
            priority=model.priority,
            status=model.status or "",
            created_at=model.created_at or datetime.now(),
            updated_at=model.updated_at or datetime.now(),
            resolved_at=model.resolved_at,
            target_start=model.target_start,
            target_end=model.target_end,
            story_points=model.story_points,
            components=model.components or [],
            labels=model.labels or [],
            last_sprint=model.last_sprint or "Backlog",
            sprint_repeats=model.sprint_repeats or 0,
            release=model.release or [],
            original_estimate=model.original_estimate,
            remaining_estimate=model.remaining_estimate,
            worklog_entries=worklog_entries,
            linked_issues=linked_issues,
        )
