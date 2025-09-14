"""Test script for the corrected hosn score calculation."""
from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.constants import DEFAULT_DEFECT_THRESHOLDS
from jira_telegram_bot.entities.team_evaluation import (
    TeamEvaluationScoreWeights,
)
from jira_telegram_bot.use_cases.team_evaluation.services.score_service import (
    ScoreService,
)


def test_corrected_hosn_score():
    """Test the corrected hosn score calculation."""

    weights = TeamEvaluationScoreWeights()

    LOGGER.info("=== تست محاسبه حسن انجام کار اصلاح شده ===\n")
    LOGGER.info("محدودیت‌ها:")
    LOGGER.info("✅ امتیاز بین 0 تا 100")
    LOGGER.info("✅ بدون فعالیت = امتیاز 0")
    LOGGER.info("✅ ورودی بر اساس روز")
    LOGGER.info("=" * 60)

    # Test Case 1: No activity (like هروی)
    LOGGER.info("\n📍 Test 1: بدون فعالیت (مثل هروی)")
    LOGGER.info("- هیچ ساعتی ثبت نکرده (0 ساعت)")
    LOGGER.info("- هیچ تسک اولویت بالایی تحویل نداده (0/1)")

    score1 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_days=0,  # No deadlines to evaluate
        registered_hours=0,  # NO TIME REGISTERED
        expected_hours=38,
        completed_high_priority=0,  # NO HIGH PRIORITY COMPLETED
        total_high_priority=1,
        support_bugs_per_story=0.0,
        tester_bugs_per_story=0.0,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS,
    )
    LOGGER.info(f"امتیاز: {score1}")
    LOGGER.info("انتظار: 0 (هیچ کاری نکرده)")

    # Test Case 2: Some activity but no high priority (like )
    LOGGER.info("\n📍 Test 2: فعالیت بدون تسک اولویت بالا (مثل )")
    LOGGER.info("- هیچ ساعتی ثبت نکرده (0 ساعت)")
    LOGGER.info("- 1 تسک اولویت بالا تحویل داده (1/7)")
    LOGGER.info("- تاخیر 28.8 روز")

    score2 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_days=28.8,  # 28.8 days late
        registered_hours=0,  # NO TIME REGISTERED
        expected_hours=38,
        completed_high_priority=1,  # 1 out of 7 high priority
        total_high_priority=7,
        support_bugs_per_story=0.0,
        tester_bugs_per_story=0.0,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS,
    )
    LOGGER.info(f"امتیاز: {score2}")
    LOGGER.info("انتظار: 0 (هیچ ساعتی ثبت نکرده)")

    # Test Case 3: Good developer
    LOGGER.info("\n📍 Test 3: توسعه‌دهنده خوب")
    LOGGER.info("- 40 ساعت ثبت کرده")
    LOGGER.info("- 3 تسک اولویت بالا تحویل داده (3/3)")
    LOGGER.info("- 1 روز تاخیر")

    score3 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_days=1.0,  # 1 day late
        registered_hours=40,
        expected_hours=38,
        completed_high_priority=3,
        total_high_priority=3,
        support_bugs_per_story=0.1,
        tester_bugs_per_story=0.1,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS,
    )
    LOGGER.info(f"امتیاز: {score3}")
    LOGGER.info("انتظار: حدود 85-95")

    # Test Case 4: Perfect developer with early delivery
    LOGGER.info("\n📍 Test 4: توسعه‌دهنده عالی با تحویل زودتر")
    LOGGER.info("- 46 ساعت ثبت کرده")
    LOGGER.info("- همه تسک‌های اولویت بالا تحویل داده")
    LOGGER.info("- 2 روز زودتر تحویل داده")

    score4 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_days=-2.0,  # 2 days early
        registered_hours=46,
        expected_hours=46,
        completed_high_priority=5,
        total_high_priority=5,
        support_bugs_per_story=0.0,
        tester_bugs_per_story=0.0,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS,
    )
    LOGGER.info(f"امتیاز: {score4}")
    LOGGER.info("انتظار: 100 (حداکثر)")

    # Test Case 5: Edge case - some hours but no high priority
    LOGGER.info("\n📍 Test 5: ساعت ثبت کرده اما تسک اولویت بالا ندارده")
    LOGGER.info("- 20 ساعت ثبت کرده")
    LOGGER.info("- هیچ تسک اولویت بالایی تحویل نداده (0/2)")

    score5 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_days=0,
        registered_hours=20,  # Some hours registered
        expected_hours=38,
        completed_high_priority=0,  # NO HIGH PRIORITY
        total_high_priority=2,
        support_bugs_per_story=0.0,
        tester_bugs_per_story=0.0,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS,
    )
    LOGGER.info(f"امتیاز: {score5}")
    LOGGER.info("انتظار: 0 (قانون: بدون تسک اولویت بالا = 0)")


if __name__ == "__main__":
    test_corrected_hosn_score()
