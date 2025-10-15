from __future__ import annotations

import unittest
from datetime import datetime

from jira_telegram_bot.entities.deadline_alert import DeadlineAlert


class TestDeadlineAlert(unittest.TestCase):
    """Test cases for DeadlineAlert entity."""

    def test_is_in_review_with_review_status(self):
        """Test is_in_review returns True for review status."""
        alert = DeadlineAlert(
            issue_key="TEST-123",
            summary="Test issue",
            assignee="john.doe",
            reporter="jane.smith",
            due_date=datetime.now(),
            days_remaining=1,
            project_key="TEST",
            status="In Review",
            priority="High",
            issue_url="http://test.com",
            issue_type="Story",
        )

        self.assertTrue(alert.is_in_review)

    def test_is_in_review_with_review_lowercase(self):
        """Test is_in_review returns True for lowercase review."""
        alert = DeadlineAlert(
            issue_key="TEST-123",
            summary="Test issue",
            assignee="john.doe",
            reporter="jane.smith",
            due_date=datetime.now(),
            days_remaining=1,
            project_key="TEST",
            status="review",
            priority="High",
            issue_url="http://test.com",
            issue_type="Story",
        )

        self.assertTrue(alert.is_in_review)

    def test_is_in_review_with_persian_review(self):
        """Test is_in_review returns True for Persian review status."""
        alert = DeadlineAlert(
            issue_key="TEST-123",
            summary="Test issue",
            assignee="john.doe",
            reporter="jane.smith",
            due_date=datetime.now(),
            days_remaining=1,
            project_key="TEST",
            status="در حال بررسی",
            priority="High",
            issue_url="http://test.com",
            issue_type="Story",
        )

        self.assertTrue(alert.is_in_review)

    def test_is_in_review_with_non_review_status(self):
        """Test is_in_review returns False for non-review status."""
        alert = DeadlineAlert(
            issue_key="TEST-123",
            summary="Test issue",
            assignee="john.doe",
            reporter="jane.smith",
            due_date=datetime.now(),
            days_remaining=1,
            project_key="TEST",
            status="In Progress",
            priority="High",
            issue_url="http://test.com",
            issue_type="Story",
        )

        self.assertFalse(alert.is_in_review)

    def test_is_in_review_with_none_status(self):
        """Test is_in_review returns False for None status."""
        alert = DeadlineAlert(
            issue_key="TEST-123",
            summary="Test issue",
            assignee="john.doe",
            reporter="jane.smith",
            due_date=datetime.now(),
            days_remaining=1,
            project_key="TEST",
            status="",
            priority="High",
            issue_url="http://test.com",
            issue_type="Story",
        )

        self.assertFalse(alert.is_in_review)

    def test_reporter_field_optional(self):
        """Test that reporter field is optional."""
        alert = DeadlineAlert(
            issue_key="TEST-123",
            summary="Test issue",
            assignee="john.doe",
            due_date=datetime.now(),
            days_remaining=1,
            project_key="TEST",
            status="In Progress",
            priority="High",
            issue_url="http://test.com",
            issue_type="Story",
        )

        self.assertIsNone(alert.reporter)

    def test_effective_deadline_prefers_due_date(self):
        """Test that effective_deadline returns due_date when both are set."""
        due_date = datetime(2025, 10, 20)
        target_end = datetime(2025, 10, 25)

        alert = DeadlineAlert(
            issue_key="TEST-123",
            summary="Test issue",
            assignee="john.doe",
            reporter="jane.smith",
            due_date=due_date,
            target_end=target_end,
            days_remaining=5,
            project_key="TEST",
            status="In Progress",
            priority="High",
            issue_url="http://test.com",
            issue_type="Story",
        )

        self.assertEqual(alert.effective_deadline, due_date)


if __name__ == "__main__":
    unittest.main()
