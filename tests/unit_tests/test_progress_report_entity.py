import unittest
from datetime import datetime

from pydantic import ValidationError
from jira_telegram_bot.entities.progress_reports.progress_report import ProgressReport


class TestProgressReport(unittest.TestCase):
    """Test cases for ProgressReport entity."""

    def test_create_progress_report_with_required_fields(self):
        """Test creating a progress report with only required fields."""
        report = ProgressReport(
            issue_key="PROJ-123",
            progress="Implemented user authentication",
            blockers="None",
            time_spent="2h"
        )
        
        self.assertEqual(report.issue_key, "PROJ-123")
        self.assertEqual(report.progress, "Implemented user authentication")
        self.assertEqual(report.blockers, "None")
        self.assertEqual(report.time_spent, "2h")
        self.assertIsNone(report.assignee)
        self.assertIsNone(report.reported_at)
        self.assertIsNone(report.report_id)

    def test_create_progress_report_with_all_fields(self):
        """Test creating a progress report with all fields."""
        timestamp = datetime.utcnow()
        
        report = ProgressReport(
            issue_key="PROJ-456",
            progress="Fixed critical bug in payment system",
            blockers="Waiting for QA approval",
            time_spent="4h",
            assignee="john_doe",
            reported_at=timestamp,
            report_id="uuid-123-456"
        )
        
        self.assertEqual(report.issue_key, "PROJ-456")
        self.assertEqual(report.progress, "Fixed critical bug in payment system")
        self.assertEqual(report.blockers, "Waiting for QA approval")
        self.assertEqual(report.time_spent, "4h")
        self.assertEqual(report.assignee, "john_doe")
        self.assertEqual(report.reported_at, timestamp)
        self.assertEqual(report.report_id, "uuid-123-456")

    def test_progress_report_immutability(self):
        """Test that ProgressReport is immutable."""
        report = ProgressReport(
            issue_key="PROJ-789",
            progress="Working on feature",
            blockers="None",
            time_spent="1h"
        )
        
        with self.assertRaises(ValidationError):
            report.issue_key = "PROJ-999"

    def test_progress_report_json_serialization(self):
        """Test JSON serialization of ProgressReport."""
        timestamp = datetime(2023, 12, 25, 15, 30, 0)
        
        report = ProgressReport(
            issue_key="PROJ-111",
            progress="Code review completed",
            blockers="None",
            time_spent="30m",
            assignee="jane_smith",
            reported_at=timestamp,
            report_id="test-uuid"
        )
        
        json_data = report.dict()
        
        self.assertEqual(json_data["issue_key"], "PROJ-111")
        self.assertEqual(json_data["progress"], "Code review completed")
        self.assertEqual(json_data["blockers"], "None")
        self.assertEqual(json_data["time_spent"], "30m")
        self.assertEqual(json_data["assignee"], "jane_smith")
        self.assertEqual(json_data["reported_at"], timestamp)
        self.assertEqual(json_data["report_id"], "test-uuid")

    def test_progress_report_from_dict(self):
        """Test creating ProgressReport from dictionary."""
        data = {
            "issue_key": "PROJ-222",
            "progress": "Database migration completed",
            "blockers": "Performance issues with large datasets",
            "time_spent": "6h",
            "assignee": "bob_wilson",
            "reported_at": datetime(2023, 12, 25, 16, 0, 0),
            "report_id": "report-456"
        }
        
        report = ProgressReport(**data)
        
        self.assertEqual(report.issue_key, "PROJ-222")
        self.assertEqual(report.progress, "Database migration completed")
        self.assertEqual(report.blockers, "Performance issues with large datasets")
        self.assertEqual(report.time_spent, "6h")
        self.assertEqual(report.assignee, "bob_wilson")
        self.assertEqual(report.reported_at, datetime(2023, 12, 25, 16, 0, 0))
        self.assertEqual(report.report_id, "report-456")


if __name__ == '__main__':
    unittest.main()
