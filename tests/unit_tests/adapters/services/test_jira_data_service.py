"""Unit tests for JiraDataService."""
from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from jira_telegram_bot.adapters.services.jira_data_service import JiraDataService
from jira_telegram_bot.entities.jira_report import JiraIssueDetail
from tests.samples.jira_report_test_factory import JiraReportTestFactory


class MockJiraIssue:
    """Mock Jira issue for testing."""

    def __init__(self, key: str = "TEST-1"):
        self.key = key
        self.fields = MockJiraFields()


class MockJiraFields:
    """Mock Jira issue fields for testing."""

    def __init__(self):
        self.summary = "Test Issue Summary"
        self.description = "Test Description"
        self.issuetype = MockIssueType()
        self.assignee = MockUser("Test Assignee")
        self.reporter = MockUser("Test Reporter")
        self.priority = MockPriority()
        self.status = MockStatus()
        self.created = "2025-06-20T10:00:00.000+0000"
        self.updated = "2025-06-27T10:00:00.000+0000"
        self.resolutiondate = None
        self.duedate = "2025-07-01T23:59:59.000+0000"
        self.project = MockProject("RADTHARN")
        self.components = [MockComponent("Frontend")]
        self.labels = ["urgent", "feature"]
        self.fixVersions = [MockVersion("v1.0.0")]
        self.comment = MockCommentCollection()
        self.customfield_10100 = "EPIC-1"  # Epic link
        self.customfield_10104 = ["Sprint 1"]  # Sprint
        self.customfield_10106 = 5.0  # Story points
        self.customfield_10109 = "2025-06-25T09:00:00.000+0000"  # Target start
        self.customfield_10110 = "2025-06-30T17:00:00.000+0000"  # Target end
        self.timetracking = MockTimeTracking()
        self.worklog = MockWorklogCollection()
        self.issuelinks = []


class MockIssueType:
    """Mock issue type."""

    def __init__(self, name: str = "Story"):
        self.name = name


class MockUser:
    """Mock user."""

    def __init__(self, display_name: str):
        self.displayName = display_name


class MockPriority:
    """Mock priority."""

    def __init__(self, name: str = "High"):
        self.name = name


class MockStatus:
    """Mock status."""

    def __init__(self, name: str = "In Progress"):
        self.name = name


class MockComponent:
    """Mock component."""

    def __init__(self, name: str):
        self.name = name


class MockVersion:
    """Mock version."""

    def __init__(self, name: str):
        self.name = name


class MockProject:
    """Mock project."""

    def __init__(self, key: str):
        self.key = key


class MockComment:
    """Mock comment."""

    def __init__(self, author_name: str, body: str):
        self.author = MockUser(author_name)
        self.body = body


class MockCommentCollection:
    """Mock comment collection."""

    def __init__(self):
        self.comments = [
            MockComment("User A", "First comment"),
            MockComment("User B", "Second comment"),
        ]


class MockTimeTracking:
    """Mock time tracking."""

    def __init__(self):
        self.originalEstimate = "3d"
        self.remainingEstimate = "1d"


class MockWorklog:
    """Mock worklog entry."""

    def __init__(self):
        self.id = "12345"
        self.author = MockUser("Test User")
        self.timeSpent = "2h"
        self.timeSpentSeconds = 7200
        self.created = "2025-06-27T10:00:00.000+0000"
        self.updated = "2025-06-27T10:30:00.000+0000"
        self.started = "2025-06-27T09:00:00.000+0000"
        self.comment = "Test worklog"


class MockWorklogCollection:
    """Mock worklog collection."""

    def __init__(self):
        self.worklogs = [MockWorklog()]


