"""Several plausible issues is a question, not a refusal and not a guess.

A real report — "for explaining the tasks to parschat's team, 4 hours" —
scored 0.496 against its best candidate and led the runner-up by 0.055. The
margin gate refused it outright, so work that had really been done went
unrecorded and the user was told to type an issue key by hand. But the
opposite failure is worse: writing the hours to whichever row happened to
lead a tie puts real time on the wrong task, and worklogs are painful to
unwind. The only correct move is to ask.
"""
import unittest
from unittest.mock import AsyncMock, Mock

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
from jira_telegram_bot.use_cases.daily_task_tracking.parse_worklog_report_use_case import (
    ParseWorklogReportUseCase,
)


def _task(key, summary, project=None):
    return DailyTaskCheck(
        issue_key=key, summary=summary, status="To Do", assignee="a_kazemi",
        check_status=TaskCheckStatus.IN_PROGRESS,
        project_key=project or key.split("-")[0],
    )


class TestATieIsNotSilentlyResolved(unittest.IsolatedAsyncioTestCase):
    """A strong score is not an answer while something else scores as well."""

    def setUp(self):
        self.candidates = [
            _task("AVA-83", "اصلاح پرامپت‌های بانک پارسیان"),
            _task("AVA-84", "رفع بلاکر اتصال همزمان به سرور"),
        ]
        self.ranker = AsyncMock()
        self.parser = ParseWorklogReportUseCase(
            ai_service=Mock(), prompt_catalog=Mock(),
            rank_candidates_use_case=self.ranker,
        )

    def _report(self):
        return ParsedWorklogReport(
            raw_text="...",
            splits=[
                ParsedWorklogSplit(
                    hours=4, description="توضیح تسک‌ها به تیم",
                    candidate_indices=[], confidence=0.2,
                    status=WorklogSplitStatus.UNMATCHED,
                ),
            ],
        )

    async def test_a_close_second_leaves_the_split_for_the_user(self):
        """0.50 leading 0.46 is a tie, however high 0.50 looks."""
        self.ranker.execute.return_value = [
            (self.candidates[0], 0.50), (self.candidates[1], 0.46),
        ]
        report = self._report()

        await self.parser._rerank_splits(report, self.candidates)

        self.assertIs(report.splits[0].status, WorklogSplitStatus.AMBIGUOUS)
        self.assertIsNone(report.splits[0].issue_key)

    async def test_both_candidates_are_offered(self):
        self.ranker.execute.return_value = [
            (self.candidates[0], 0.50), (self.candidates[1], 0.46),
        ]
        report = self._report()

        await self.parser._rerank_splits(report, self.candidates)

        self.assertEqual(report.splits[0].candidate_indices, [0, 1])

    async def test_a_clear_leader_still_settles_without_asking(self):
        """Asking about work the ranking already settled is noise."""
        self.ranker.execute.return_value = [
            (self.candidates[0], 0.72), (self.candidates[1], 0.31),
        ]
        report = self._report()

        await self.parser._rerank_splits(report, self.candidates)

        self.assertIs(report.splits[0].status, WorklogSplitStatus.RESOLVED)
        self.assertEqual(report.splits[0].issue_key, "AVA-83")

    async def test_a_lone_candidate_still_settles(self):
        self.ranker.execute.return_value = [(self.candidates[0], 0.47)]
        report = self._report()

        await self.parser._rerank_splits(report, self.candidates)

        self.assertIs(report.splits[0].status, WorklogSplitStatus.RESOLVED)


class TestTheQuestionExplainsItself(unittest.TestCase):
    """A bare "which task?" reads as the bot not having looked."""

    def setUp(self):
        self.use_case = ConfirmWorklogReportUseCase()
        self.candidates = [
            _task("AVA-83", "اصلاح پرامپت‌های بانک پارسیان"),
            _task("AVA-84", "رفع بلاکر اتصال همزمان به سرور"),
        ]

    def _ask(self, indices, candidates=None):
        report = ParsedWorklogReport(
            raw_text="...",
            splits=[
                ParsedWorklogSplit(
                    hours=4, description="توضیح تسک‌ها به تیم",
                    candidate_indices=indices, confidence=0.2,
                    status=WorklogSplitStatus.AMBIGUOUS,
                ),
            ],
        )
        return self.use_case.execute(
            report, candidates or self.candidates,
        ).questions[0]

    def test_the_users_own_words_are_quoted_back(self):
        self.assertIn("توضیح تسک‌ها به تیم", self._ask([0, 1]).text)

    def test_the_hours_are_stated(self):
        self.assertIn("4", self._ask([0, 1]).text)

    def test_the_number_of_matches_is_stated(self):
        """Saying how many were found shows the work was done."""
        self.assertIn("۲ تسک", self._ask([0, 1]).text)

    def test_the_project_is_named(self):
        self.assertIn("AVA", self._ask([0, 1]).text)

    def test_several_projects_are_all_named(self):
        candidates = [
            _task("AVA-83", "اصلاح پرامپت‌ها"),
            _task("PARS-32", "کارهای عمومی"),
        ]

        text = self._ask([0, 1], candidates).text

        self.assertIn("AVA", text)
        self.assertIn("PARS", text)

    def test_a_single_option_is_not_described_as_a_tie(self):
        text = self._ask([0]).text

        self.assertIn("نزدیک‌ترین تسک", text)
        self.assertNotIn("تصمیم بگیرم", text)

    def test_the_summary_leads_the_button_label(self):
        """People recognise their work by its name, not by its key."""
        label = self._ask([0, 1]).options[0].label

        self.assertTrue(label.startswith("اصلاح پرامپت‌های بانک پارسیان"))
        self.assertIn("AVA-83", label)


if __name__ == "__main__":
    unittest.main()
