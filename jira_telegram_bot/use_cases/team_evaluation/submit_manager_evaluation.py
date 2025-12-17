"""Use case for submitting manager evaluations."""
from datetime import datetime
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.manager_evaluation_repository import (
    ManagerEvaluationRepository,
)
from jira_telegram_bot.entities.manager_evaluation import ManagerEvaluation


class SubmitManagerEvaluation:
    """Submit a manager's evaluation of a developer.
    
    This use case:
    1. Validates the manager is assigned to evaluate the developer
    2. Validates scores are within acceptable ranges
    3. Saves the evaluation
    4. Returns the saved evaluation with calculated total score
    """

    def __init__(self, manager_eval_repo: ManagerEvaluationRepository):
        """Initialize use case.
        
        Args:
            manager_eval_repo: Manager evaluation repository
        """
        self.manager_eval_repo = manager_eval_repo

    def execute(
        self,
        sprint_id: int,
        developer_name: str,
        manager_name: str,
        evaluation_month: str,
        collaboration_score: int,
        alignment_score: int,
        comments: Optional[str] = None,
    ) -> ManagerEvaluation:
        """Submit a manager evaluation.
        
        Args:
            sprint_id: Sprint ID being evaluated
            developer_name: Developer being evaluated
            manager_name: Manager submitting evaluation
            evaluation_month: Month in YYYY-MM format
            collaboration_score: Score for collaboration (0-100)
            alignment_score: Score for alignment with goals (0-100)
            comments: Optional comments from manager
            
        Returns:
            Saved evaluation
            
        Raises:
            ValueError: If scores are invalid or manager not assigned
        """
        # Validate manager is assigned to this developer
        managers = self.manager_eval_repo.get_managers_for_developer(developer_name)
        if not any(m.manager_name == manager_name for m in managers):
            raise ValueError(
                f"Manager {manager_name} is not assigned to evaluate {developer_name}"
            )
        
        # Validate scores
        if not (0 <= collaboration_score <= 100):
            raise ValueError("Collaboration score must be between 0 and 100")
        
        if not (0 <= alignment_score <= 100):
            raise ValueError("Alignment score must be between 0 and 100")
        
        # Calculate total manager score
        total_score = ManagerEvaluation.calculate_total_score(
            collaboration_score, alignment_score
        )
        
        # Create evaluation
        evaluation = ManagerEvaluation(
            sprint_id=sprint_id,
            developer_name=developer_name,
            manager_name=manager_name,
            evaluation_month=evaluation_month,
            collaboration_score=collaboration_score,
            alignment_score=alignment_score,
            total_manager_score=total_score,
            comments=comments,
            evaluated_at=datetime.now(),
        )
        
        # Save evaluation
        saved_evaluation = self.manager_eval_repo.save_evaluation(evaluation)
        
        LOGGER.info(
            f"Manager {manager_name} evaluated {developer_name} for sprint {sprint_id}: "
            f"collaboration={collaboration_score}, alignment={alignment_score}, "
            f"total={total_score}"
        )
        
        return saved_evaluation

    def bulk_submit_evaluations(
        self,
        evaluations: list[dict],
        manager_name: str,
    ) -> list[ManagerEvaluation]:
        """Submit multiple evaluations at once.
        
        Args:
            evaluations: List of evaluation dicts with keys:
                - sprint_id
                - developer_name
                - evaluation_month
                - collaboration_score
                - alignment_score
                - comments (optional)
            manager_name: Manager submitting all evaluations
            
        Returns:
            List of saved evaluations
        """
        results = []
        
        for eval_data in evaluations:
            try:
                result = self.execute(
                    sprint_id=eval_data["sprint_id"],
                    developer_name=eval_data["developer_name"],
                    manager_name=manager_name,
                    evaluation_month=eval_data["evaluation_month"],
                    collaboration_score=eval_data["collaboration_score"],
                    alignment_score=eval_data["alignment_score"],
                    comments=eval_data.get("comments"),
                )
                results.append(result)
            except Exception as e:
                LOGGER.error(
                    f"Failed to submit evaluation for {eval_data.get('developer_name')}: {e}"
                )
                continue
        
        return results
