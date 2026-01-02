"""Unit tests for GetUserDailyTasksUseCase."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.get_user_daily_tasks_use_case import (
    GetUserDailyTasksUseCase,
)


class TestGetUserDailyTasksUseCase(unittest.TestCase):
    """Test cases for GetUserDailyTasksUseCase."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_task_manager = Mock()
        self.use_case = GetUserDailyTasksUseCase(
            task_manager_repository=self.mock_task_manager,
        )

    async def test_execute_returns_tasks_needing_attention(self):
        """Test that execute returns only tasks needing attention."""
        mock_issue = Mock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Test task"
        mock_issue.fields.status.name = "To Do"
        mock_issue.fields.assignee.name = "testuser"
        mock_issue.fields.project.key = "TEST"
        mock_issue.fields.issuetype.name = "Task"
        
        self.mock_task_manager.search_for_issues.return_value = [mock_issue]
        self.mock_task_manager.jira.worklogs.return_value = []
        
        with patch.object(
            self.use_case,
            "_get_custom_date_field",
            return_value=datetime.now() - timedelta(days=1),
        ):
            with patch.object(
                self.use_case,
                "_check_dependencies_completed",
                return_value=True,
            ):
                tasks = await self.use_case.execute("testuser")
                
                self.assertEqual(len(tasks), 1)
                self.assertEqual(tasks[0].issue_key, "TEST-123")
                self.assertEqual(
                    tasks[0].check_status,
                    TaskCheckStatus.SHOULD_BE_STARTED,
                )

    async def test_execute_filters_ok_tasks(self):
        """Test that execute filters out tasks with OK status."""
        mock_issue = Mock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Test task"
        mock_issue.fields.status.name = "To Do"
        mock_issue.fields.assignee.name = "testuser"
        mock_issue.fields.project.key = "TEST"
        
        self.mock_task_manager.search_for_issues.return_value = [mock_issue]
        
        with patch.object(
            self.use_case,
            "_determine_check_status",
            return_value=TaskCheckStatus.OK,
        ):
            tasks = await self.use_case.execute("testuser")
            
            self.assertEqual(len(tasks), 0)

    def test_determine_check_status_should_be_started(self):
        """Test check status determination for tasks that should be started."""
        status = self.use_case._determine_check_status(
            status="To Do",
            target_start=datetime.now() - timedelta(days=1),
            dependencies_completed=True,
            worklog_hours=0,
        )
        
        self.assertEqual(status, TaskCheckStatus.SHOULD_BE_STARTED)

    def test_determine_check_status_in_progress(self):
        """Test check status determination for in-progress tasks."""
        status = self.use_case._determine_check_status(
            status="In Progress",
            target_start=datetime.now() - timedelta(days=1),
            dependencies_completed=True,
            worklog_hours=0,
        )
        
        self.assertEqual(status, TaskCheckStatus.IN_PROGRESS)

    def test_determine_check_status_needs_worklog(self):
        """Test check status determination for done tasks without worklog."""
        status = self.use_case._determine_check_status(
            status="Done",
            target_start=None,
            dependencies_completed=True,
            worklog_hours=0,
        )
        
        self.assertEqual(status, TaskCheckStatus.NEEDS_WORKLOG)


if __name__ == "__main__":
    unittest.main()
