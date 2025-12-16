"""Interface for team evaluation calculation log repository."""
from typing import List, Protocol

from jira_telegram_bot.entities.team_evaluation_calculation_log import (
    TeamEvaluationCalculationLog,
)


class TeamEvaluationCalculationLogRepositoryInterface(Protocol):
    """Repository interface for team evaluation calculation logs."""

    def save_log(self, log: TeamEvaluationCalculationLog) -> None:
        """Save a single calculation log entry.

        Args:
            log: TeamEvaluationCalculationLog entity to save.
        """
        ...

    def save_logs_batch(self, logs: List[TeamEvaluationCalculationLog]) -> None:
        """Save multiple calculation log entries in a batch.

        Args:
            logs: List of TeamEvaluationCalculationLog entities to save.
        """
        ...

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
        ...

    def get_logs_by_evaluation_id(
        self, evaluation_id: int
    ) -> List[TeamEvaluationCalculationLog]:
        """Retrieve calculation logs for a specific evaluation record.

        Args:
            evaluation_id: Evaluation record identifier.

        Returns:
            List of TeamEvaluationCalculationLog entities.
        """
        ...
