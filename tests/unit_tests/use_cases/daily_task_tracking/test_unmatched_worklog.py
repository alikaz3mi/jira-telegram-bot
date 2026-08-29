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
