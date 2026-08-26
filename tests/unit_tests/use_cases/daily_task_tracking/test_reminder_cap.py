"""The daily reminder must ask a number of questions people will answer."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock

from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.send_daily_task_reminders_use_case import (
    MAX_TASKS_PER_REMINDER,
    SendDailyTaskRemindersUseCase,
)


def _task(key, check_status, target_end=None):
    return DailyTaskCheck(
        issue_key=key,
        summary="کار",
        status="To Do",
        assignee="ali",
        check_status=check_status,
        project_key="PARSCHAT",
        target_end=target_end,
    )


class TestReminderCap(unittest.TestCase):
    """Tests for which tasks a reminder asks about."""

    def setUp(self):
        self.use_case = SendDailyTaskRemindersUseCase.__new__(
            SendDailyTaskRemindersUseCase,
        )

    def test_queue_is_capped(self):
        """187 prompts is an abandoned queue, not a daily check-in."""
        tasks = [
            _task(f"P-{i}", TaskCheckStatus.SHOULD_BE_STARTED)
            for i in range(200)
        ]

        self.assertEqual(
            len(self.use_case._most_pressing(tasks)), MAX_TASKS_PER_REMINDER,
        )

    def test_short_lists_are_untouched(self):
        """Most people are under the cap and must see everything."""
        tasks = [_task(f"P-{i}", TaskCheckStatus.IN_PROGRESS) for i in range(4)]

        self.assertEqual(len(self.use_case._most_pressing(tasks)), 4)

    def test_actionable_tasks_win_over_unstarted_ones(self):
        """An answer changes something for these; for the rest it does not."""
        tasks = [
            _task(f"NEW-{i}", TaskCheckStatus.SHOULD_BE_STARTED)
            for i in range(50)
        ]
        tasks += [
            _task("LOG-1", TaskCheckStatus.NEEDS_WORKLOG),
            _task("WIP-1", TaskCheckStatus.IN_PROGRESS),
            _task("REG-1", TaskCheckStatus.STATUS_REGRESSED),
        ]

        picked = {task.issue_key for task in self.use_case._most_pressing(tasks)}

        self.assertIn("REG-1", picked)
        self.assertIn("LOG-1", picked)
        self.assertIn("WIP-1", picked)

    def test_regression_is_asked_about_first(self):
        """A task that slipped backwards is the most urgent thing to raise."""
        tasks = [
            _task("WIP-1", TaskCheckStatus.IN_PROGRESS),
            _task("REG-1", TaskCheckStatus.STATUS_REGRESSED),
        ]

        self.assertEqual(
            self.use_case._most_pressing(tasks)[0].issue_key, "REG-1",
        )

    def test_earlier_deadline_comes_first_within_a_status(self):
        """Among equals, the one due soonest is asked about first."""
        soon = datetime.now() + timedelta(days=1)
        later = datetime.now() + timedelta(days=30)
        tasks = [
            _task("LATE", TaskCheckStatus.IN_PROGRESS, target_end=later),
            _task("SOON", TaskCheckStatus.IN_PROGRESS, target_end=soon),
        ]

        self.assertEqual(
            self.use_case._most_pressing(tasks)[0].issue_key, "SOON",
        )

    def test_undated_tasks_do_not_crash_the_sort(self):
        """target_end is often empty; that must not raise."""
        tasks = [
            _task("A", TaskCheckStatus.IN_PROGRESS),
            _task("B", TaskCheckStatus.IN_PROGRESS, target_end=datetime.now()),
        ]

        self.assertEqual(len(self.use_case._most_pressing(tasks)), 2)


if __name__ == "__main__":
    unittest.main()
