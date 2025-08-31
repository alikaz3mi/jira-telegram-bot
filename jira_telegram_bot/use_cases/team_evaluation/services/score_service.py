"""Score service for team evaluation."""

from typing import Dict

from jira_telegram_bot.entities.team_evaluation import TeamEvaluationScoreWeights
from jira_telegram_bot.entities.constants import (
    DEADLINE_PENALTY_PER_DAY,
    EARLY_DELIVERY_BONUS_PER_DAY,
    MAX_EARLY_DELIVERY_BONUS,
    HIGH_PRIORITY_ZERO_COMPLETION_PENALTY,
    HIGH_PRIORITY_BELOW_MIN_SCORE,
    MIN_HIGH_PRIORITY_TASKS_PER_WEEK
)


class ScoreService:
    """Service for computing quality scores."""

    @staticmethod
    def compute_hosn_score(
        weights: TeamEvaluationScoreWeights,
        avg_deadline_delta_days: float,
        registered_hours: float,
        expected_hours: float,
        completed_high_priority: int,
        total_high_priority: int,
        support_bugs_per_story: float,
        tester_bugs_per_story: float,
        defect_thresholds: Dict
    ) -> int:
        """Compute the composite quality score (حسن انجام کار) with enhanced high priority weighting.
        
        Args:
            weights: Score weights configuration
            avg_deadline_delta_days: Average deadline delta in days (positive = late)
            registered_hours: Actual registered hours
            expected_hours: Expected hours for the period
            completed_high_priority: Number of completed high priority items
            total_high_priority: Total number of high priority items assigned
            support_bugs_per_story: Support bugs per delivered story
            tester_bugs_per_story: Tester bugs per delivered story
            defect_thresholds: Defect penalty thresholds
            
        Returns:
            Composite score between 0 and 100
        """
        # 1. Deadline score (penalty/bonus based on days)
        if avg_deadline_delta_days > 0:
            # Late delivery: penalty (2 points per day late)
            deadline_penalty = avg_deadline_delta_days * DEADLINE_PENALTY_PER_DAY
            s_deadline = max(0, min(100, 100 - deadline_penalty))
        else:
            # Early delivery: bonus (1 point per day early, but capped at 100)
            early_bonus = abs(avg_deadline_delta_days) * EARLY_DELIVERY_BONUS_PER_DAY
            s_deadline = min(100, 100 + early_bonus)  # Cap at 100, not 110
        
        # 2. Worklog score (ratio of registered to expected, capped at 100)
        if expected_hours > 0:
            worklog_ratio = min(registered_hours / expected_hours, 1.0)
        else:
            worklog_ratio = 1.0 if registered_hours > 0 else 0.0
        s_worklog = worklog_ratio * 100
        
        # 3. HIGH PRIORITY SCORE WITH SEVERE PENALTIES
        if total_high_priority == 0:
            # No high priority tasks assigned - neutral score
            s_high = 100
        elif completed_high_priority == 0:
            # CRITICAL: No high priority tasks completed - severe penalty
            # این یعنی وقت تلف شده - امتیاز خیلی منفی
            s_high = HIGH_PRIORITY_ZERO_COMPLETION_PENALTY  # -50
        elif completed_high_priority < MIN_HIGH_PRIORITY_TASKS_PER_WEEK:
            # Less than minimum 1 task per week - major penalty
            s_high = HIGH_PRIORITY_BELOW_MIN_SCORE  # 20
        else:
            # Normal calculation for when at least minimum tasks are completed
            high_priority_ratio = completed_high_priority / total_high_priority
            s_high = high_priority_ratio * 100
        
        # 4. Defect score
        support_threshold = defect_thresholds.get("support_per_story", 0.3)
        tester_threshold = defect_thresholds.get("tester_per_story", 0.4)
        max_penalty = defect_thresholds.get("max_penalty", 60)
        
        support_penalty = (support_bugs_per_story / support_threshold) * 30
        tester_penalty = (tester_bugs_per_story / tester_threshold) * 30
        total_defect_penalty = min(support_penalty + tester_penalty, max_penalty)
        s_defects = 100 - total_defect_penalty
        
        # Weighted composite score with new emphasis on high priority
        composite_score = (
            weights.deadline * s_deadline +
            weights.worklog * s_worklog +
            weights.high_priority * s_high +
            weights.defects * s_defects
        )
        
        # CRITICAL: If someone has done nothing meaningful, score should be 0
        # Rule 1: No time registered = 0 score (regardless of other metrics)
        if registered_hours == 0:
            return 0
        
        # Rule 2: No high priority tasks completed = 0 score (time is wasted)
        if completed_high_priority == 0 and total_high_priority > 0:
            return 0
        
        # Score must be between 0 and 100 (no scores above 100)
        final_score = max(0, min(100, round(composite_score)))
        
        return final_score
