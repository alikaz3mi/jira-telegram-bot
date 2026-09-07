"""Asking for details must never be a wall the user cannot get past.

Reported: "میخوام تایممو ثبت کنم. تسکام توی برد خودمو بهم میگی؟" and then
"بهم تسکامو بگو بهت میگم" both answered "بگویید چند ساعت و روی چه کاری" —
the same sentence twice. Somebody who cannot see their task list cannot name
a task from it, so the conversation had nowhere to go.

The candidate list is already fetched at that point in the handler. Showing
it costs nothing and turns the refusal into an answer.
"""
import unittest
from unittest.mock import Mock

from jira_telegram_bot.entities.constants import persian_messages
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.frameworks.telegram.daily_task_tracking_handler import (
    MAX_TASKS_OFFERED,
    DailyTaskTrackingHandler,
)


def _task(key, summary):
    return DailyTaskCheck(
        issue_key=key, summary=summary, status="To Do", assignee="a_kazemi",
        check_status=TaskCheckStatus.IN_PROGRESS,
        project_key=key.split("-")[0],
    )


class TestTheTaskListIsOffered(unittest.TestCase):
    """What the bot says when it needs details it was not given."""

    def setUp(self):
        self.handler = DailyTaskTrackingHandler.__new__(DailyTaskTrackingHandler)
        self.handler.base_url = "https://jira.example.com"
        self.tasks = [
            _task("AK-13", "شرح وظایف تیم پارسچت"),
            _task("AK-16", "گزارش خودکار کلی"),
        ]

    def test_the_open_tasks_are_named(self):
        offer = self.handler._offer_the_task_list(self.tasks)

        self.assertIn("شرح وظایف تیم پارسچت", offer)
        self.assertIn("گزارش خودکار کلی", offer)

    def test_the_original_prompt_is_kept(self):
        """They still need to know hours are what is missing."""
        offer = self.handler._offer_the_task_list(self.tasks)

        self.assertIn(persian_messages.WORKLOG_NEEDS_DETAIL, offer)

    def test_each_task_is_linked_by_its_title(self):
        offer = self.handler._offer_the_task_list(self.tasks)

        self.assertIn(
            '<a href="https://jira.example.com/browse/AK-13">'
            "شرح وظایف تیم پارسچت</a>",
            offer,
        )

    def test_the_key_is_shown_so_it_can_be_quoted_back(self):
        offer = self.handler._offer_the_task_list(self.tasks)

        self.assertIn("AK-13", offer)

    def test_a_long_list_is_capped_and_says_so(self):
        """A reminder inside a prompt is not a report."""
        many = [_task(f"PARSCHAT-{index}", f"کار {index}") for index in range(30)]

        offer = self.handler._offer_the_task_list(many)

        self.assertEqual(offer.count("• "), MAX_TASKS_OFFERED)
        self.assertIn("تسک دیگر", offer)

    def test_a_short_list_claims_no_remainder(self):
        offer = self.handler._offer_the_task_list(self.tasks)

        self.assertNotIn("تسک دیگر", offer)

    def test_a_summary_with_html_characters_is_escaped(self):
        """One unescaped & costs the whole message."""
        offer = self.handler._offer_the_task_list([_task("AK-1", "A & B <b>")])

        self.assertIn("&amp;", offer)
        self.assertNotIn("<b>", offer)

    def test_an_empty_summary_falls_back_to_the_key(self):
        offer = self.handler._offer_the_task_list([_task("AK-1", "")])

        self.assertIn("AK-1", offer)

    def test_without_a_base_url_the_titles_survive_unlinked(self):
        self.handler.base_url = ""

        offer = self.handler._offer_the_task_list(self.tasks)

        self.assertIn("شرح وظایف تیم پارسچت", offer)
        self.assertNotIn("<a href", offer)


if __name__ == "__main__":
    unittest.main()
