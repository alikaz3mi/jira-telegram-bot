"""Blocking links have a direction, and it decides their meaning.

Jira puts the issue a task waits on in `inwardIssue` ("is blocked by") and
what it holds up in `outwardIssue` ("blocks"). The parser accepted either,
so a task that blocked three others was read as depending on them — and
"your blocker is done" would have fired on the wrong tasks.
"""
import unittest
from unittest.mock import Mock

from jira_telegram_bot.use_cases.daily_task_tracking.get_user_daily_tasks_use_case import (
    GetUserDailyTasksUseCase,
)


def _link(name="Blocks", inward=None, outward=None):
    link = Mock(spec=["type", "inwardIssue", "outwardIssue"])
    link.type = Mock(name_attr=name)
    link.type.name = name
    if inward:
        link.inwardIssue = Mock()
        link.inwardIssue.key = inward
    else:
        del link.inwardIssue
    if outward:
        link.outwardIssue = Mock()
        link.outwardIssue.key = outward
    else:
        del link.outwardIssue
    return link


def _issue(*links):
    issue = Mock()
    issue.key = "PARSCHAT-1"
    issue.fields.issuelinks = list(links)
    return issue


class TestDependencyDirection(unittest.TestCase):
    """Only what a task waits on counts as a dependency."""

    def setUp(self):
        self.use_case = GetUserDailyTasksUseCase.__new__(GetUserDailyTasksUseCase)

    def test_is_blocked_by_is_a_dependency(self):
        found = self.use_case._get_dependencies(_issue(_link(inward="PARSCHAT-9")))

        self.assertEqual(found, ["PARSCHAT-9"])

    def test_blocks_is_not_a_dependency(self):
        """The blockee does not gate this task; it is the other way round."""
        found = self.use_case._get_dependencies(_issue(_link(outward="PARSCHAT-9")))

        self.assertEqual(found, [])

    def test_a_task_that_both_blocks_and_is_blocked_keeps_only_the_blocker(self):
        found = self.use_case._get_dependencies(_issue(
            _link(outward="PARSCHAT-8"),
            _link(inward="PARSCHAT-9"),
        ))

        self.assertEqual(found, ["PARSCHAT-9"])

    def test_unrelated_link_types_are_ignored(self):
        found = self.use_case._get_dependencies(
            _issue(_link(name="Relates", inward="PARSCHAT-9")),
        )

        self.assertEqual(found, [])

    def test_depends_links_are_still_honoured(self):
        found = self.use_case._get_dependencies(
            _issue(_link(name="Depends", inward="PARSCHAT-9")),
        )

        self.assertEqual(found, ["PARSCHAT-9"])

    def test_no_links_is_no_dependencies(self):
        self.assertEqual(self.use_case._get_dependencies(_issue()), [])


if __name__ == "__main__":
    unittest.main()
