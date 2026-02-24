"""PostgreSQL repository implementation for Jira report data."""
from __future__ import annotations

import urllib
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.jira_report import JiraIssueDetail
from jira_telegram_bot.entities.jira_report import LinkedIssue
from jira_telegram_bot.entities.jira_report import ProjectReport
from jira_telegram_bot.entities.jira_report import WorklogEntry
from jira_telegram_bot.entities.sync_status import SyncStatus
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface
from jira_telegram_bot.use_cases.interfaces.jira_report_repository_interface import JiraReportRepositoryInterface

Base = declarative_base()


class JiraTaskModel(Base):
    """SQLAlchemy ORM model for Jira tasks with comprehensive fields."""

    __tablename__ = "jira_tasks_enhanced"

    key = Column(String, primary_key=True)
    summary = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    epic_name = Column(Text, nullable=True)
    epic_link = Column(String, nullable=True)
    comments = Column(Text, nullable=True)
    task_type = Column(String, nullable=True)
    assignee = Column(String, nullable=True)
    reporter = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    target_start = Column(DateTime, nullable=True)
    target_end = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    actual_start_date = Column(DateTime, nullable=True)
    actual_end_date = Column(DateTime, nullable=True)
    project = Column(String, nullable=True)
    story_points = Column(Float, nullable=True)
    components = Column(ARRAY(String), nullable=True)
    labels = Column(ARRAY(String), nullable=True)
    last_sprint = Column(String, nullable=True)
    all_sprints = Column(ARRAY(String), nullable=True)
    sprint_repeats = Column(Integer, nullable=True)
    release = Column(ARRAY(String), nullable=True)
    original_estimate = Column(Text, nullable=True)
    remaining_estimate = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    delay_reason = Column(Text, nullable=True)
    fix_versions = Column(ARRAY(String), nullable=True)
    affected_versions = Column(ARRAY(String), nullable=True)
    worklog_entries = Column(JSON, nullable=True)
    linked_issues = Column(JSON, nullable=True)
    last_synced = Column(DateTime, nullable=True)


