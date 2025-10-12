"""Score service for team evaluation."""

from typing import Dict, List, Tuple

from jira_telegram_bot.entities.team_evaluation import (
    TeamEvaluationScoreWeights,
    IssueSnapshot
)
from jira_telegram_bot.entities.constants import (
    DEADLINE_PENALTY_PER_DAY,
    EARLY_DELIVERY_BONUS_PER_DAY,
    MAX_EARLY_DELIVERY_BONUS,
    HIGH_PRIORITY_ZERO_COMPLETION_PENALTY,
    HIGH_PRIORITY_BELOW_MIN_SCORE,
    MIN_HIGH_PRIORITY_TASKS_PER_WEEK,
    DONE_STATUSES,
    EXTRA_TASK_COMPLETION_BONUS
)


class ScoreService:
    """Service for computing quality scores."""

    @staticmethod
    def calculate_required_tasks_count(
        all_issues: List[IssueSnapshot],
        expected_weekly_hours: float
    ) -> Tuple[int, List[IssueSnapshot]]:
        """Calculate number of tasks required based on 50% of weekly time.
        
        Args:
            all_issues: All issues assigned to developer
            expected_weekly_hours: Developer's expected weekly hours
            
        Returns:
            Tuple of (required_task_count, sorted_priority_issues)
        """
        target_hours = expected_weekly_hours * 0.5
        
        priority_order = {
            "Highest": 1,
            "High": 2,
            "Medium": 3,
            "Low": 4,
            "Lowest": 5,
            None: 6
        }
        
        sorted_issues = sorted(
            all_issues,
            key=lambda x: (priority_order.get(x.priority, 6), x.key)
        )
        
        cumulative_hours = 0.0
        required_count = 0
        
        for issue in sorted_issues:
            if issue.time_estimate_hours != 0:
                estimated_hours = issue.time_estimate_hours or 0.0
                if cumulative_hours >= target_hours:
                    break
                cumulative_hours += estimated_hours
                required_count += 1
        
        return required_count, sorted_issues[:required_count]

    @staticmethod
    def compute_hosn_score(
        weights: TeamEvaluationScoreWeights,
        deadline_penalty_score: float,
        registered_hours: float,
        expected_hours: float,
        all_issues: List[IssueSnapshot],
        completed_high_priority: int,
        total_high_priority: int,
        support_bugs_per_story: float,
        tester_bugs_per_story: float,
        defect_thresholds: Dict,
        extra_completed_tasks_count: int = 0
    ) -> int:
        """Compute the composite quality score (حسن انجام کار) with per-task deadline penalties.
        
        Args:
            weights: Score weights configuration
            deadline_penalty_score: Total penalty from per-task deadline calculation
            registered_hours: Actual registered hours
            expected_hours: Expected hours for the period
            all_issues: All issues assigned to developer (for 50% calculation)
            completed_high_priority: Number of completed high priority items
            total_high_priority: Total number of high priority items assigned
            support_bugs_per_story: Support bugs per delivered story
            tester_bugs_per_story: Tester bugs per delivered story
            defect_thresholds: Defect penalty thresholds
            extra_completed_tasks_count: Number of extra tasks completed beyond capacity
            
        Returns:
            Composite score between -50 and 100 (plus extra task bonuses)
        """
        # 1. Deadline score (direct penalty from per-task calculation)
        # Start with 100 and subtract the calculated penalty
        s_deadline = max(0, 100 - deadline_penalty_score)
        
        # 2. Worklog score (ratio of registered to expected, capped at 100)
        if expected_hours > 0:
            worklog_ratio = min(registered_hours / expected_hours, 1.0)
        else:
            worklog_ratio = 1.0 if registered_hours > 0 else 0.0
        s_worklog = worklog_ratio * 100
        
        # 3. HIGH PRIORITY SCORE BASED ON REQUIRED 50% COMPLETION
        required_task_count, required_tasks = ScoreService.calculate_required_tasks_count(
            all_issues, 
            expected_hours
        )
        
        if required_task_count == 0:
            s_high = 100
        else:
            completed_required_tasks = sum(
                1 for task in required_tasks 
                if task.status in DONE_STATUSES
            )
            
            if completed_required_tasks == 0:
                s_high = HIGH_PRIORITY_ZERO_COMPLETION_PENALTY
            elif completed_required_tasks < min(1, required_task_count):
                s_high = HIGH_PRIORITY_BELOW_MIN_SCORE
            else:
                completion_ratio = completed_required_tasks / required_task_count
                s_high = completion_ratio * 100
        
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
        
        # CRITICAL: Apply penalties for poor performance
        # Rule 1: No time registered = -30 penalty
        if registered_hours == 0:
            composite_score -= 30
        else:
            # Rule 1b: Insufficient time registration penalty
            # If registered hours < 65% of min(expected_hours, total_task_hours)
            total_task_hours = sum(issue.time_estimate_hours or 0.0 for issue in all_issues)
            min_threshold = min(expected_hours, total_task_hours)
            required_min_hours = min_threshold * 0.65
            
            if registered_hours < required_min_hours:
                shortage = required_min_hours - registered_hours
                shortage_percentage = shortage / required_min_hours
                time_registration_penalty = shortage_percentage * 30
                composite_score -= time_registration_penalty
        
        # Rule 2: No high priority tasks completed = severe penalty (already in s_high)
        # This is already handled in the s_high calculation above
        
        # Bonus for completing extra tasks beyond reasonable capacity
        extra_task_bonus = extra_completed_tasks_count * EXTRA_TASK_COMPLETION_BONUS
        composite_score += extra_task_bonus
        
        # Score must be between -50 and 100+bonuses (allowing negative scores for poor performance)
        # Note: Extra task bonuses can push score above 100
        final_score = max(-50, round(composite_score))
        
        return final_score
