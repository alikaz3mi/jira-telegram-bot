"""PostgreSQL repository for team evaluation data."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.declarative import declarative_base

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.team_evaluation import TeamEvaluationRow
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface
from jira_telegram_bot.use_cases.interfaces.team_evaluation_repository_interface import (
    TeamEvaluationRepositoryInterface,
)

Base = declarative_base()


class TeamEvaluationModel(Base):
    """SQLAlchemy model for team_evaluation table."""

    __tablename__ = "team_evaluation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Sprint and developer identification
    sprint_id = Column(Integer, nullable=False)
    sprint_name = Column(String(255), nullable=False)
    developer_name = Column(String(255), nullable=False)
    department = Column(String(100), nullable=False)
    project = Column(String(100), nullable=False)

    # Task counts
    development_count = Column(Integer, nullable=False, default=0)
    bug_count = Column(Integer, nullable=False, default=0)
    support_count = Column(Integer, nullable=False, default=0)
    high_priority_count = Column(Integer, nullable=False, default=0)

    # Time metrics
    registered_hours_week = Column(Float, nullable=False, default=0.0)
    expected_hours_week = Column(Float, nullable=False, default=0.0)
    bug_hours = Column(Float, nullable=False, default=0.0)
    development_hours = Column(Float, nullable=False, default=0.0)
    support_hours = Column(Float, nullable=False, default=0.0)

    # Performance metrics
    avg_deadline_delivery_days = Column(String(50), nullable=True)
    review_back_count = Column(Integer, nullable=False, default=0)
    story_test_pass_rate = Column(String(50), nullable=True)
    acceptance_criteria_pass_rate = Column(String(50), nullable=True)

    # Completion metrics
    high_priority_completed_count = Column(Integer, nullable=False, default=0)
    development_delivered_count = Column(Integer, nullable=False, default=0)
    bug_delivered_count = Column(Integer, nullable=False, default=0)
    support_delivered_count = Column(Integer, nullable=False, default=0)

    # Defect metrics
    avg_support_bugs_per_story = Column(Float, nullable=False, default=0.0)
    avg_tester_bugs_per_story = Column(Float, nullable=False, default=0.0)

    # Quality score
    quality_score = Column(Integer, nullable=False, default=0)


class PostgresTeamEvaluationRepository(TeamEvaluationRepositoryInterface):
    """PostgreSQL implementation of team evaluation repository."""

    def __init__(self, db_connection: DatabaseConnectionInterface):
        """Initialize the repository.
        
        Args:
            db_connection: Database connection interface.
        """
        self.db_connection = db_connection
        self.engine = db_connection.get_engine()

    def _entity_to_model(self, evaluation: TeamEvaluationRow) -> dict:
        """Convert entity to database model dictionary.
        
        Args:
            evaluation: Team evaluation entity.
            
        Returns:
            Dictionary for database insertion.
        """
        return {
            "sprint_name": evaluation.sprint,
            "developer_name": evaluation.developer_name,
            "department": evaluation.department,
            "project": evaluation.project,
            "development_count": evaluation.development_count,
            "bug_count": evaluation.bug_count,
            "support_count": evaluation.support_count,
            "high_priority_count": evaluation.high_priority_count,
            "registered_hours_week": evaluation.registered_hours_week,
            "expected_hours_week": evaluation.expected_hours_week,
            "bug_hours": evaluation.bug_hours,
            "development_hours": evaluation.development_hours,
            "support_hours": evaluation.support_hours,
            "avg_deadline_delivery_days": evaluation.avg_deadline_delivery_days,
            "review_back_count": evaluation.review_back_count,
            "story_test_pass_rate": evaluation.story_test_pass_rate,
            "acceptance_criteria_pass_rate": evaluation.acceptance_criteria_pass_rate,
            "high_priority_completed_count": evaluation.high_priority_completed_count,
            "avg_support_bugs_per_story": evaluation.avg_support_bugs_per_story,
            "avg_tester_bugs_per_story": evaluation.avg_tester_bugs_per_story,
            "development_delivered_count": evaluation.development_delivered_count,
            "bug_delivered_count": evaluation.bug_delivered_count,
            "support_delivered_count": evaluation.support_delivered_count,
            "quality_score": evaluation.quality_score,
        }

    def _model_to_entity(self, model: TeamEvaluationModel) -> TeamEvaluationRow:
        """Convert database model to entity.
        
        Args:
            model: Database model instance.
            
        Returns:
            Team evaluation entity.
        """
        return TeamEvaluationRow(
            developer_name=model.developer_name,
            department=model.department,
            project=model.project,
            sprint=model.sprint_name,
            development_count=model.development_count,
            bug_count=model.bug_count,
            support_count=model.support_count,
            high_priority_count=model.high_priority_count,
            registered_hours_week=model.registered_hours_week,
            expected_hours_week=model.expected_hours_week,
            bug_hours=model.bug_hours,
            development_hours=model.development_hours,
            support_hours=model.support_hours,
            avg_deadline_delivery_days=model.avg_deadline_delivery_days or "N/A",
            review_back_count=model.review_back_count,
            story_test_pass_rate=model.story_test_pass_rate or "N/A",
            acceptance_criteria_pass_rate=model.acceptance_criteria_pass_rate or "N/A",
            high_priority_completed_count=model.high_priority_completed_count,
            avg_support_bugs_per_story=model.avg_support_bugs_per_story,
            avg_tester_bugs_per_story=model.avg_tester_bugs_per_story,
            development_delivered_count=model.development_delivered_count,
            bug_delivered_count=model.bug_delivered_count,
            support_delivered_count=model.support_delivered_count,
            quality_score=model.quality_score,
        )

    async def save_evaluation(self, evaluation: TeamEvaluationRow) -> None:
        """Save a team evaluation row using upsert (insert or update).
        
        Args:
            evaluation: Team evaluation data to save.
        """
        # Extract sprint_id from sprint name (assuming format "Sprint X")
        sprint_id = self._extract_sprint_id(evaluation.sprint)
        
        data = self._entity_to_model(evaluation)
        data["sprint_id"] = sprint_id
        data["updated_at"] = datetime.utcnow()

        # Upsert: insert or update on conflict
        stmt = insert(TeamEvaluationModel).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="unique_sprint_developer_dept_project",
            set_=data
        )

        with self.engine.connect() as connection:
            connection.execute(stmt)
            connection.commit()

        LOGGER.debug(
            f"Saved evaluation for {evaluation.developer_name} in "
            f"{evaluation.sprint} ({evaluation.department}/{evaluation.project})"
        )

    async def save_evaluations_batch(self, evaluations: List[TeamEvaluationRow]) -> int:
        """Save multiple team evaluation rows in a batch.
        
        Args:
            evaluations: List of team evaluation data to save.
            
        Returns:
            Number of rows saved.
        """
        if not evaluations:
            return 0

        for evaluation in evaluations:
            await self.save_evaluation(evaluation)

        LOGGER.info(f"Saved batch of {len(evaluations)} team evaluations")
        return len(evaluations)
    async def get_sprint_evaluations(
        self,
        sprint_id: int,
        project: Optional[str] = None
    ) -> List[TeamEvaluationRow]:
        """Get all evaluations for a specific sprint.
        
        Args:
            sprint_id: Sprint ID.
            project: Optional project filter.
            
        Returns:
            List of evaluation rows for the sprint.
        """
        query = select(TeamEvaluationModel).where(
            TeamEvaluationModel.sprint_id == sprint_id
        )

        if project:
            query = query.where(TeamEvaluationModel.project == project)

        with self.engine.connect() as connection:
            result = connection.execute(query)
            models = result.fetchall()

        return [self._model_to_entity(model) for model in models]

    async def get_developer_evaluations(
        self,
        developer_name: str,
        limit: Optional[int] = None
    ) -> List[TeamEvaluationRow]:
        """Get evaluation history for a specific developer.
        
        Args:
            developer_name: Developer name.
            limit: Optional limit on number of rows returned.
            
        Returns:
            List of evaluation rows for the developer.
        """
        query = select(TeamEvaluationModel).where(
            TeamEvaluationModel.developer_name == developer_name
        ).order_by(TeamEvaluationModel.created_at.desc())

        if limit:
            query = query.limit(limit)

        with self.engine.connect() as connection:
            result = connection.execute(query)
            models = result.fetchall()

        return [self._model_to_entity(model) for model in models]

    async def delete_sprint_evaluations(self, sprint_id: int) -> int:
        """Delete all evaluations for a sprint.
        
        Args:
            sprint_id: Sprint ID.
            
        Returns:
            Number of rows deleted.
        """
        stmt = delete(TeamEvaluationModel).where(
            TeamEvaluationModel.sprint_id == sprint_id
        )

        with self.engine.connect() as connection:
            result = connection.execute(stmt)
            connection.commit()
            deleted_count = result.rowcount

        LOGGER.info(f"Deleted {deleted_count} evaluations for sprint {sprint_id}")
        return deleted_count

    async def evaluation_exists(
        self,
        sprint_id: int,
        developer_name: str,
        department: str,
        project: str
    ) -> bool:
        """Check if an evaluation already exists.
        
        Args:
            sprint_id: Sprint ID.
            developer_name: Developer name.
            department: Department.
            project: Project.
            
        Returns:
            True if evaluation exists, False otherwise.
        """
        query = select(TeamEvaluationModel).where(
            TeamEvaluationModel.sprint_id == sprint_id,
            TeamEvaluationModel.developer_name == developer_name,
            TeamEvaluationModel.department == department,
            TeamEvaluationModel.project == project
        )

        with self.engine.connect() as connection:
            result = connection.execute(query)
            return result.fetchone() is not None
        return result.scalar_one_or_none() is not None

    def _extract_sprint_id(self, sprint_name: str) -> int:
        """Extract sprint ID from sprint name.
        
        For now, we'll use a hash of the sprint name as ID.
        In production, this should be the actual Jira sprint ID.
        
        Args:
            sprint_name: Sprint name string.
            
        Returns:
            Sprint ID integer.
        """
        # Simple hash-based ID for now
        # This should be replaced with actual sprint ID from Jira
        return abs(hash(sprint_name)) % (10 ** 8)
