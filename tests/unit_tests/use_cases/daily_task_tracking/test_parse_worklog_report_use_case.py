"""Unit tests for ParseWorklogReportUseCase."""
import unittest
from unittest.mock import AsyncMock

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


def _task(key: str, summary: str, project: str = "PARSCHAT") -> DailyTaskCheck:
    return DailyTaskCheck(
        issue_key=key,
        summary=summary,
        status="In Progress",
        assignee="ali",
        check_status=TaskCheckStatus.IN_PROGRESS,
        project_key=project,
    )


class TestParseWorklogReportUseCase(unittest.IsolatedAsyncioTestCase):
    """Test cases for ParseWorklogReportUseCase."""

    def setUp(self):
        self.candidates = [
            _task("PARSCHAT-1", "تغییرات درگاه بانک پارسیان"),
            _task("PARSCHAT-2", "رفع مشکلات فرانت‌اند ویجت"),
            _task("PARSCHAT-3", "مستندسازی API"),
        ]
        self.ai_service = AsyncMock()
        self.prompt_catalog = AsyncMock()
        self.use_case = ParseWorklogReportUseCase(
            ai_service=self.ai_service,
            prompt_catalog=self.prompt_catalog,
        )

    async def test_splits_report_into_confident_entries(self):
        """A clear breakdown resolves to issue keys with no questions left."""
        self.ai_service.run.return_value = {
            "total_hours": 5,
            "project_hint": "پارس‌چت",
            "splits": [
                {
                    "hours": 3,
                    "description": "تغییرات سمت بانک پارسیان",
                    "candidate_indices": [0],
                    "confidence": 0.95,
                },
                {
                    "hours": 2,
                    "description": "رفع مشکلات فرانت",
                    "candidate_indices": [1],
                    "confidence": 0.9,
                },
            ],
        }

        report = await self.use_case.execute("...", self.candidates)

        self.assertEqual(report.total_hours, 5)
        self.assertEqual(report.allocated_hours, 5)
        self.assertFalse(report.needs_confirmation)
        self.assertEqual(
            [split.issue_key for split in report.splits],
            ["PARSCHAT-1", "PARSCHAT-2"],
        )

    async def test_low_confidence_is_ambiguous_not_written(self):
        """A shaky single match is held back for confirmation."""
        self.ai_service.run.return_value = {
            "total_hours": 2,
            "splits": [
                {
                    "hours": 2,
                    "description": "یه کاری کردم",
                    "candidate_indices": [2],
                    "confidence": 0.4,
                },
            ],
        }

        report = await self.use_case.execute("...", self.candidates)

        split = report.splits[0]
        self.assertIs(split.status, WorklogSplitStatus.AMBIGUOUS)
        self.assertIsNone(split.issue_key)
        self.assertTrue(report.needs_confirmation)

    async def test_multiple_candidates_are_ambiguous(self):
        """Two plausible rows are never silently narrowed to one."""
        self.ai_service.run.return_value = {
            "splits": [
                {
                    "hours": 4,
                    "description": "کار روی فرانت",
                    "candidate_indices": [1, 2],
                    "confidence": 0.9,
                },
            ],
        }

        report = await self.use_case.execute("...", self.candidates)

        self.assertIs(report.splits[0].status, WorklogSplitStatus.AMBIGUOUS)
        self.assertIsNone(report.splits[0].issue_key)

    async def test_hallucinated_index_is_discarded(self):
        """An out-of-range index cannot become an issue key."""
        self.ai_service.run.return_value = {
            "splits": [
                {
                    "hours": 1,
                    "description": "کار نامشخص",
                    "candidate_indices": [99],
                    "confidence": 1.0,
                },
            ],
        }

        report = await self.use_case.execute("...", self.candidates)

        split = report.splits[0]
        self.assertIs(split.status, WorklogSplitStatus.UNMATCHED)
        self.assertIsNone(split.issue_key)
        self.assertEqual(split.candidate_indices, [])

    async def test_persian_digits_and_string_numbers(self):
        """Numbers may arrive as Persian-digit strings."""
        self.ai_service.run.return_value = {
            "total_hours": "۵",
            "splits": [
                {
                    "hours": "۲.۵",
                    "description": "بانک",
                    "candidate_indices": ["۰"],
                    "confidence": "0.9",
                },
            ],
        }

        report = await self.use_case.execute("...", self.candidates)

        self.assertEqual(report.total_hours, 5.0)
        self.assertEqual(report.splits[0].hours, 2.5)
        self.assertEqual(report.splits[0].issue_key, "PARSCHAT-1")

    async def test_zero_hour_splits_are_dropped(self):
        """An entry with no hours is not a worklog."""
        self.ai_service.run.return_value = {
            "splits": [
                {"hours": 0, "description": "هیچی", "candidate_indices": [0],
                 "confidence": 1.0},
                {"hours": 3, "description": "بانک", "candidate_indices": [0],
                 "confidence": 0.95},
            ],
        }

        report = await self.use_case.execute("...", self.candidates)

        self.assertEqual(len(report.splits), 1)
        self.assertEqual(report.splits[0].hours, 3)

    async def test_no_candidates_skips_the_model(self):
        """With nothing to match against, no LLM call is made."""
        report = await self.use_case.execute("۵ ساعت کار کردم", [])

        self.assertEqual(report.splits, [])
        self.ai_service.run.assert_not_called()

    async def test_malformed_split_does_not_raise(self):
        """Junk in the splits array is skipped, not fatal."""
        self.ai_service.run.return_value = {
            "splits": ["nonsense", {"hours": 2, "description": "بانک",
                                    "candidate_indices": [0], "confidence": 0.9}],
        }

        report = await self.use_case.execute("...", self.candidates)

        self.assertEqual(len(report.splits), 1)
        self.assertEqual(report.splits[0].issue_key, "PARSCHAT-1")

    async def test_candidates_are_numbered_for_the_model(self):
        """The model is shown indices and keys, so it can point at a row."""
        self.ai_service.run.return_value = {"splits": []}

        await self.use_case.execute("...", self.candidates)

        rendered = self.ai_service.run.call_args[0][1]["candidates"]
        self.assertIn("[0] PARSCHAT-1:", rendered)
        self.assertIn("[2] PARSCHAT-3:", rendered)


if __name__ == "__main__":
    unittest.main()
