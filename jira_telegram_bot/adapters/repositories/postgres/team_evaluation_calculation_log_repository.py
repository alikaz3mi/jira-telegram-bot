"""PostgreSQL implementation of team evaluation calculation log repository."""
from datetime import datetime
from typing import List

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from jira_telegram_bot.entities.team_evaluation_calculation_log import (
    TeamEvaluationCalculationLog,
)
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import (
    DatabaseConnectionInterface,
)
from jira_telegram_bot import LOGGER

Base = declarative_base()


class TeamEvaluationCalculationLogModel(Base):
    """SQLAlchemy model for team evaluation calculation logs."""

    __tablename__ = "team_evaluation_calculation_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sprint_id = Column(Integer, nullable=False)
    sprint_name = Column(String(255), nullable=False)
    developer_name = Column(String(255), nullable=False)
    department = Column(String(100), nullable=False)
    project = Column(String(100), nullable=False)
    calculation_type = Column(String(100), nullable=False)
    metric_name = Column(String(255), nullable=False)
    metric_value = Column(Float, nullable=False)
    calculation_formula = Column(Text, nullable=False)
    calculation_details = Column(Text, nullable=False)
    weight = Column(Float, nullable=True)
    contribution_to_total = Column(Float, nullable=True)
    evaluation_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)


class PostgreSQLTeamEvaluationCalculationLogRepository:
    """PostgreSQL repository for team evaluation calculation logs."""

    def __init__(self, db_connection: DatabaseConnectionInterface):
        """Initialize repository with database connection.

        Args:
            db_connection: Database connection interface.
        """
        self.db_connection = db_connection

    def _get_session(self) -> Session:
        """Get database session.

        Returns:
            SQLAlchemy Session instance.
        """
        return self.db_connection.get_session()

    def save_log(self, log: TeamEvaluationCalculationLog) -> None:
        """Save a single calculation log entry.

        Args:
            log: TeamEvaluationCalculationLog entity to save.
        """
        session = self._get_session()
        try:
            log_model = self._to_model(log)
            session.add(log_model)
            session.commit()
            LOGGER.info(
                f"Saved calculation log for {log.developer_name} - {log.metric_name}"
            )
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Failed to save calculation log: {e}")
            raise

    def save_logs_batch(self, logs: List[TeamEvaluationCalculationLog]) -> None:
        """Save multiple calculation log entries in a batch.

        Args:
            logs: List of TeamEvaluationCalculationLog entities to save.
        """
        session = self._get_session()
        try:
            log_models = [self._to_model(log) for log in logs]
            session.add_all(log_models)
            session.commit()
            LOGGER.info(f"Saved {len(logs)} calculation log entries")
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Failed to save calculation logs batch: {e}")
            raise

    def get_logs_by_sprint_and_developer(
        self, sprint_id: int, developer_name: str
    ) -> List[TeamEvaluationCalculationLog]:
        """Retrieve calculation logs for a specific sprint and developer.

        Args:
            sprint_id: Sprint identifier.
            developer_name: Developer name.

        Returns:
            List of TeamEvaluationCalculationLog entities.
        """
        session = self._get_session()
        try:
            logs = (
                session.query(TeamEvaluationCalculationLogModel)
                .filter(
                    TeamEvaluationCalculationLogModel.sprint_id == sprint_id,
                    TeamEvaluationCalculationLogModel.developer_name == developer_name,
                )
                .order_by(TeamEvaluationCalculationLogModel.timestamp)
                .all()
            )
            return [self._to_entity(log) for log in logs]
        except Exception as e:
            LOGGER.error(
                f"Failed to retrieve logs for sprint {sprint_id}, developer {developer_name}: {e}"
            )
            raise

    def get_logs_by_evaluation_id(
        self, evaluation_id: int
    ) -> List[TeamEvaluationCalculationLog]:
        """Retrieve calculation logs for a specific evaluation record.

        Args:
            evaluation_id: Evaluation record identifier.

        Returns:
            List of TeamEvaluationCalculationLog entities.
        """
        session = self._get_session()
        try:
            logs = (
                session.query(TeamEvaluationCalculationLogModel)
                .filter(
                    TeamEvaluationCalculationLogModel.evaluation_id == evaluation_id
                )
                .order_by(TeamEvaluationCalculationLogModel.timestamp)
                .all()
            )
            return [self._to_entity(log) for log in logs]
        except Exception as e:
            LOGGER.error(f"Failed to retrieve logs for evaluation {evaluation_id}: {e}")
            raise

    def _to_model(
        self, log: TeamEvaluationCalculationLog
    ) -> TeamEvaluationCalculationLogModel:
        """Convert entity to SQLAlchemy model.

        Args:
            log: TeamEvaluationCalculationLog entity.

        Returns:
            TeamEvaluationCalculationLogModel instance.
        """
        return TeamEvaluationCalculationLogModel(
            sprint_id=log.sprint_id,
            sprint_name=log.sprint_name,
            developer_name=log.developer_name,
            department=log.department,
            project=log.project,
            calculation_type=log.calculation_type,
            metric_name=log.metric_name,
            metric_value=log.metric_value,
            calculation_formula=log.calculation_formula,
            calculation_details=log.calculation_details,
            weight=log.weight,
            contribution_to_total=log.contribution_to_total,
            evaluation_id=log.evaluation_id,
            timestamp=log.timestamp or datetime.utcnow(),
        )

    def _to_entity(
        self, model: TeamEvaluationCalculationLogModel
    ) -> TeamEvaluationCalculationLog:
        """Convert SQLAlchemy model to entity.

        Args:
            model: TeamEvaluationCalculationLogModel instance.

        Returns:
            TeamEvaluationCalculationLog entity.
        """
        return TeamEvaluationCalculationLog(
            sprint_id=model.sprint_id,
            sprint_name=model.sprint_name,
            developer_name=model.developer_name,
            department=model.department,
            project=model.project,
            calculation_type=model.calculation_type,
            metric_name=model.metric_name,
            metric_value=model.metric_value,
            calculation_formula=model.calculation_formula,
            calculation_details=model.calculation_details,
            weight=model.weight,
            contribution_to_total=model.contribution_to_total,
            evaluation_id=model.id,
            timestamp=model.timestamp,
        )
