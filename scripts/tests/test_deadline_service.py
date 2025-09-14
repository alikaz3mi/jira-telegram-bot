"""Test script for deadline service with changelog data."""
from __future__ import annotations

import os
import sys
from datetime import datetime
from datetime import timedelta
from datetime import timezone

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from jira_telegram_bot.entities.team_evaluation import IssueSnapshot, ChangeLogEvent
from jira_telegram_bot.use_cases.team_evaluation.services.deadline_service import (
    DeadlineService,
)


def test_deadline_service():
    """Test the deadline service with sample data."""

    # Create test data with timezone issues
    base_time = datetime.now()
    due_date_naive = base_time - timedelta(days=1)  # Due yesterday (naive)
    delivery_time_aware = base_time.replace(
        tzinfo=timezone.utc,
    )  # Delivered today (aware)

    print("Testing timezone handling...")
    print(f"Due date (naive): {due_date_naive} - tzinfo: {due_date_naive.tzinfo}")
    print(
        f"Delivery time (aware): {delivery_time_aware} - tzinfo: {delivery_time_aware.tzinfo}",
    )

    # Sample issue with naive due date
    issue = IssueSnapshot(
        key="TEST-123",
        issue_type="Task",
        priority="High",
        labels=[],
        components=[],
        epic_key=None,
        epic_name=None,
        due_date=due_date_naive,  # Naive datetime
        status="Done",
        assignee="testuser",
        project_key="TEST",
        project_name="Test Project",
        resolution_date=None,
        created_date=base_time - timedelta(days=5),
        updated_date=delivery_time_aware,
        linked_issues=[],
    )

    # Sample changelog showing move to Done with aware datetime
    changelog = ChangeLogEvent(
        issue_key="TEST-123",
        field="status",
        from_status="In Progress",
        to_status="Done",
        changed_at=delivery_time_aware,  # Aware datetime
        author="testuser",
    )

    issues = [issue]
    changelogs = {"TEST-123": [changelog]}

    # Test the service
    try:
        avg_delta = DeadlineService.average_deadline_delta_hours(issues, changelogs)
        print(f"\n✅ Test PASSED: No timezone error occurred")
        print(f"Calculated Delta: {avg_delta} hours")

        # Should be approximately 24 hours (1 day late)
        if avg_delta and abs(avg_delta - 24.0) < 2.0:  # Allow 2 hour tolerance
            print("✅ Calculation appears correct (approximately 24 hours late)")
        else:
            print(f"⚠️  Calculation might be off: expected ~24h, got {avg_delta}h")

    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return

    # Test case with mixed timezone scenarios
    print("\n" + "=" * 50)
    print("Testing mixed timezone scenarios...")

    # Test with both naive datetimes
    due_date_naive2 = base_time - timedelta(hours=12)
    delivery_time_naive = base_time

    issue2 = IssueSnapshot(
        key="TEST-124",
        issue_type="Task",
        priority="High",
        labels=[],
        components=[],
        epic_key=None,
        epic_name=None,
        due_date=due_date_naive2,  # Naive
        status="Done",
        assignee="testuser",
        project_key="TEST",
        project_name="Test Project",
        resolution_date=None,
        created_date=base_time - timedelta(days=5),
        updated_date=delivery_time_naive,
        linked_issues=[],
    )

    changelog2 = ChangeLogEvent(
        issue_key="TEST-124",
        field="status",
        from_status="In Progress",
        to_status="Done",
        changed_at=delivery_time_naive,  # Naive
        author="testuser",
    )

    issues2 = [issue2]
    changelogs2 = {"TEST-124": [changelog2]}

    try:
        avg_delta2 = DeadlineService.average_deadline_delta_hours(issues2, changelogs2)
        print(f"✅ Both naive datetimes handled successfully")
        print(f"Expected: 12h late, Calculated: {avg_delta2}h")

    except Exception as e:
        print(f"❌ Mixed datetime test FAILED: {e}")


if __name__ == "__main__":
    test_deadline_service()
