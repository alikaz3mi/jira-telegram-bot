"""Undated sprint work must not be filtered out of the daily task list."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock

from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.get_user_daily_tasks_use_case import (
    GetUserDailyTasksUseCase,
)


class TestUndatedTasksAreVisible(unittest.TestCase):
    """Regression tests for tasks with no Target start date.

    A To Do issue in an active sprint with no Target start used to fall
    through every branch to OK and vanish from the list, so the assistant
    reported "you have no tasks" for real sprint work.
    """

    def setUp(self):
        self.use_case = GetUserDailyTasksUseCase(task_manager_repository=Mock())

    def _status(self, status, target_start, deps_done=True, hours=0.0):
        return self.use_case._determine_check_status(
            status, target_start, deps_done, hours,
        )

    def test_undated_todo_needs_attention(self):
        """The case that made FOLLOWUP-128 invisible."""
        self.assertIs(
            self._status("To Do", None), TaskCheckStatus.SHOULD_BE_STARTED,
        )

    def test_task_dated_in_the_future_is_left_alone(self):
        """Work genuinely scheduled for later is not nagged about."""
        self.assertIs(
            self._status("To Do", datetime.now() + timedelta(days=5)),
            TaskCheckStatus.OK,
        )

    def test_task_due_today_needs_attention(self):
        self.assertIs(
            self._status("To Do", datetime.now()),
            TaskCheckStatus.SHOULD_BE_STARTED,
        )

    def test_blocked_task_is_not_pushed(self):
        """An undated task whose blockers are open is not ready to start."""
        self.assertIs(
            self._status("To Do", None, deps_done=False), TaskCheckStatus.OK,
        )

    def test_in_progress_is_unaffected(self):
        self.assertIs(
            self._status("In Progress", None), TaskCheckStatus.IN_PROGRESS,
        )

    def test_done_without_worklog_still_asks_for_hours(self):
        self.assertIs(
            self._status("Done", None), TaskCheckStatus.NEEDS_WORKLOG,
        )

    def test_done_with_worklog_is_settled(self):
        self.assertIs(self._status("Done", None, hours=3.0), TaskCheckStatus.OK)


if __name__ == "__main__":
    unittest.main()
