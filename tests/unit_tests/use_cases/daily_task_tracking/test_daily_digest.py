"""The digest that opens the check-in, and what it leaves to ask about.

The reminder used to ask about tasks one at a time, up to twelve, which
inverted the conversation: the person already knew what they did, and the
bot spent the morning extracting it a tap at a time. The digest leads with
what they could not know — a blocker that cleared, a task that regressed —
and asks one open question instead.
"""
import unittest

from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.daily_task_tracking.build_daily_digest_use_case import (
    BuildDailyDigestUseCase,
    RenderDailyDigestUseCase,
)


def _task(key, check_status=TaskCheckStatus.IN_PROGRESS, cleared=None,
          summary="عنوان"):
    return DailyTaskCheck(
        issue_key=key,
        summary=summary,
        status="In Progress",
        assignee="a_kazemi",
        check_status=check_status,
        project_key="PARSCHAT",
        blockers_cleared_recently=cleared or [],
    )


class TestBuildDailyDigest(unittest.TestCase):
    """Grouping tasks into the story the morning message tells."""

    def setUp(self):
        self.use_case = BuildDailyDigestUseCase()

    def test_a_cleared_blocker_leads(self):
        """This is the only part a person could not work out themselves."""
        digest = self.use_case.execute([
            _task("PARSCHAT-1", cleared=["PARSCHAT-99"]),
            _task("PARSCHAT-2"),
        ])

        self.assertEqual(
            [task.issue_key for task in digest.unblocked], ["PARSCHAT-1"],
        )
        self.assertTrue(digest.has_news)

    def test_each_task_lands_in_exactly_one_group(self):
        """Otherwise the rendered counts disagree with what was fetched."""
        tasks = [
            _task("A", cleared=["X"]),
            _task("B", TaskCheckStatus.STATUS_REGRESSED),
            _task("C", TaskCheckStatus.IN_PROGRESS),
            _task("D", TaskCheckStatus.SHOULD_BE_STARTED),
            _task("E", TaskCheckStatus.NEEDS_WORKLOG),
        ]

        digest = self.use_case.execute(tasks)
        grouped = (
            digest.unblocked + digest.regressed
            + digest.in_flight + digest.waiting
        )

        self.assertEqual(len(grouped), len(tasks))
        self.assertEqual(len({task.issue_key for task in grouped}), len(tasks))

    def test_an_unblocked_task_is_not_also_listed_as_waiting(self):
        digest = self.use_case.execute([
            _task("A", TaskCheckStatus.SHOULD_BE_STARTED, cleared=["X"]),
        ])

        self.assertEqual(len(digest.unblocked), 1)
        self.assertEqual(digest.waiting, [])

    def test_nothing_to_say_is_recognised(self):
        self.assertTrue(self.use_case.execute([]).is_empty)

    def test_routine_work_alone_is_not_news(self):
        digest = self.use_case.execute([_task("A", TaskCheckStatus.IN_PROGRESS)])

        self.assertFalse(digest.has_news)
        self.assertFalse(digest.is_empty)


class TestUnaccountedFor(unittest.TestCase):
    """What is still worth asking after the person has reported."""

    def setUp(self):
        self.tasks = [_task("PARSCHAT-1"), _task("PARSCHAT-2"), _task("PARSCHAT-3")]

    def test_reported_work_is_not_asked_about_again(self):
        remaining = BuildDailyDigestUseCase.unaccounted_for(
            self.tasks, ["PARSCHAT-2"], limit=8,
        )

        self.assertEqual(
            [task.issue_key for task in remaining],
            ["PARSCHAT-1", "PARSCHAT-3"],
        )

    def test_a_full_report_leaves_nothing_to_ask(self):
        remaining = BuildDailyDigestUseCase.unaccounted_for(
            self.tasks, ["PARSCHAT-1", "PARSCHAT-2", "PARSCHAT-3"], limit=8,
        )

        self.assertEqual(remaining, [])

    def test_keys_match_regardless_of_case(self):
        remaining = BuildDailyDigestUseCase.unaccounted_for(
            self.tasks, ["parschat-2"], limit=8,
        )

        self.assertNotIn("PARSCHAT-2", [task.issue_key for task in remaining])

    def test_the_remainder_is_still_capped(self):
        many = [_task(f"PARSCHAT-{i}") for i in range(20)]

        remaining = BuildDailyDigestUseCase.unaccounted_for(many, [], limit=8)

        self.assertEqual(len(remaining), 8)


class TestRenderDailyDigest(unittest.TestCase):
    """What the person actually reads."""

    def setUp(self):
        self.render = RenderDailyDigestUseCase(base_url="https://jira.example.com")
        self.build = BuildDailyDigestUseCase()

    def test_the_cleared_blocker_is_named(self):
        """"You can start" is only actionable if it says what cleared."""
        digest = self.build.execute([_task("PARSCHAT-1", cleared=["PARSCHAT-99"])])

        message = self.render.execute(digest)

        self.assertIn("PARSCHAT-99", message)
        self.assertIn("PARSCHAT-1", message)

    def test_issue_keys_are_linked(self):
        digest = self.build.execute([_task("PARSCHAT-1")])

        self.assertIn(
            '<a href="https://jira.example.com/browse/PARSCHAT-1"',
            self.render.execute(digest),
        )

    def test_a_long_group_says_how_many_were_not_listed(self):
        """A truncated list read as complete is worse than an error."""
        digest = self.build.execute([_task(f"PARSCHAT-{i}") for i in range(12)])

        message = self.render.execute(digest)

        self.assertIn("7", message)

    def test_an_empty_digest_says_so_rather_than_greeting_emptily(self):
        message = self.render.execute(self.build.execute([]))

        self.assertIn("ندارید", message)

    def test_the_open_question_is_asked(self):
        digest = self.build.execute([_task("PARSCHAT-1")])

        self.assertIn("امروز چه کار کردید؟", self.render.execute(digest))

    def test_backlog_is_counted_not_listed(self):
        digest = self.build.execute([_task("PARSCHAT-1")], backlog_count=103)

        self.assertIn("103", self.render.execute(digest))


if __name__ == "__main__":
    unittest.main()
