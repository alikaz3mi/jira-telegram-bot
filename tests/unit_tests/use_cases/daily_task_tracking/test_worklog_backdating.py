"""Unit tests for backdated worklogs and work-type tagging."""
import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.use_cases.daily_task_tracking.parse_worklog_report_use_case import (
    ParseWorklogReportUseCase,
)
from jira_telegram_bot.use_cases.daily_task_tracking.record_worklog_use_case import (
    RecordWorklogUseCase,
)

HISTORY = "assistant: PARSCHAT-3353 — a\nPARSCHAT-5004 — b\nPARS-32 — c"


class TestOrdinalResolution(unittest.TestCase):
    """Ordinals must resolve in Python, not be left to the model."""

    def test_every_ordinal_form_resolves(self):
        """"دومی" must be as reliable as "تسک دوم"."""
        cases = {
            "روی تسک اول ۳ ساعت": "PARSCHAT-3353",
            "اولی ۳ ساعت": "PARSCHAT-3353",
            "روی دومی ۲ ساعت": "PARSCHAT-5004",
            "تسک دوم ۲ ساعت": "PARSCHAT-5004",
            "سومی ۱ ساعت": "PARS-32",
            "آخری ۱ ساعت": "PARS-32",
        }
        for text, expected in cases.items():
            self.assertEqual(
                ParseWorklogReportUseCase._ordinal_issue_key(text, HISTORY),
                expected,
                msg=text,
            )

    def test_no_ordinal_resolves_to_nothing(self):
        """A plain report must not be forced onto a task by this path."""
        self.assertIsNone(
            ParseWorklogReportUseCase._ordinal_issue_key("۲ ساعت کار کردم", HISTORY),
        )

    def test_ordinal_past_the_end_is_not_invented(self):
        """Asking for the fifth of three names nothing."""
        self.assertIsNone(
            ParseWorklogReportUseCase._ordinal_issue_key("پنجمی ۱ ساعت", HISTORY),
        )

    def test_no_history_means_no_resolution(self):
        """With nothing listed, an ordinal cannot mean anything."""
        self.assertIsNone(
            ParseWorklogReportUseCase._ordinal_issue_key("اولی ۲ ساعت", ""),
        )


class TestWorkDateGuard(unittest.TestCase):
    """A worklog must never be dated into the future."""

    def test_past_date_is_kept(self):
        two_days_ago = (date.today() - timedelta(days=2)).isoformat()

        self.assertEqual(
            ParseWorklogReportUseCase._to_past_date(two_days_ago), two_days_ago,
        )

    def test_future_date_is_dropped(self):
        ahead = (date.today() + timedelta(days=3)).isoformat()

        self.assertIsNone(ParseWorklogReportUseCase._to_past_date(ahead))

    def test_unparseable_date_is_dropped(self):
        self.assertIsNone(ParseWorklogReportUseCase._to_past_date("دیروز"))

    def test_missing_date_means_today(self):
        self.assertIsNone(ParseWorklogReportUseCase._to_past_date(None))


class TestRecordWorklogStarted(unittest.IsolatedAsyncioTestCase):
    """The chosen day must reach Jira, not just the parser."""

    def setUp(self):
        self.repo = Mock()
        self.repo.jira.add_worklog = Mock()
        self.use_case = RecordWorklogUseCase(
            task_manager_repository=self.repo,
            tracking_repository=AsyncMock(),
        )

    async def test_backdated_worklog_sets_started(self):
        """Without this Jira dates the work to now and misfiles it."""
        await self.use_case.execute(
            issue_key="PARSCHAT-1",
            jira_username="ali",
            telegram_username="ali_tg",
            hours=4,
            comment="ریموت — کار",
            started_date="2026-08-24",
        )

        started = self.repo.jira.add_worklog.call_args.kwargs["started"]
        self.assertEqual(started.date().isoformat(), "2026-08-24")

    async def test_todays_worklog_omits_started(self):
        """Jira's own default is correct when no day was named."""
        await self.use_case.execute(
            issue_key="PARSCHAT-1",
            jira_username="ali",
            telegram_username="ali_tg",
            hours=2,
        )

        self.assertNotIn("started", self.repo.jira.add_worklog.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