class TestJiraDataService(unittest.IsolatedAsyncioTestCase):
    """Test cases for JiraDataService."""

    def setUp(self):
        """Set up test dependencies."""
        self.mock_repository = MagicMock()
        self.service = JiraDataService(self.mock_repository)

    async def test_a_fetch_project_issues_success(self):
        """Test successful project issues fetching."""
        project_key = "TEST"
        mock_issues = [MockJiraIssue("TEST-1"), MockJiraIssue("TEST-2")]

        self.mock_repository.search_issues.return_value = mock_issues

        result = await self.service.fetch_project_issues(project_key)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        for issue in result:
            self.assertIsInstance(issue, JiraIssueDetail)

        self.mock_repository.search_issues.assert_called()

    async def test_a_fetch_project_issues_pagination(self):
        """Test project issues fetching with pagination."""
        project_key = "TEST"

        # Mock pagination: first call returns 100 issues, second returns 50
        first_batch = [MockJiraIssue(f"TEST-{i}") for i in range(1, 101)]
        second_batch = [MockJiraIssue(f"TEST-{i}") for i in range(101, 151)]

        call_count = 0
        def search_issues_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First two calls are pagination
            if call_count == 1:
                return first_batch
            elif call_count == 2:
                return second_batch
            # All subsequent calls are epic lookups, return empty
            else:
                return []
        
        self.mock_repository.search_issues.side_effect = search_issues_side_effect

        result = await self.service.fetch_project_issues(project_key)

        self.assertEqual(len(result), 150)
        # Expect 2 pagination calls + 150 epic lookup calls = 152 total
        self.assertEqual(self.mock_repository.search_issues.call_count, 152)

    async def test_a_fetch_project_issues_no_issues(self):
        """Test project issues fetching with no issues."""
        project_key = "EMPTY"

        self.mock_repository.search_issues.return_value = []

        result = await self.service.fetch_project_issues(project_key)

        self.assertEqual(len(result), 0)

    async def test_a_fetch_project_issues_filters_epics(self):
        """Test that Epic issues are filtered out."""
        project_key = "TEST"
        epic_issue = MockJiraIssue("EPIC-1")
        epic_issue.fields.issuetype.name = "Epic"
        story_issue = MockJiraIssue("TEST-1")

        self.mock_repository.search_issues.return_value = [epic_issue, story_issue]

        result = await self.service.fetch_project_issues(project_key)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].key, "TEST-1")

    async def test_a_fetch_issue_details_success(self):
        """Test successful single issue fetching."""
        issue_key = "TEST-1"
        mock_issue = MockJiraIssue(issue_key)
        epic_issue = MockJiraIssue("EPIC-1")
        epic_issue.fields.summary = "Test Epic"

        self.mock_repository.get_issue_with_expand.return_value = mock_issue
        self.mock_repository.get_issue.return_value = epic_issue

        result = await self.service.fetch_issue_details(issue_key)

        self.assertIsInstance(result, JiraIssueDetail)
        self.assertEqual(result.key, issue_key)
        self.assertEqual(result.epic_name, "Test Epic")

    async def test_a_fetch_issue_details_no_epic(self):
        """Test issue fetching when no epic is linked."""
        issue_key = "TEST-1"
        mock_issue = MockJiraIssue(issue_key)
        mock_issue.fields.customfield_10100 = None

        self.mock_repository.get_issue_with_expand.return_value = mock_issue

        result = await self.service.fetch_issue_details(issue_key)

        self.assertIsInstance(result, JiraIssueDetail)
        self.assertIsNone(result.epic_name)

    def test_extract_epics(self):
        """Test epic extraction from issues list."""
        epic1 = MockJiraIssue("EPIC-1")
        epic1.fields.issuetype.name = "Epic"
        epic1.fields.summary = "First Epic"

        epic2 = MockJiraIssue("EPIC-2")
        epic2.fields.issuetype.name = "Epic"
        epic2.fields.summary = "Second Epic"

        story = MockJiraIssue("TEST-1")

        issues = [epic1, epic2, story]

        result = self.service._extract_epics(issues)

        self.assertEqual(len(result), 2)
        self.assertEqual(result["EPIC-1"], "First Epic")
        self.assertEqual(result["EPIC-2"], "Second Epic")

    def test_extract_comments(self):
        """Test comment extraction from issue."""
        mock_issue = MockJiraIssue()
        mock_issue.fields.reporter.displayName = "Test Reporter"

        result = self.service._extract_comments(mock_issue)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertIn("User A: First comment", result)
        self.assertIn("User B: Second comment", result)

    def test_extract_comments_filters_reporter(self):
        """Test that reporter comments are filtered out."""
        mock_issue = MockJiraIssue()
        mock_issue.fields.reporter.displayName = "User A"  # Same as comment author

        result = self.service._extract_comments(mock_issue)

        self.assertEqual(len(result), 1)
        self.assertIn("User B: Second comment", result)

    def test_extract_sprint_info(self):
        """Test sprint information extraction."""
        mock_issue = MockJiraIssue()
        mock_issue.fields.customfield_10104 = [
            "com.atlassian.greenhopper.service.sprint.Sprint@123[id=1,name=Sprint 1,startDate=2025-06-01,endDate=2025-06-15]",
        ]

        result = self.service._extract_sprint_info(mock_issue)

        self.assertEqual(result["name"], "Sprint 1")
        self.assertEqual(result["count"], 1)

    def test_extract_sprint_info_no_sprint(self):
        """Test sprint extraction when no sprint is assigned."""
        mock_issue = MockJiraIssue()
        mock_issue.fields.customfield_10104 = None

        result = self.service._extract_sprint_info(mock_issue)

        self.assertEqual(result["name"], "Backlog")
        self.assertEqual(result["count"], 0)

    def test_extract_worklog_entries(self):
        """Test worklog entries extraction."""
        mock_issue = MockJiraIssue()

        result = self.service._extract_worklog_entries(mock_issue)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "12345")
        self.assertEqual(result[0].author, "Test User")
        self.assertEqual(result[0].time_spent, "2h")

    def test_extract_worklog_entries_no_worklog(self):
        """Test worklog extraction when no worklog exists."""
        mock_issue = MockJiraIssue()
        mock_issue.fields.worklog = None

        result = self.service._extract_worklog_entries(mock_issue)

        self.assertEqual(len(result), 0)

    def test_extract_linked_issues_no_links(self):
        """Test linked issues extraction when no links exist."""
        mock_issue = MockJiraIssue()

        result = self.service._extract_linked_issues(mock_issue)

        self.assertEqual(len(result), 0)

    def test_parse_datetime_valid(self):
        """Test datetime parsing with valid input."""
        date_str = "2025-06-27T10:00:00.000+0000"

        result = self.service._parse_datetime(date_str)

        self.assertIsNotNone(result)

    def test_parse_datetime_none(self):
        """Test datetime parsing with None input."""
        result = self.service._parse_datetime(None)

        self.assertIsNone(result)

    def test_parse_datetime_invalid(self):
        """Test datetime parsing with invalid input."""
        result = self.service._parse_datetime("invalid-date")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
