"""What the daily reminder actually puts in front of a person.

Three things were wrong in a rendered dry run: a corrupted byte where the
link emoji belongs, "اسپرینت: N/A" on the line meant to be most useful, and
finished work being asked about as though it were late.
"""
import unittest

from jira_telegram_bot.entities.constants import persian_messages
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


def _task(key="PARSCHAT-1", status="In Progress", sprint=None):
    return DailyTaskCheck(
        issue_key=key,
        summary="عنوان",
        status=status,
        assignee="a_kazemi",
        check_status=TaskCheckStatus.IN_PROGRESS,
        project_key="PARSCHAT",
        sprint_name=sprint,
    )


class TestReminderMessageQuality(unittest.TestCase):
    """The templates and the filters that decide what is asked."""

    def test_no_replacement_character_in_any_message(self):
        """A corrupted byte rendered as "�" on every undated task."""
        source = persian_messages.__file__
        with open(source, encoding="utf-8") as handle:
            self.assertNotIn("�", handle.read())

    def test_the_link_line_carries_its_emoji(self):
        self.assertIn("🔗", persian_messages.TASK_HEADER)
        self.assertIn("🔗", persian_messages.TASK_HEADER_WITH_DATES)

    def test_sprint_is_not_baked_into_the_headers(self):
        """Most issues here carry no sprint; a placeholder is noise."""
        self.assertNotIn("sprint_name", persian_messages.TASK_HEADER)
        self.assertNotIn("sprint_name", persian_messages.TASK_HEADER_WITH_DATES)

    def test_the_sprint_line_exists_for_issues_that_have_one(self):
        rendered = persian_messages.TASK_SPRINT.format(sprint_name="S-1405-06-A")

        self.assertIn("S-1405-06-A", rendered)

    def test_finished_work_is_not_asked_about(self):
        """`resolution = Unresolved` still lets Done-status issues through."""
        for status in ("Done", "Closed", "Resolved", "Cancelled"):
            with self.subTest(status=status):
                self.assertTrue(
                    SendDailyTaskRemindersUseCase._is_finished(_task(status=status)),
                )

    def test_live_work_is_still_asked_about(self):
        for status in ("In Progress", "Review", "To Do", "Backlog", "Pause"):
            with self.subTest(status=status):
                self.assertFalse(
                    SendDailyTaskRemindersUseCase._is_finished(_task(status=status)),
                )

    def test_a_status_is_matched_regardless_of_case_and_spacing(self):
        self.assertTrue(
            SendDailyTaskRemindersUseCase._is_finished(_task(status="  DONE ")),
        )

    def test_loose_backlog_is_still_recognised(self):
        self.assertTrue(
            SendDailyTaskRemindersUseCase._is_loose_backlog(
                _task(status="Backlog", sprint=None),
            ),
        )
        self.assertFalse(
            SendDailyTaskRemindersUseCase._is_loose_backlog(
                _task(status="Backlog", sprint="S-1405-06-A"),
            ),
        )

    def test_the_queue_is_short_enough_to_finish(self):
        """Twelve one-at-a-time questions is a form, not a check-in."""
        self.assertLessEqual(MAX_TASKS_PER_REMINDER, 8)

    def test_leaving_the_queue_is_offered(self):
        self.assertTrue(persian_messages.FINISH_LATER.strip())
        self.assertTrue(persian_messages.CHECK_PAUSED.strip())

    def test_every_button_callback_is_routed(self):
        """A button whose callback is unrouted renders but does nothing.

        The registration pattern is the only thing connecting an inline
        button to its handler, so a new button added to a keyboard without
        a matching pattern entry fails silently in front of the user.
        """
        import re
        from pathlib import Path

        source = Path(persian_messages.__file__).parents[3]
        main = (source / "jira_telegram_bot" / "__main__.py").read_text(
            encoding="utf-8",
        )
        pattern = re.search(
            r'pattern=r"\^\((?P<alts>[^"]+)\)"', main,
        ).group("alts").split("|")

        handler = (
            source / "jira_telegram_bot" / "frameworks" / "telegram"
            / "daily_task_tracking_handler.py"
        ).read_text(encoding="utf-8")
        buttons = set(re.findall(r'callback_data="([a-z_]+)"', handler))

        for callback in buttons:
            with self.subTest(callback=callback):
                self.assertTrue(
                    any(callback.startswith(alt) for alt in pattern),
                    f"{callback} is not matched by the registration pattern",
                )


if __name__ == "__main__":
    unittest.main()
