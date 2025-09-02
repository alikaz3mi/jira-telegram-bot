#!/usr/bin/env python3
"""Test script for the corrected hosn score calculation."""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from jira_telegram_bot.entities.team_evaluation import TeamEvaluationScoreWeights
from jira_telegram_bot.use_cases.team_evaluation.services.score_service import ScoreService
from jira_telegram_bot.entities.constants import DEFAULT_DEFECT_THRESHOLDS

def test_corrected_hosn_score():
    """Test the corrected hosn score calculation."""
    
    weights = TeamEvaluationScoreWeights()
    
    print("=== تست محاسبه حسن انجام کار اصلاح شده ===\n")
    print("محدودیت‌ها:")
    print("✅ امتیاز بین 0 تا 100")
    print("✅ بدون فعالیت = امتیاز 0")
    print("✅ ورودی بر اساس روز")
    print("=" * 60)
    
    # Test Case 1: No activity (like هروی)
    print("\n📍 Test 1: بدون فعالیت (مثل هروی)")
    print("- هیچ ساعتی ثبت نکرده (0 ساعت)")
    print("- هیچ تسک اولویت بالایی تحویل نداده (0/1)")
    
    score1 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_days=0,       # No deadlines to evaluate
        registered_hours=0,              # NO TIME REGISTERED
        expected_hours=38,
        completed_high_priority=0,       # NO HIGH PRIORITY COMPLETED
        total_high_priority=1,
        support_bugs_per_story=0.0,
        tester_bugs_per_story=0.0,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS
    )
    print(f"امتیاز: {score1}")
    print("انتظار: 0 (هیچ کاری نکرده)")
    
    # Test Case 2: Some activity but no high priority (like )
    print("\n📍 Test 2: فعالیت بدون تسک اولویت بالا (مثل )")
    print("- هیچ ساعتی ثبت نکرده (0 ساعت)")
    print("- 1 تسک اولویت بالا تحویل داده (1/7)")
    print("- تاخیر 28.8 روز")
    
    score2 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_days=28.8,    # 28.8 days late
        registered_hours=0,              # NO TIME REGISTERED
        expected_hours=38,
        completed_high_priority=1,       # 1 out of 7 high priority
        total_high_priority=7,
        support_bugs_per_story=0.0,
        tester_bugs_per_story=0.0,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS
    )
    print(f"امتیاز: {score2}")
    print("انتظار: 0 (هیچ ساعتی ثبت نکرده)")
    
    # Test Case 3: Good developer
    print("\n📍 Test 3: توسعه‌دهنده خوب")
    print("- 40 ساعت ثبت کرده")
    print("- 3 تسک اولویت بالا تحویل داده (3/3)")
    print("- 1 روز تاخیر")
    
    score3 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_days=1.0,     # 1 day late
        registered_hours=40,
        expected_hours=38,
        completed_high_priority=3,
        total_high_priority=3,
        support_bugs_per_story=0.1,
        tester_bugs_per_story=0.1,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS
    )
    print(f"امتیاز: {score3}")
    print("انتظار: حدود 85-95")
    
    # Test Case 4: Perfect developer with early delivery
    print("\n📍 Test 4: توسعه‌دهنده عالی با تحویل زودتر")
    print("- 46 ساعت ثبت کرده")
    print("- همه تسک‌های اولویت بالا تحویل داده")
    print("- 2 روز زودتر تحویل داده")
    
    score4 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_days=-2.0,    # 2 days early
        registered_hours=46,
        expected_hours=46,
        completed_high_priority=5,
        total_high_priority=5,
        support_bugs_per_story=0.0,
        tester_bugs_per_story=0.0,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS
    )
    print(f"امتیاز: {score4}")
    print("انتظار: 100 (حداکثر)")
    
    # Test Case 5: Edge case - some hours but no high priority
    print("\n📍 Test 5: ساعت ثبت کرده اما تسک اولویت بالا ندارده")
    print("- 20 ساعت ثبت کرده")
    print("- هیچ تسک اولویت بالایی تحویل نداده (0/2)")
    
    score5 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_days=0,
        registered_hours=20,             # Some hours registered
        expected_hours=38,
        completed_high_priority=0,       # NO HIGH PRIORITY
        total_high_priority=2,
        support_bugs_per_story=0.0,
        tester_bugs_per_story=0.0,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS
    )
    print(f"امتیاز: {score5}")
    print("انتظار: 0 (قانون: بدون تسک اولویت بالا = 0)")

if __name__ == "__main__":
    test_corrected_hosn_score()
