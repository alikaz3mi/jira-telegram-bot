"""Sample data for Jira report testing."""
from __future__ import annotations

from datetime import datetime
from typing import List

from jira_telegram_bot.entities.jira_report import JiraIssueDetail
from jira_telegram_bot.entities.jira_report import LinkedIssue
from jira_telegram_bot.entities.jira_report import ProjectReport
from jira_telegram_bot.entities.jira_report import WorklogEntry


class JiraReportTestFactory:
    """Factory for creating test Jira report data."""

    @staticmethod
    def create_worklog_entry(
        worklog_id: str = "12345",
        author: str = "Test User",
        time_spent: str = "2h 30m",
        comment: str = "Test worklog comment",
    ) -> WorklogEntry:
        """Create a test worklog entry."""
        return WorklogEntry(
            id=worklog_id,
            author=author,
            time_spent=time_spent,
            time_spent_seconds=9000,
            created=datetime(2025, 6, 27, 10, 0, 0),
            updated=datetime(2025, 6, 27, 10, 30, 0),
            started=datetime(2025, 6, 27, 9, 0, 0),
            comment=comment,
        )

    @staticmethod
    def create_linked_issue(
        key: str = "TEST-2",
        summary: str = "Linked test issue",
        relationship: str = "blocks",
    ) -> LinkedIssue:
        """Create a test linked issue."""
        return LinkedIssue(
            key=key,
            summary=summary,
            status="In Progress",
            issue_type="Bug",
            relationship=relationship,
        )

    @staticmethod
    def create_jira_issue_detail(
        key: str = "TEST-1",
        summary: str = "Test issue summary",
        with_worklogs: bool = True,
        with_linked_issues: bool = True,
    ) -> JiraIssueDetail:
        """Create a test Jira issue detail."""
        worklog_entries = []
        if with_worklogs:
            worklog_entries = [
                JiraReportTestFactory.create_worklog_entry("12345", "User A"),
                JiraReportTestFactory.create_worklog_entry("12346", "User B", "1h"),
            ]

        linked_issues = []
        if with_linked_issues:
            linked_issues = [
                JiraReportTestFactory.create_linked_issue("TEST-2", "Blocked issue"),
                JiraReportTestFactory.create_linked_issue("TEST-3", "Related issue", "relates to"),
            ]

        return JiraIssueDetail(
            key=key,
            summary=summary,
            description="Test issue description",
            epic_name="Test Epic",
            comments="User A: Test comment\nUser B: Another comment",
            task_type="Story",
            assignee="Test Assignee",
            reporter="Test Reporter",
            priority="High",
            status="In Progress",
            created_at=datetime(2025, 6, 20, 10, 0, 0),
            updated_at=datetime(2025, 6, 27, 10, 0, 0),
            resolved_at=None,
            target_start=datetime(2025, 6, 25, 9, 0, 0),
            target_end=datetime(2025, 6, 30, 17, 0, 0),
            story_points=5.0,
            components=["Frontend", "Backend"],
            labels=["urgent", "feature"],
            last_sprint="Sprint 24",
            sprint_repeats=2,
            release=["v2.1.0", "v2.1.1"],
            original_estimate="3d",
            remaining_estimate="1d",
            worklog_entries=worklog_entries,
            linked_issues=linked_issues,
        )

    @staticmethod
    def create_project_report(
        project_key: str = "TEST",
        issue_count: int = 3,
    ) -> ProjectReport:
        """Create a test project report."""
        issues = [
            JiraReportTestFactory.create_jira_issue_detail(f"{project_key}-{i}")
            for i in range(1, issue_count + 1)
        ]

        return ProjectReport(
            project_key=project_key,
            generated_at=datetime(2025, 6, 27, 12, 0, 0),
            total_issues=issue_count,
            issues=issues,
        )

    @staticmethod
    def create_multiple_issues(count: int = 5) -> List[JiraIssueDetail]:
        """Create multiple test issues."""
        return [
            JiraReportTestFactory.create_jira_issue_detail(
                key=f"TEST-{i}",
                summary=f"Test issue {i}",
                with_worklogs=i % 2 == 0,
                with_linked_issues=i % 3 == 0,
            )
            for i in range(1, count + 1)
        ]
