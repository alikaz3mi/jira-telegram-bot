"""Similarity settles a split by what that split describes.

Ranking the whole message does not work: "دیروز ۲ ساعت ریموت روی تنزل
خودکار کار کردم" embeds hours, a date and a way of working alongside the
task. The right issue still led, but by 0.04 instead of 0.15, and the
margin gate then read it as no match. Each split carries only its own
description, which is the text worth comparing.
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
    WorklogSplitStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.parse_worklog_report_use_case import (
    ParseWorklogReportUseCase,
)


def _task(key, summary):
    return DailyTaskCheck(
        issue_key=key,
        summary=summary,
        status="In Progress",
        assignee="a_kazemi",
        check_status=TaskCheckStatus.IN_PROGRESS,
        project_key="PARSCHAT",
    )


class TestSplitReranking(unittest.IsolatedAsyncioTestCase):
    """Ranking runs per split, and only on splits the model left open."""

    def setUp(self):
        self.candidates = [
            _task("PARSCHAT-5813", "بهینه‌سازی کوئری‌های سنگین"),
            _task("PARSCHAT-5830", "مهاجرت داده مشتریان"),
            _task("PARSCHAT-5829", "تنزل خودکار به بسته رایگان"),
        ]
        self.ranker = AsyncMock()
        self.ai = AsyncMock()
        self.ai.run.return_value = {
            "total_hours": 2,
            "project_hint": "",
            "splits": [{
                "hours": 2,
                "description": "تنزل خودکار به بسته رایگان",
                "candidate_indices": [0, 1, 2],
                "confidence": 0.4,
            }],
        }
        catalog = AsyncMock()
        catalog.get_prompt.return_value = "prompt"
        self.use_case = ParseWorklogReportUseCase(
            ai_service=self.ai,
            prompt_catalog=catalog,
            alias_repository=None,
            rank_candidates_use_case=self.ranker,
        )

    async def test_ranking_sees_the_split_not_the_whole_message(self):
        """The surrounding hours and date are what buried the signal."""
        self.ranker.execute.return_value = [(self.candidates[2], 0.52)]

        await self.use_case.execute(
            "دیروز ۲ ساعت ریموت روی تنزل خودکار کار کردم", self.candidates,
        )

        self.assertEqual(
            self.ranker.execute.call_args.args[0],
            "تنزل خودکار به بسته رایگان",
        )

    async def test_a_strong_match_settles_the_split(self):
        self.ranker.execute.return_value = [
            (self.candidates[2], 0.52), (self.candidates[0], 0.31),
        ]

        report = await self.use_case.execute("...", self.candidates)

        self.assertEqual(report.splits[0].issue_key, "PARSCHAT-5829")
        self.assertIs(report.splits[0].status, WorklogSplitStatus.RESOLVED)

    async def test_a_weak_field_stays_a_question(self):
        """A shortlist without a clear winner is asked about, not written."""
        self.ranker.execute.return_value = [
            (self.candidates[0], 0.33), (self.candidates[1], 0.31),
        ]

        report = await self.use_case.execute("...", self.candidates)

        self.assertIs(report.splits[0].status, WorklogSplitStatus.AMBIGUOUS)
        self.assertIsNone(report.splits[0].issue_key)

    async def test_no_match_clears_the_options(self):
        """Offering rows that all scored alike is a guess wearing a keyboard."""
        self.ranker.execute.return_value = []

        report = await self.use_case.execute("...", self.candidates)

        self.assertIs(report.splits[0].status, WorklogSplitStatus.UNMATCHED)
        self.assertEqual(report.splits[0].candidate_indices, [])

    async def test_ranking_failure_leaves_the_model_reading_intact(self):
        """None means no ranking was available, not that nothing matched."""
        self.ranker.execute.return_value = None

        report = await self.use_case.execute("...", self.candidates)

        self.assertEqual(report.splits[0].candidate_indices, [0, 1, 2])

    async def test_a_confident_reading_is_not_second_guessed(self):
        """The model naming one issue at high confidence already settles it."""
        self.ai.run.return_value["splits"][0]["candidate_indices"] = [2]
        self.ai.run.return_value["splits"][0]["confidence"] = 0.95

        report = await self.use_case.execute("...", self.candidates)

        self.ranker.execute.assert_not_called()
        self.assertEqual(report.splits[0].issue_key, "PARSCHAT-5829")

    async def test_indices_point_into_the_full_candidate_list(self):
        """A wrong index here writes the hours to the wrong issue."""
        self.ranker.execute.return_value = [
            (self.candidates[2], 0.33), (self.candidates[1], 0.30),
        ]

        report = await self.use_case.execute("...", self.candidates)

        self.assertEqual(report.splits[0].candidate_indices, [2, 1])

    async def test_a_single_candidate_list_is_not_ranked(self):
        report = await self.use_case.execute("...", [self.candidates[0]])

        self.ranker.execute.assert_not_called()
        self.assertEqual(len(report.splits), 1)


if __name__ == "__main__":
    unittest.main()