class SyncStatusModel(Base):
    """SQLAlchemy ORM model for sync status tracking."""

    __tablename__ = "sync_status"

    project_key = Column(String, primary_key=True)
    last_full_sync = Column(DateTime, nullable=True)
    last_incremental_sync = Column(DateTime, nullable=True)
    last_sync_status = Column(String(20), nullable=False, default="never_synced")
    issues_synced = Column(Integer, nullable=False, default=0)
    issues_failed = Column(Integer, nullable=False, default=0)
    sync_duration_seconds = Column(Float, nullable=True)
    errors = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class JiraReportRepository(JiraReportRepositoryInterface):
    """PostgreSQL implementation of Jira report repository."""

    def __init__(self, db_connection: DatabaseConnectionInterface) -> None:
        """Initialize the repository with database connection."""
        self.db_connection = db_connection
        self._ensure_schema_exists()

    def _ensure_schema_exists(self) -> None:
        """Ensure the database schema exists."""
        try:
            Base.metadata.create_all(self.db_connection.get_engine())
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

        session = self.db_connection.get_session()
        try:
            for issue in issues:
                task_model = self._convert_to_model(issue)
                session.merge(task_model)
                
                # Flush to ensure task exists before inserting status history
                session.flush()
                
                # Store status changes in history table
                if issue.status_changes:
                    # Delete existing history for this issue
                    session.execute(
                        text("DELETE FROM jira_status_history WHERE issue_key = :key"),
                        {"key": issue.key}
                    )
                    
                    # Insert new status changes
                    for change in issue.status_changes:
                        session.execute(
                            text("""
                                INSERT INTO jira_status_history 
                                (issue_key, from_status, to_status, changed_at, changed_by, project)
                                VALUES (:issue_key, :from_status, :to_status, :changed_at, :changed_by, :project)
                            """),
                            {
                                "issue_key": issue.key,
                                "from_status": change.from_status,
                                "to_status": change.to_status,
                                "changed_at": change.changed_at,
                                "changed_by": change.changed_by,
                                "project": change.project,
                            },
                        )
            
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
        session = self.db_connection.get_session()
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

        session = self.db_connection.get_session()
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

    def _serialize_worklog_entry(self, entry: WorklogEntry) -> dict:
        """Serialize WorklogEntry to dict with datetime conversion.
        
        Args:
            entry: WorklogEntry to serialize.
            
        Returns:
            Dictionary with datetime objects converted to ISO strings.
        """
        # Use mode='json' to ensure proper datetime serialization
        return entry.model_dump(mode='json')

    def _deserialize_worklog_entry(self, data: dict) -> WorklogEntry:
        """Deserialize dict to WorklogEntry with datetime conversion.
        
        Args:
            data: Dictionary with datetime fields as ISO strings.
            
        Returns:
            WorklogEntry instance.
        """
        # Convert ISO format strings back to datetime objects
        for field in ['created', 'updated', 'started']:
            if field in data and data[field] is not None:
                if isinstance(data[field], str):
                    try:
                        data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                    except ValueError:
                        # Fallback for invalid date strings
                        data[field] = datetime.now()
        return WorklogEntry(**data)

    def _convert_to_model(self, issue: JiraIssueDetail) -> JiraTaskModel:
        """Convert issue entity to SQLAlchemy model.
        
        Args:
            issue: Issue entity to convert.
            
        Returns:
            SQLAlchemy model instance.
        """
        worklog_data = [self._serialize_worklog_entry(entry) for entry in issue.worklog_entries]
        linked_data = [link.model_dump(mode='json') for link in issue.linked_issues]

        return JiraTaskModel(
            key=issue.key,
            summary=issue.summary,
            description=issue.description,
            epic_name=issue.epic_name,
            epic_link=issue.epic_link,
            comments=issue.comments,
            task_type=issue.task_type,
            assignee=issue.assignee,
            reporter=issue.reporter,
            priority=issue.priority,
            status=issue.status,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            resolved_at=issue.resolved_at,
            reviewed_at=issue.reviewed_at,
            target_start=issue.target_start,
            target_end=issue.target_end,
            due_date=issue.due_date,
            actual_start_date=issue.actual_start_date,
            actual_end_date=issue.actual_end_date,
            project=issue.project,
            story_points=issue.story_points,
            components=issue.components,
            labels=issue.labels,
            last_sprint=issue.last_sprint,
            all_sprints=issue.all_sprints,
            sprint_repeats=issue.sprint_repeats,
            release=issue.release,
            original_estimate=issue.original_estimate,
            remaining_estimate=issue.remaining_estimate,
            root_cause=issue.root_cause,
            delay_reason=issue.delay_reason,
            fix_versions=issue.fix_versions,
            affected_versions=issue.affected_versions,
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
                self._deserialize_worklog_entry(entry) for entry in model.worklog_entries
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
            epic_link=model.epic_link,
            comments=model.comments or "",
            task_type=model.task_type or "",
            assignee=model.assignee,
            reporter=model.reporter or "",
            priority=model.priority,
            status=model.status or "",
            created_at=model.created_at or datetime.now(),
            updated_at=model.updated_at or datetime.now(),
            resolved_at=model.resolved_at,
            reviewed_at=model.reviewed_at,
            target_start=model.target_start,
            target_end=model.target_end,
            due_date=model.due_date,
            actual_start_date=model.actual_start_date,
            actual_end_date=model.actual_end_date,
            project=model.project,
            story_points=model.story_points,
            components=model.components or [],
            labels=model.labels or [],
            last_sprint=model.last_sprint or "Backlog",
            all_sprints=model.all_sprints or [],
            sprint_repeats=model.sprint_repeats or 0,
            release=model.release or [],
            original_estimate=model.original_estimate,
            remaining_estimate=model.remaining_estimate,
            root_cause=model.root_cause,
            delay_reason=model.delay_reason,
            fix_versions=model.fix_versions or [],
            affected_versions=model.affected_versions or [],
            worklog_entries=worklog_entries,
            linked_issues=linked_issues,
        )

    async def get_sync_status(self, project_key: str) -> Optional[SyncStatus]:
        """Retrieve sync status for a project.
        
        Args:
            project_key: The Jira project key.
            
        Returns:
            Sync status if exists, None otherwise.
        """
        session = self.db_connection.get_session()
        try:
            model = session.query(SyncStatusModel).filter(
                SyncStatusModel.project_key == project_key
            ).first()
            
            if not model:
                return None
            
            return SyncStatus(
                project_key=model.project_key,
                last_full_sync=model.last_full_sync,
                last_incremental_sync=model.last_incremental_sync,
                last_sync_status=model.last_sync_status,
                issues_synced=model.issues_synced,
                issues_failed=model.issues_failed,
                sync_duration_seconds=model.sync_duration_seconds,
                errors=model.errors,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            
        except Exception as e:
            LOGGER.error(f"Failed to get sync status for {project_key}: {e}")
            raise
        finally:
            session.close()

    async def update_sync_status(self, sync_status: SyncStatus) -> None:
        """Update sync status for a project.
        
        Args:
            sync_status: Updated sync status to store.
        """
        session = self.db_connection.get_session()
        try:
            model = SyncStatusModel(
                project_key=sync_status.project_key,
                last_full_sync=sync_status.last_full_sync,
                last_incremental_sync=sync_status.last_incremental_sync,
                last_sync_status=sync_status.last_sync_status,
                issues_synced=sync_status.issues_synced,
                issues_failed=sync_status.issues_failed,
                sync_duration_seconds=sync_status.sync_duration_seconds,
                errors=sync_status.errors,
                created_at=sync_status.created_at,
                updated_at=datetime.now(),
            )
            
            session.merge(model)
            session.commit()
            LOGGER.info(f"Updated sync status for {sync_status.project_key}")
            
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Failed to update sync status: {e}")
            raise
        finally:
            session.close()
