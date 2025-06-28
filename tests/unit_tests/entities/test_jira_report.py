"""Unit tests for Jira report entities."""
from __future__ import annotations

import unittest
from datetime import datetime

from jira_telegram_bot.entities.jira_report import JiraIssueDetail
from jira_telegram_bot.entities.jira_report import LinkedIssue
from jira_telegram_bot.entities.jira_report import ProjectReport
from jira_telegram_bot.entities.jira_report import WorklogEntry
from tests.samples.jira_report_test_factory import JiraReportTestFactory


class TestWorklogEntry(unittest.TestCase):
    """Test cases for WorklogEntry entity."""

    def test_worklog_entry_creation(self):
        """Test worklog entry creation with all fields."""
        entry = WorklogEntry(
            id="12345",
            author="Test User",
            time_spent="2h 30m",
            time_spent_seconds=9000,
            created=datetime(2025, 6, 27, 10, 0, 0),
            updated=datetime(2025, 6, 27, 10, 30, 0),
            started=datetime(2025, 6, 27, 9, 0, 0),
            comment="Test comment",
        )
        
        self.assertEqual(entry.id, "12345")
        self.assertEqual(entry.author, "Test User")
        self.assertEqual(entry.time_spent, "2h 30m")
        self.assertEqual(entry.time_spent_seconds, 9000)
        self.assertEqual(entry.comment, "Test comment")

    def test_worklog_entry_without_comment(self):
        """Test worklog entry creation without comment."""
        entry = WorklogEntry(
            id="12345",
            author="Test User",
            time_spent="1h",
            created=datetime(2025, 6, 27, 10, 0, 0),
            updated=datetime(2025, 6, 27, 10, 30, 0),
            started=datetime(2025, 6, 27, 9, 0, 0),
        )
        
        self.assertIsNone(entry.comment)
        self.assertIsNone(entry.time_spent_seconds)

    def test_worklog_entry_factory(self):
        """Test worklog entry creation using factory."""
        entry = JiraReportTestFactory.create_worklog_entry()
        
        self.assertEqual(entry.id, "12345")
        self.assertEqual(entry.author, "Test User")
        self.assertEqual(entry.time_spent, "2h 30m")


class TestLinkedIssue(unittest.TestCase):
    """Test cases for LinkedIssue entity."""

    def test_linked_issue_creation(self):
        """Test linked issue creation with all fields."""
        linked = LinkedIssue(
            key="TEST-2",
            summary="Linked issue",
            status="Open",
            issue_type="Bug",
            relationship="blocks",
        )
        
        self.assertEqual(linked.key, "TEST-2")
        self.assertEqual(linked.summary, "Linked issue")
        self.assertEqual(linked.status, "Open")
        self.assertEqual(linked.issue_type, "Bug")
        self.assertEqual(linked.relationship, "blocks")

    def test_linked_issue_factory(self):
        """Test linked issue creation using factory."""
        linked = JiraReportTestFactory.create_linked_issue()
        
        self.assertEqual(linked.key, "TEST-2")
        self.assertEqual(linked.relationship, "blocks")


class TestJiraIssueDetail(unittest.TestCase):
    """Test cases for JiraIssueDetail entity."""

    def test_jira_issue_detail_creation(self):
        """Test Jira issue detail creation with all fields."""
        issue = JiraIssueDetail(
            key="TEST-1",
            summary="Test issue",
            task_type="Story",
            reporter="Test Reporter",
            status="Open",
            created_at=datetime(2025, 6, 27, 10, 0, 0),
            updated_at=datetime(2025, 6, 27, 11, 0, 0),
        )
        
        self.assertEqual(issue.key, "TEST-1")
        self.assertEqual(issue.summary, "Test issue")
        self.assertEqual(issue.task_type, "Story")
        self.assertEqual(issue.reporter, "Test Reporter")
        self.assertEqual(issue.status, "Open")

    def test_jira_issue_detail_with_collections(self):
        """Test Jira issue detail with worklog and linked issues."""
        worklog = JiraReportTestFactory.create_worklog_entry()
        linked = JiraReportTestFactory.create_linked_issue()
        
        issue = JiraIssueDetail(
            key="TEST-1",
            summary="Test issue",
            task_type="Story",
            reporter="Test Reporter",
            status="Open",
            created_at=datetime(2025, 6, 27, 10, 0, 0),
            updated_at=datetime(2025, 6, 27, 11, 0, 0),
            worklog_entries=[worklog],
            linked_issues=[linked],
            components=["Frontend"],
            labels=["urgent"],
            release=["v1.0.0"],
        )
        
        self.assertEqual(len(issue.worklog_entries), 1)
        self.assertEqual(len(issue.linked_issues), 1)
        self.assertEqual(issue.components, ["Frontend"])
        self.assertEqual(issue.labels, ["urgent"])
        self.assertEqual(issue.release, ["v1.0.0"])

    def test_jira_issue_detail_defaults(self):
        """Test Jira issue detail with default values."""
        issue = JiraIssueDetail(
            key="TEST-1",
            summary="Test issue",
            task_type="Story",
            reporter="Test Reporter",
            status="Open",
            created_at=datetime(2025, 6, 27, 10, 0, 0),
            updated_at=datetime(2025, 6, 27, 11, 0, 0),
        )
        
        self.assertEqual(issue.comments, "")
        self.assertEqual(issue.last_sprint, "Backlog")
        self.assertEqual(issue.sprint_repeats, 0)
        self.assertEqual(len(issue.worklog_entries), 0)
        self.assertEqual(len(issue.linked_issues), 0)
        self.assertEqual(len(issue.components), 0)
        self.assertEqual(len(issue.labels), 0)
        self.assertEqual(len(issue.release), 0)

    def test_jira_issue_detail_factory(self):
        """Test Jira issue detail creation using factory."""
        issue = JiraReportTestFactory.create_jira_issue_detail()
        
        self.assertEqual(issue.key, "TEST-1")
        self.assertIsNotNone(issue.epic_name)
        self.assertGreater(len(issue.worklog_entries), 0)
        self.assertGreater(len(issue.linked_issues), 0)


class TestProjectReport(unittest.TestCase):
    """Test cases for ProjectReport entity."""

    def test_project_report_creation(self):
        """Test project report creation."""
        issues = JiraReportTestFactory.create_multiple_issues(3)
        
        report = ProjectReport(
            project_key="TEST",
            generated_at=datetime(2025, 6, 27, 12, 0, 0),
            total_issues=3,
            issues=issues,
        )
        
        self.assertEqual(report.project_key, "TEST")
        self.assertEqual(report.total_issues, 3)
        self.assertEqual(len(report.issues), 3)

    def test_project_report_empty(self):
        """Test project report with no issues."""
        report = ProjectReport(
            project_key="EMPTY",
            generated_at=datetime(2025, 6, 27, 12, 0, 0),
            total_issues=0,
            issues=[],
        )
        
        self.assertEqual(report.project_key, "EMPTY")
        self.assertEqual(report.total_issues, 0)
        self.assertEqual(len(report.issues), 0)

    def test_project_report_factory(self):
        """Test project report creation using factory."""
        report = JiraReportTestFactory.create_project_report("TEST", 5)
        
        self.assertEqual(report.project_key, "TEST")
        self.assertEqual(report.total_issues, 5)
        self.assertEqual(len(report.issues), 5)


if __name__ == "__main__":
    unittest.main()
