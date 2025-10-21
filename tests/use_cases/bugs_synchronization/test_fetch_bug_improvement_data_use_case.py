"""Unit tests for FetchBugImprovementDataUseCase."""
import unittest
from datetime import datetime
from datetime import timedelta
from unittest.mock import MagicMock
from unittest.mock import Mock

from jira_telegram_bot.entities.bugs_synchronization import BugImprovementSheetRow
from jira_telegram_bot.use_cases.bugs_synchronization import (
    FetchBugImprovementDataUseCase,
)


class TestFetchBugImprovementDataUseCase(unittest.TestCase):
    """Test FetchBugImprovementDataUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_task_manager = Mock()
        self.jira_base_url = "https://jira.example.com"
        self.use_case = FetchBugImprovementDataUseCase(
            task_manager=self.mock_task_manager,
            jira_base_url=self.jira_base_url,
        )

    def test_build_jql_without_days_back(self):
        """Test JQL building without days_back filter."""
        jql = self.use_case._build_jql("TEST", None)
        self.assertIn('project = "TEST"', jql)
        self.assertIn("issuetype in (Bug, Improvement)", jql)
        self.assertIn("ORDER BY created DESC", jql)
        self.assertNotIn("updated >=", jql)

    def test_build_jql_with_days_back(self):
        """Test JQL building with days_back filter."""
        jql = self.use_case._build_jql("TEST", 7)
        self.assertIn('project = "TEST"', jql)
        self.assertIn("issuetype in (Bug, Improvement)", jql)
        self.assertIn("updated >=", jql)
        self.assertIn("ORDER BY created DESC", jql)

    def test_execute_returns_empty_list_when_no_issues(self):
        """Test execute returns empty list when no issues found."""
        self.mock_task_manager.search_for_issues.return_value = []

        result = self.use_case.execute("TEST")

        self.assertEqual(result, [])
        self.mock_task_manager.search_for_issues.assert_called_once()

    def test_execute_converts_issues_to_rows(self):
        """Test execute converts Jira issues to BugImprovementSheetRow entities."""
        mock_issue = self._create_mock_issue(
            key="TEST-1",
            summary="Test Bug",
            status="Open",
        )
        self.mock_task_manager.search_for_issues.return_value = [mock_issue]
        self.mock_task_manager.jira_epic_link_id = "customfield_10014"
        self.mock_task_manager.jira_sprint_id = "customfield_10020"

        result = self.use_case.execute("TEST")

        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], BugImprovementSheetRow)
        self.assertEqual(result[0].issue_key, "TEST-1")
        self.assertEqual(result[0].task_title, "Test Bug")
        self.assertEqual(result[0].status, "Open")

    def test_get_departments_from_components(self):
        """Test extracting departments from issue components."""
        mock_component = Mock()
        mock_component.name = "Backend"

        mock_issue = Mock()
        mock_issue.fields.components = [mock_component]

        result = self.use_case._get_departments(mock_issue)

        self.assertEqual(result, ["Backend"])

    def test_get_departments_returns_empty_when_no_components(self):
        """Test _get_departments returns empty list when no components."""
        mock_issue = Mock()
        mock_issue.fields.components = []

        result = self.use_case._get_departments(mock_issue)

        self.assertEqual(result, [])

    def test_parse_jira_datetime_with_milliseconds(self):
        """Test parsing Jira datetime with milliseconds."""
        date_str = "2024-01-15T10:30:45.123+0000"
        result = self.use_case._parse_jira_datetime(date_str)

        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

    def test_parse_jira_datetime_without_milliseconds(self):
        """Test parsing Jira datetime without milliseconds."""
        date_str = "2024-01-15T10:30:45+0000"
        result = self.use_case._parse_jira_datetime(date_str)

        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2024)

    def test_parse_jira_datetime_returns_none_for_invalid(self):
        """Test parsing invalid datetime returns None."""
        result = self.use_case._parse_jira_datetime("invalid-date")
        self.assertIsNone(result)

    def test_parse_jira_datetime_returns_none_for_empty(self):
        """Test parsing empty datetime returns None."""
        result = self.use_case._parse_jira_datetime(None)
        self.assertIsNone(result)

    def _create_mock_issue(self, key, summary, status):
        """Create a mock Jira issue for testing.

        Args:
            key: Issue key.
            summary: Issue summary.
            status: Issue status.

        Returns:
            Mock Jira issue.
        """
        mock_issue = Mock()
        mock_issue.key = key
        mock_issue.fields.summary = summary
        mock_issue.fields.description = "Test description"
        mock_issue.fields.status.name = status
        mock_issue.fields.created = "2024-01-15T10:30:45.123+0000"
        mock_issue.fields.priority = None
        mock_issue.fields.components = []
        mock_issue.fields.fixVersions = []
        mock_issue.fields.assignee = None
        mock_issue.fields.subtasks = []
        mock_issue.fields.issuelinks = []

        return mock_issue


if __name__ == "__main__":
    unittest.main()
