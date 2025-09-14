"""Debug script to check early delivery bonus calculation."""
from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.constants import DEFAULT_DEFECT_THRESHOLDS
from jira_telegram_bot.entities.team_evaluation import TeamEvaluationScoreWeights
from jira_telegram_bot.use_cases.team_evaluation.services.score_service import (
    ScoreService,
)


def debug_early_delivery():
    """Debug early delivery bonus calculation."""

    weights = TeamEvaluationScoreWeights()

    LOGGER.info("=== دیباگ محاسبه بونوس تعجیل ===\n")

    # Manual calculation for test case 2
    avg_deadline_delta_hours = -48  # 2 days early
    deadline_delta_days = avg_deadline_delta_hours / 24.0  # -2.0 days

    LOGGER.info(f"Deadline delta hours: {avg_deadline_delta_hours}")
    LOGGER.info(f"Deadline delta days: {deadline_delta_days}")

    # Early delivery calculation
    early_bonus = abs(deadline_delta_days) * 1.0  # abs(-2.0) * 1.0 = 2.0
    s_deadline = min(110, 100 + early_bonus)  # min(110, 102) = 102

    LOGGER.info(f"Early bonus: {early_bonus}")
    LOGGER.info(f"S_deadline: {s_deadline}")

    # Other scores
    s_worklog = 100  # 40/40 = 100%
    s_high = 100  # 2/2 = 100%

    # Defect calculation
    support_penalty = (0.1 / 0.3) * 30  # 10
    tester_penalty = (0.1 / 0.4) * 30  # 7.5
    total_defect_penalty = min(support_penalty + tester_penalty, 60)  # 17.5
    s_defects = 100 - total_defect_penalty  # 82.5

    LOGGER.info(f"S_worklog: {s_worklog}")
    LOGGER.info(f"S_high: {s_high}")
    LOGGER.info(f"S_defects: {s_defects}")

    # Final weighted score
    composite_score = (
        weights.deadline * s_deadline
        + weights.worklog * s_worklog
        + weights.high_priority * s_high
        + weights.defects * s_defects
    )

    LOGGER.info(f"\nFinal calculation:")
    LOGGER.info(
        f"0.25 × {s_deadline} + 0.20 × {s_worklog} + 0.40 × {s_high} + 0.15 × {s_defects}",
    )
    LOGGER.info(
        f"= {0.25 * s_deadline} + {0.20 * s_worklog} + {0.40 * s_high} + {0.15 * s_defects}",
    )
    LOGGER.info(f"= {composite_score}")
    LOGGER.info(f"Rounded: {round(composite_score)}")

    # Test with actual function
    actual_score = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_hours=-48,
        registered_hours=40,
        expected_hours=40,
        completed_high_priority=2,
        total_high_priority=2,
        support_bugs_per_story=0.1,
        tester_bugs_per_story=0.1,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS,
    )

    LOGGER.info(f"\nActual function result: {actual_score}")


if __name__ == "__main__":
    debug_early_delivery()
