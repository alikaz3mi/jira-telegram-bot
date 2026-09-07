"""An unmatched worklog must ask, never guess an issue."""
import unittest

from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.entities.daily_task_tracking.worklog_intent import (
    ParsedWorklogReport,
    ParsedWorklogSplit,
    WorklogSplitStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.confirm_worklog_report_use_case import (
    ConfirmWorklogReportUseCase,
)


def _task(key):
    return DailyTaskCheck(
        issue_key=key, summary="کار", status="In Progress", assignee="ali",
        check_status=TaskCheckStatus.IN_PROGRESS, project_key="PARSCHAT",
    )


class TestUnmatchedSplit(unittest.TestCase):
    """The user said the task does not exist; do not offer a random one."""

    def setUp(self):
        self.use_case = ConfirmWorklogReportUseCase()
        self.candidates = [_task(f"PARSCHAT-{n}") for n in (1, 2, 3, 4, 5)]

    def _confirm(self, split):
        return self.use_case.execute(
            ParsedWorklogReport(raw_text="...", splits=[split]), self.candidates,
        )

    def test_unmatched_split_offers_no_arbitrary_issues(self):
        """Offering the first few tasks looks like a choice but is a guess."""
        confirmation = self._confirm(ParsedWorklogSplit(
            hours=1, description="ریموت", candidate_indices=[],
            confidence=0.9, status=WorklogSplitStatus.UNMATCHED,
        ))

        self.assertEqual(len(confirmation.questions), 1)
        self.assertEqual(confirmation.questions[0].options, [])

    def test_unmatched_question_tells_the_user_what_to_do(self):
        confirmation = self._confirm(ParsedWorklogSplit(
            hours=1, description="ریموت", candidate_indices=[],
            confidence=0.9, status=WorklogSplitStatus.UNMATCHED,
        ))

        self.assertIn("پیدا نکردم", confirmation.questions[0].text)

    def test_a_real_shortlist_is_still_offered(self):
        """Genuine ambiguity keeps its tappable options."""
        confirmation = self._confirm(ParsedWorklogSplit(
            hours=2, description="کار", candidate_indices=[0, 1],
            confidence=0.5, status=WorklogSplitStatus.AMBIGUOUS,
        ))

        options = confirmation.questions[0].options
        self.assertEqual(len(options), 2)
        self.assertEqual(options[0].issue_key, "PARSCHAT-1")

    def test_unmatched_report_is_never_ready(self):
        """Nothing may be written while a split has no issue."""
        confirmation = self._confirm(ParsedWorklogSplit(
            hours=1, description="ریموت", candidate_indices=[],
            confidence=0.9, status=WorklogSplitStatus.UNMATCHED,
        ))

        self.assertFalse(confirmation.is_ready)


if __name__ == "__main__":
    unittest.main()


class TestUnmatchedSplitShowsTheBoard(unittest.TestCase):
    """A description that names work, but matches nothing, still gets help.

    Reported: "میخوام روی تسکهای برنامه ریزیم ... ۴ ساعت تایم ریموت ثبت کنم"
    was answered with "تسکی پیدا نکردم — کلید تسک را بنویسید". There is no
    planning task on that board, so refusing to guess was right; asking for
    an issue key while showing nothing was not. Somebody who cannot recall
    their own keys has nowhere to go from there.
    """

    def setUp(self):
        self.use_case = ConfirmWorklogReportUseCase()
        self.candidates = [
            _task("AK-13"), _task("AK-23"), _task("AK-16"),
        ]

    def _ask(self, description):
        report = ParsedWorklogReport(
            raw_text="...",
            splits=[
                ParsedWorklogSplit(
                    hours=4, description=description, candidate_indices=[],
                    confidence=0.2, status=WorklogSplitStatus.UNMATCHED,
                ),
            ],
        )
        return self.use_case.execute(report, self.candidates).questions[0]

    def test_a_described_subject_gets_the_open_tasks_as_options(self):
        question = self._ask("تسکهای برنامه ریزی")

        self.assertTrue(question.options)
        self.assertIn("AK-13", [option.issue_key for option in question.options])

    def test_the_number_of_open_tasks_is_stated(self):
        self.assertIn("۳ تسک باز", self._ask("تسکهای برنامه ریزی").text)

    def test_typing_a_key_is_still_offered(self):
        """The list is a shortcut, not the only way out."""
        self.assertIn("PARSCHAT-123", self._ask("تسکهای برنامه ریزی").text)

    def test_a_bare_work_type_still_offers_nothing(self):
        """«ریموت» names no subject, so buttons there are a guess."""
        self.assertEqual(self._ask("ریموت").options, [])

    def test_a_bare_day_still_offers_nothing(self):
        self.assertEqual(self._ask("دیروز").options, [])

    def test_an_empty_description_offers_nothing(self):
        self.assertEqual(self._ask("").options, [])

    def test_the_options_are_capped(self):
        self.candidates = [_task(f"AK-{index}") for index in range(20)]

        question = self._ask("تسکهای برنامه ریزی")

        self.assertLessEqual(len(question.options), 4)
