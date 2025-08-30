"""Score service for team evaluation."""

from typing import Dict

from jira_telegram_bot.entities.team_evaluation import TeamEvaluationScoreWeights
from jira_telegram_bot.entities.constants import DEFAULT_DEADLINE_PENALTY_RATE


class ScoreService:
    """Service for computing quality scores."""

    @staticmethod
    def compute_hosn_score(
        weights: TeamEvaluationScoreWeights,
        avg_deadline_delta_hours: float,
        registered_hours: float,
        expected_hours: float,
        completed_high_priority: int,
        total_high_priority: int,
        support_bugs_per_story: float,
        tester_bugs_per_story: float,
        defect_thresholds: Dict
    ) -> int:
        """Compute the composite quality score (حسن انجام کار).
        
        Args:
            weights: Score weights configuration
            avg_deadline_delta_hours: Average deadline delta (positive = late)
            registered_hours: Actual registered hours
            expected_hours: Expected hours for the period
            completed_high_priority: Number of completed high priority items
            total_high_priority: Total number of high priority items assigned
            support_bugs_per_story: Support bugs per delivered story
            tester_bugs_per_story: Tester bugs per delivered story
            defect_thresholds: Defect penalty thresholds
            
        Returns:
            Composite score from 0 to 100
        """
        # Deadline score (penalty for being late, max 100)
        deadline_penalty = max(0, avg_deadline_delta_hours) * DEFAULT_DEADLINE_PENALTY_RATE
        s_deadline = max(0, min(100, 100 - deadline_penalty))
        
        # Worklog score (ratio of registered to expected, capped at 100)
        if expected_hours > 0:
            worklog_ratio = min(registered_hours / expected_hours, 1.0)
        else:
            worklog_ratio = 1.0 if registered_hours > 0 else 0.0
        s_worklog = worklog_ratio * 100
        
        # High priority score
        if total_high_priority > 0:
            high_priority_ratio = completed_high_priority / total_high_priority
        else:
            high_priority_ratio = 1.0  # No high priority items = perfect score
        s_high = high_priority_ratio * 100
        
        # Defect score
        support_threshold = defect_thresholds.get("support_per_story", 0.3)
        tester_threshold = defect_thresholds.get("tester_per_story", 0.4)
        max_penalty = defect_thresholds.get("max_penalty", 60)
        
        support_penalty = (support_bugs_per_story / support_threshold) * 30
        tester_penalty = (tester_bugs_per_story / tester_threshold) * 30
        total_defect_penalty = min(support_penalty + tester_penalty, max_penalty)
        s_defects = 100 - total_defect_penalty
        
        # Weighted composite score
        composite_score = (
            weights.deadline * s_deadline +
            weights.worklog * s_worklog +
            weights.high_priority * s_high +
            weights.defects * s_defects
        )
        
        return round(composite_score)
