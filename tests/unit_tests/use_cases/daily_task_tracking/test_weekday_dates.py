"""Persian weekday phrases must resolve in Python, not in the model."""
import unittest
from datetime import date

from jira_telegram_bot.use_cases.daily_task_tracking.parse_worklog_report_use_case import (
    ParseWorklogReportUseCase,
)

SATURDAY = date(2026, 8, 29)


class TestWeekdayResolution(unittest.TestCase):
    """Asked for "last Thursday" the model returned a Tuesday.

    A worklog filed against the wrong day is not visibly wrong to anyone
    reading it later, so this arithmetic is done in code.
    """

    def _resolve(self, text, today=SATURDAY):
        return ParseWorklogReportUseCase._weekday_date(text, today)

    def test_last_thursday_from_a_saturday(self):
        """The reported bug: 27 Aug was wanted, 24 Aug was written."""
        self.assertEqual(self._resolve("۵شنبه هفته پیش"), date(2026, 8, 27))

    def test_spelled_out_thursday_matches_the_digit_form(self):
        self.assertEqual(
            self._resolve("پنجشنبه هفته پیش"), date(2026, 8, 27),
        )

    def test_bare_weekday_is_the_most_recent_one(self):
        self.assertEqual(self._resolve("پنجشنبه ۲ ساعت"), date(2026, 8, 27))

    def test_longer_name_wins_over_shorter(self):
        """"پنجشنبه" must not be matched by the "شنبه" inside it."""
        self.assertEqual(self._resolve("پنجشنبه"), date(2026, 8, 27))
        self.assertEqual(self._resolve("شنبه"), date(2026, 8, 22))

    def test_today_named_by_weekday_means_a_week_ago(self):
        """Logging against today is done by saying today, not by naming it."""
        self.assertEqual(self._resolve("شنبه", SATURDAY), date(2026, 8, 22))

    def test_last_week_does_not_skip_a_week(self):
        """The Persian week starts Saturday.

        On a Saturday the most recent Thursday already sits in the previous
        week, so adding another seven days lands a week too early.
        """
        self.assertEqual(
            self._resolve("۵شنبه هفته پیش", date(2026, 9, 1)), date(2026, 8, 27),
        )

    def test_monday_last_week(self):
        self.assertEqual(
            self._resolve("دوشنبه هفته پیش"), date(2026, 8, 24),
        )

    def test_no_weekday_named_resolves_to_nothing(self):
        """Relative phrases like «دیروز» stay with the model."""
        self.assertIsNone(self._resolve("دیروز ۲ ساعت کار کردم"))
        self.assertIsNone(self._resolve("۲ ساعت کار کردم"))


class TestDateIsSpelledOut(unittest.TestCase):
    """A bare ISO date reads as correct even when it is days out."""

    def test_weekday_is_named_alongside_the_date(self):
        from jira_telegram_bot.frameworks.telegram.daily_task_tracking_handler import (
            DailyTaskTrackingHandler,
        )

        self.assertEqual(
            DailyTaskTrackingHandler._spell_date("2026-08-27"),
            "پنج‌شنبه 2026-08-27",
        )

    def test_today_shows_no_date(self):
        from jira_telegram_bot.frameworks.telegram.daily_task_tracking_handler import (
            DailyTaskTrackingHandler,
        )

        self.assertIsNone(DailyTaskTrackingHandler._spell_date(None))


if __name__ == "__main__":
    unittest.main()
