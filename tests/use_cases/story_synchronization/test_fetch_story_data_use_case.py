"""Unit tests for FetchStoryDataUseCase."""
import unittest
from datetime import datetime
from unittest.mock import Mock

from jira_telegram_bot.entities.story_synchronization import StorySheetRow
from jira_telegram_bot.use_cases.story_synchronization import (
    FetchStoryDataUseCase,
)


class TestFetchStoryDataUseCase(unittest.TestCase):
    """Test FetchStoryDataUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_task_manager = Mock()
        self.mock_user_config = Mock()
        self.jira_base_url = "https://jira.example.com"
        self.use_case = FetchStoryDataUseCase(
            task_manager=self.mock_task_manager,
            jira_base_url=self.jira_base_url,
            user_config=self.mock_user_config,
        )

    def test_build_jql_without_days_back(self):
        """Test JQL building without days_back filter."""
        jql = self.use_case._build_jql("TEST", None)
        self.assertIn('project = "TEST"', jql)
        self.assertIn("issuetype = Story", jql)
        self.assertIn("ORDER BY created DESC", jql)
        self.assertNotIn("updated >=", jql)

    def test_build_jql_with_days_back(self):
        """Test JQL building with days_back filter."""
        jql = self.use_case._build_jql("TEST", 7)
        self.assertIn('project = "TEST"', jql)
        self.assertIn("issuetype = Story", jql)
        self.assertIn("updated >=", jql)
        self.assertIn("ORDER BY created DESC", jql)

    def test_execute_returns_empty_list_when_no_issues(self):
        """Test execute returns empty list when no issues found."""
        self.mock_task_manager.search_for_issues.return_value = []

        result = self.use_case.execute("TEST")

        self.assertEqual(result, [])
        self.mock_task_manager.search_for_issues.assert_called_once()

    def test_execute_converts_issues_to_rows(self):
        """Test execute converts Jira issues to StorySheetRow entities."""
        mock_issue = self._create_mock_issue(
            key="TEST-1",
            summary="Test Story",
            status="In Progress",
        )
        self.mock_task_manager.search_for_issues.return_value = [mock_issue]
        self.mock_task_manager.jira_epic_link_id = "customfield_10014"
        self.mock_task_manager.jira_sprint_id = "customfield_10020"
        self.mock_task_manager.get_issue_with_expand.return_value = None

        result = self.use_case.execute("TEST")

        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], StorySheetRow)
        self.assertEqual(result[0].developer_board_issue_key, "TEST-1")
        self.assertEqual(result[0].task_title, "Test Story")

    def test_get_departments_from_components(self):
        """Test extracting departments from issue components."""
        mock_component = Mock()
        mock_component.name = "Backend"

        mock_issue = Mock()
        mock_issue.fields.components = [mock_component]

        result = self.use_case._get_departments(mock_issue)

        self.assertEqual(result, ["Backend"])

    def test_get_departments_converts_frontend(self):
        """Test Front-end component is converted to Frontend."""
        mock_component = Mock()
        mock_component.name = "Front-end"

        mock_issue = Mock()
        mock_issue.fields.components = [mock_component]

        result = self.use_case._get_departments(mock_issue)

        self.assertEqual(result, ["Frontend"])

    def test_get_worklog_data_aggregates_hours(self):
        """Test worklog data aggregation."""
        mock_issue = Mock()
        mock_issue.key = "TEST-1"

        mock_worklog_issue = Mock()
        mock_worklog1 = Mock()
        mock_worklog1.timeSpentSeconds = 3600
        mock_worklog1.author.name = "user1"

        mock_worklog2 = Mock()
        mock_worklog2.timeSpentSeconds = 7200
        mock_worklog2.author.name = "user2"

        mock_worklog_issue.fields.worklog.worklogs = [mock_worklog1, mock_worklog2]

        self.mock_task_manager.get_issue_with_expand.return_value = mock_worklog_issue

        mock_user_config1 = Mock()
        mock_user_config1.google_sheet_name = "User One"
        mock_user_config1.department = "Backend"

        mock_user_config2 = Mock()
        mock_user_config2.google_sheet_name = "User Two"
        mock_user_config2.department = "Frontend"

        def get_user_config_side_effect(username):
            if username == "user1":
                return mock_user_config1
            elif username == "user2":
                return mock_user_config2
            return None

        self.mock_user_config.get_user_config_by_jira_username.side_effect = (
            get_user_config_side_effect
        )

        progress_hours, involved_people, dept_hours, individual_hours = (
            self.use_case._get_worklog_data(mock_issue)
        )

        self.assertEqual(progress_hours, 3.0)
        self.assertIn("User One", involved_people)
        self.assertIn("User Two", involved_people)
        self.assertEqual(dept_hours["backend_hours"], 1.0)
        self.assertEqual(dept_hours["frontend_hours"], 2.0)
        self.assertEqual(individual_hours["User One"], 1.0)
        self.assertEqual(individual_hours["User Two"], 2.0)

    def test_get_time_tracking_returns_hours(self):
        """Test time tracking extraction."""
        mock_issue = Mock()
        mock_time_tracking = Mock()
        mock_time_tracking.originalEstimateSeconds = 28800
        mock_issue.fields.timetracking = mock_time_tracking
        mock_issue.fields.timeoriginalestimate = 28800

        eta_hours, total_hours = self.use_case._get_time_tracking(mock_issue)

        self.assertEqual(eta_hours, 8.0)
        self.assertEqual(total_hours, 8.0)

    def test_map_jira_status_to_sheet(self):
        """Test Jira status mapping to Persian sheet status."""
        result = self.use_case._map_jira_status_to_sheet("In Progress")
        self.assertEqual(result, "۶. در حال پیاده سازی")

        result = self.use_case._map_jira_status_to_sheet("Done")
        self.assertEqual(result, "۸. آماده تحویل")

        result = self.use_case._map_jira_status_to_sheet("Backlog")
        self.assertEqual(result, "۵. آماده پیاده سازی فنی")

        result = self.use_case._map_jira_status_to_sheet("Pause")
        self.assertEqual(result, "۶.۵ توقف پیاده سازی فنی")

        result = self.use_case._map_jira_status_to_sheet("Unknown Status")
        self.assertEqual(result, "Unknown Status")

    def test_get_linked_pm_issue(self):
        """Test extraction of linked PM board issue."""
        mock_issue = Mock()

        mock_outward_issue = Mock()
        mock_outward_issue.key = "PCD-123"

        mock_link = Mock()
        mock_link.outwardIssue = mock_outward_issue

        mock_issue.fields.issuelinks = [mock_link]

        result = self.use_case._get_linked_pm_issue(mock_issue)

        self.assertEqual(result, "PCD-123")

    def test_parse_jira_datetime_with_timezone(self):
        """Test parsing Jira datetime with timezone."""
        date_str = "2024-10-23T10:30:00.000+0000"
        result = self.use_case._parse_jira_datetime(date_str)
        self.assertIsInstance(result, datetime)

    def test_parse_jira_datetime_date_only(self):
        """Test parsing Jira date-only string."""
        date_str = "2024-10-23"
        result = self.use_case._parse_jira_datetime(date_str)
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 23)

    def test_parse_jira_datetime_none(self):
        """Test parsing None datetime."""
        result = self.use_case._parse_jira_datetime(None)
        self.assertIsNone(result)

    def _create_mock_issue(self, key, summary, status):
        """Create a mock Jira issue for testing."""
        mock_issue = Mock()
        mock_issue.key = key
        mock_issue.fields.summary = summary
        mock_issue.fields.status.name = status
        mock_issue.fields.created = "2024-10-23T10:00:00.000+0000"
        mock_issue.fields.description = "Test description"
        mock_issue.fields.priority.name = "High"
        mock_issue.fields.components = []
        mock_issue.fields.fixVersions = []
        mock_issue.fields.issuelinks = []
        mock_issue.fields.duedate = None
        return mock_issue


if __name__ == "__main__":
    unittest.main()
