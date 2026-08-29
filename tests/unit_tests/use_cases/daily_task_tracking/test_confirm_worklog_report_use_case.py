"""Unit tests for ConfirmWorklogReportUseCase."""
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
    MAX_OPTIONS,
)


def _task(key: str, summary: str) -> DailyTaskCheck:
    return DailyTaskCheck(
        issue_key=key,
        summary=summary,
        status="In Progress",
        assignee="ali",
        check_status=TaskCheckStatus.IN_PROGRESS,
        project_key="PARSCHAT",
    )


def _resolved(hours: float, key: str) -> ParsedWorklogSplit:
    return ParsedWorklogSplit(
        hours=hours,
        description="کار",
        candidate_indices=[0],
        confidence=0.95,
        issue_key=key,
        status=WorklogSplitStatus.RESOLVED,
    )


class TestConfirmWorklogReportUseCase(unittest.TestCase):
    """Test cases for ConfirmWorklogReportUseCase."""

    def setUp(self):
        self.candidates = [
            _task("PARSCHAT-1", "تغییرات درگاه بانک پارسیان"),
            _task("PARSCHAT-2", "رفع مشکلات فرانت‌اند ویجت"),
            _task("PARSCHAT-3", "مستندسازی API"),
        ]
        self.use_case = ConfirmWorklogReportUseCase()

    def test_fully_resolved_report_needs_no_questions(self):
        """The happy path is a single confirm, not an interrogation."""
        report = ParsedWorklogReport(
            raw_text="...",
            total_hours=5,
            splits=[_resolved(3, "PARSCHAT-1"), _resolved(2, "PARSCHAT-2")],
        )

        confirmation = self.use_case.execute(report, self.candidates)

        self.assertTrue(confirmation.is_ready)
        self.assertEqual(confirmation.questions, [])
        self.assertIsNone(confirmation.arithmetic_warning)

    def test_arithmetic_mismatch_is_flagged(self):
        """3 + 2 against a stated 6 is surfaced, not silently accepted."""
        report = ParsedWorklogReport(
            raw_text="...",
            total_hours=6,
            splits=[_resolved(3, "PARSCHAT-1"), _resolved(2, "PARSCHAT-2")],
        )

        confirmation = self.use_case.execute(report, self.candidates)

        self.assertIsNotNone(confirmation.arithmetic_warning)
        self.assertIn("6", confirmation.arithmetic_warning)
        self.assertFalse(confirmation.is_ready)

    def test_rounding_is_within_tolerance(self):
        """Small rounding differences do not provoke a question."""
        report = ParsedWorklogReport(
            raw_text="...",
            total_hours=5,
            splits=[_resolved(2.5, "PARSCHAT-1"), _resolved(2.48, "PARSCHAT-2")],
        )

        confirmation = self.use_case.execute(report, self.candidates)

        self.assertIsNone(confirmation.arithmetic_warning)

    def test_ambiguous_split_asks_with_its_shortlist(self):
        """The question offers exactly the rows the model shortlisted."""
        report = ParsedWorklogReport(
            raw_text="...",
            splits=[
                ParsedWorklogSplit(
                    hours=4,
                    description="کار روی فرانت",
                    candidate_indices=[1, 2],
                    confidence=0.5,
                    status=WorklogSplitStatus.AMBIGUOUS,
                ),
            ],
        )

        confirmation = self.use_case.execute(report, self.candidates)

        self.assertEqual(len(confirmation.questions), 1)
        question = confirmation.questions[0]
        self.assertEqual(question.split_index, 0)
        self.assertIn("کار روی فرانت", question.text)
        self.assertEqual(
            [option.issue_key for option in question.options],
            ["PARSCHAT-2", "PARSCHAT-3"],
        )

    def test_unmatched_split_offers_no_options(self):
        """The user may have just said the task does not exist.

        Offering the first few of their issues looks like a choice but is a
        guess wearing a keyboard, and confirming it writes real hours to the
        wrong issue. Ask instead.
        """
        report = ParsedWorklogReport(
            raw_text="...",
            splits=[
                ParsedWorklogSplit(
                    hours=1,
                    description="یه کاری",
                    candidate_indices=[],
                    status=WorklogSplitStatus.UNMATCHED,
                ),
            ],
        )

        confirmation = self.use_case.execute(report, self.candidates)

        self.assertEqual(confirmation.questions[0].options, [])
        self.assertIn("پیدا نکردم", confirmation.questions[0].text)
        self.assertFalse(confirmation.is_ready)

    def test_options_are_capped_for_telegram(self):
        """A long issue list is trimmed to a readable keyboard."""
        many = [_task(f"PARSCHAT-{i}", f"تسک {i}") for i in range(12)]
        report = ParsedWorklogReport(
            raw_text="...",
            splits=[
                ParsedWorklogSplit(
                    hours=1,
                    description="کار",
                    candidate_indices=list(range(12)),
                    confidence=0.3,
                    status=WorklogSplitStatus.AMBIGUOUS,
                ),
            ],
        )

        confirmation = self.use_case.execute(report, many)

        self.assertEqual(len(confirmation.questions[0].options), MAX_OPTIONS)

    def test_no_stated_total_skips_the_arithmetic_check(self):
        """Users who never state a total are not told their maths is wrong."""
        report = ParsedWorklogReport(
            raw_text="...",
            total_hours=None,
            splits=[_resolved(3, "PARSCHAT-1")],
        )

        confirmation = self.use_case.execute(report, self.candidates)

        self.assertIsNone(confirmation.arithmetic_warning)
        self.assertTrue(confirmation.is_ready)

    def test_long_summary_is_truncated_in_labels(self):
        """Button labels stay short enough to render."""
        long_task = _task("PARSCHAT-9", "ی" * 120)
        report = ParsedWorklogReport(
            raw_text="...",
            splits=[
                ParsedWorklogSplit(
                    hours=1,
                    description="کار",
                    candidate_indices=[0],
                    confidence=0.2,
                    status=WorklogSplitStatus.AMBIGUOUS,
                ),
            ],
        )

        confirmation = self.use_case.execute(report, [long_task])

        label = confirmation.questions[0].options[0].label
        self.assertLess(len(label), 60)
        self.assertTrue(label.endswith("…"))


if __name__ == "__main__":
    unittest.main()
