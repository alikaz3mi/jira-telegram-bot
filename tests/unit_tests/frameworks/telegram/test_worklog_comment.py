"""A worklog comment says what was done, not what was asked for.

Reported from Tempo: a worklog carried the comment
"ریموت — میخوام روی تسکهای برنامه ریزیم توی برد خودم ۴ ساعت تایم ریموت برای
روز شنبه ثبت کنم" — the request to record time, written verbatim into the
field a colleague reads months later. It also repeated the hours, the day and
the work type, each of which is its own column on the same worklog.
"""
import unittest

from jira_telegram_bot.frameworks.telegram.daily_task_tracking_handler import (
    _strip_logging_framing,
)


class TestStripLoggingFraming(unittest.TestCase):
    """What survives from a spoken request to a stored comment."""

    def test_the_reported_message_keeps_only_its_subject(self):
        stripped = _strip_logging_framing(
            "میخوام روی تسکهای برنامه ریزیم توی برد خودم ۴ ساعت تایم ریموت "
            "برای روز شنبه ثبت کنم",
        )

        self.assertEqual(stripped, "تسکهای برنامه ریزیم")

    def test_the_hours_are_not_repeated_in_the_comment(self):
        stripped = _strip_logging_framing("امروز ۳ ساعت روی رفع باگ ورود کار کردم")

        self.assertEqual(stripped, "رفع باگ ورود")

    def test_the_work_type_is_not_repeated_in_the_comment(self):
        """work_type is its own field and is already prefixed to the comment."""
        stripped = _strip_logging_framing("دیروز ۲ ساعت ریموت روی تنزل خودکار")

        self.assertEqual(stripped, "تنزل خودکار")

    def test_a_fractional_hour_comes_off_whole(self):
        stripped = _strip_logging_framing("۴ ساعت و نیم روی گزارش‌ها")

        self.assertEqual(stripped, "گزارش‌ها")

    def test_english_framing_is_stripped_too(self):
        stripped = _strip_logging_framing(
            "I want to log 2 hours for the quota refactor",
        )

        self.assertEqual(stripped, "the quota refactor")

    def test_a_bare_subject_is_left_alone(self):
        for text in ("رفع باگ ورود", "ریفکتورینگ سیستم اشتراک", "APISIX"):
            with self.subTest(text=text):
                self.assertEqual(_strip_logging_framing(text), text)

    def test_an_empty_description_stays_empty(self):
        self.assertEqual(_strip_logging_framing(""), "")

    def test_a_description_that_is_only_framing_is_kept(self):
        """An unhelpful comment beats an empty one."""
        self.assertEqual(_strip_logging_framing("ثبت کنم"), "ثبت کنم")


if __name__ == "__main__":
    unittest.main()
