#!/usr/bin/env python3
"""Test script for the new enhanced hosn score calculation."""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from jira_telegram_bot.entities.team_evaluation import TeamEvaluationScoreWeights
from jira_telegram_bot.use_cases.team_evaluation.services.score_service import ScoreService
from jira_telegram_bot.entities.constants import DEFAULT_DEFECT_THRESHOLDS

def test_enhanced_hosn_score():
    """Test the new hosn score calculation with enhanced high priority weighting."""
    
    # Default weights with new emphasis on high priority
    weights = TeamEvaluationScoreWeights()  # Uses new defaults
    
    print("=== تست محاسبه حسن انجام کار جدید ===\n")
    print(f"وزن‌های جدید: Deadline={weights.deadline}, Worklog={weights.worklog}, High Priority={weights.high_priority}, Defects={weights.defects}")
    print("=" * 60)
    
    # Test Case 1: Developer with NO high priority completion (SEVERE PENALTY)
    print("\n📍 Test 1: توسعه‌دهنده بدون تحویل تسک اولویت بالا")
    score1 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_hours=0,      # On time
        registered_hours=40,
        expected_hours=40,
        completed_high_priority=0,       # ZERO completion - باید امتیاز منفی بگیره
        total_high_priority=3,
        support_bugs_per_story=0.1,
        tester_bugs_per_story=0.2,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS
    )
    print(f"Score: {score1}")
    print("انتظار: امتیاز منفی یا خیلی پایین (تایم تلف شده)")
    
    # Test Case 2: Early delivery with good high priority completion
    print("\n📍 Test 2: تحویل زودتر از موعد + تسک‌های اولویت بالا")
    score2 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_hours=-48,    # 2 days early
        registered_hours=40,
        expected_hours=40,
        completed_high_priority=2,
        total_high_priority=2,
        support_bugs_per_story=0.1,
        tester_bugs_per_story=0.1,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS
    )
    print(f"Score: {score2}")
    print("انتظار: امتیاز بالا با بونوس تعجیل (> 100)")
    
    # Test Case 3: Late delivery (in days)
    print("\n📍 Test 3: تاخیر در تحویل (3 روز)")
    score3 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_hours=72,     # 3 days late
        registered_hours=35,
        expected_hours=40,
        completed_high_priority=1,
        total_high_priority=2,
        support_bugs_per_story=0.2,
        tester_bugs_per_story=0.3,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS
    )
    print(f"Score: {score3}")
    print("انتظار: امتیاز متوسط با کسر تاخیر")
    
    # Test Case 4: Below minimum high priority (< 1 per week)
    print("\n📍 Test 4: کمتر از حداقل تسک اولویت بالا")
    score4 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_hours=0,
        registered_hours=40,
        expected_hours=40,
        completed_high_priority=0,       # کمتر از حداقل
        total_high_priority=1,
        support_bugs_per_story=0.1,
        tester_bugs_per_story=0.1,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS
    )
    print(f"Score: {score4}")
    print("انتظار: امتیاز خیلی پایین")
    
    # Test Case 5: Perfect developer (early + all high priority + no defects)
    print("\n📍 Test 5: توسعه‌دهنده عالی")
    score5 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_hours=-24,    # 1 day early
        registered_hours=46,
        expected_hours=46,
        completed_high_priority=3,
        total_high_priority=3,
        support_bugs_per_story=0.0,
        tester_bugs_per_story=0.0,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS
    )
    print(f"Score: {score5}")
    print("انتظار: امتیاز بسیار بالا (نزدیک 110)")
    
    # Test Case 6: No high priority tasks assigned
    print("\n📍 Test 6: بدون تسک اولویت بالا")
    score6 = ScoreService.compute_hosn_score(
        weights=weights,
        avg_deadline_delta_hours=0,
        registered_hours=40,
        expected_hours=40,
        completed_high_priority=0,
        total_high_priority=0,           # هیچ تسک اولویت بالایی اساین نشده
        support_bugs_per_story=0.1,
        tester_bugs_per_story=0.1,
        defect_thresholds=DEFAULT_DEFECT_THRESHOLDS
    )
    print(f"Score: {score6}")
    print("انتظار: امتیاز خنثی (حدود 80-90)")
    
    print("\n" + "=" * 60)
    print("تغییرات اصلی:")
    print("✅ وزن تسک‌های اولویت بالا از 20% به 40% افزایش یافت")
    print("✅ عدم تحویل هیچ تسک اولویت بالا = امتیاز -50")
    print("✅ تحویل زودتر از موعد = بونوس تا 110")
    print("✅ محاسبه تاخیر بر اساس روز")

if __name__ == "__main__":
    test_enhanced_hosn_score()
