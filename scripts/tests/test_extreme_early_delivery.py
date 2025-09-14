"""Test extreme early delivery to see maximum possible score."""
from __future__ import annotations

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from jira_telegram_bot.entities.team_evaluation import TeamEvaluationScoreWeights
from jira_telegram_bot.use_cases.team_evaluation.services.score_service import (
    ScoreService,
)
from jira_telegram_bot.entities.constants import DEFAULT_DEFECT_THRESHOLDS


def test_extreme_early_delivery():
    """Test extreme early delivery to see maximum possible score."""

    weights = TeamEvaluationScoreWeights()

    print("=== تست تعجیل شدید در تحویل ===\n")

    # Test with 10 days early delivery (maximum bonus)
    score_extreme = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_hours=-240,  # 10 days early (max bonus = 110)
        registered_hours=46,
        expected_hours=46,
        completed_high_priority=5,
        total_high_priority=5,
        support_bugs_per_story=0.0,  # No defects
        tester_bugs_per_story=0.0,  # No defects
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS,
    )

    print(f"تعجیل 10 روزه + کیفیت عالی: {score_extreme}")

    # Manual calculation
    s_deadline = 110  # Maximum
    s_worklog = 100  # Perfect
    s_high = 100  # Perfect
    s_defects = 100  # Perfect

    manual_calc = (
        0.25 * s_deadline + 0.20 * s_worklog + 0.40 * s_high + 0.15 * s_defects
    )

    print(f"محاسبه دستی: 0.25×110 + 0.20×100 + 0.40×100 + 0.15×100 = {manual_calc}")

    print(f"\nحداکثر امتیاز ممکن: {manual_calc}")
    print(f"امتیاز واقعی: {score_extreme}")

    # Test a more reasonable early delivery
    score_reasonable = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_hours=-72,  # 3 days early
        registered_hours=46,
        expected_hours=46,
        completed_high_priority=3,
        total_high_priority=3,
        support_bugs_per_story=0.05,  # Very low defects
        tester_bugs_per_story=0.05,  # Very low defects
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS,
    )

    print(f"\nتعجیل 3 روزه + کیفیت خوب: {score_reasonable}")


if __name__ == "__main__":
    test_extreme_early_delivery()
