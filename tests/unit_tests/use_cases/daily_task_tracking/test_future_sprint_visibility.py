"""Work committed to the next sprint must be visible before it starts.

A Jira sprint is open, future, or closed. The daily query named only the
first two states — "in an open sprint, or in no sprint" — so anything in a
FUTURE sprint fell through the gap. Reported: "دیروز سمت آواخرد تایم گذاشتم"
was answered with every project except Avakherad, because FOLLOWUP-109 sat in
S-1405-06-B, a sprint starting in three days.

The opposite mistake is as bad: pulling in a sprint two months out buries
today's work under sixty rows.
"""
import re
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.use_cases.daily_task_tracking.get_user_daily_tasks_use_case import (
    UPCOMING_SPRINT_DAYS,
    GetUserDailyTasksUseCase,
)


def _sprint(state, starts_in_days=None):
    """A sprint field value in the string form Jira Server returns."""
    if starts_in_days is None:
        return f"com.atlassian.greenhopper.service.sprint.Sprint@1[id=1,state={state},name=S-1,startDate=<null>]"
    start = datetime.now(timezone.utc) + timedelta(days=starts_in_days)
    return (
        f"com.atlassian.greenhopper.service.sprint.Sprint@1[id=1,"
        f"state={state},name=S-1,startDate={start.isoformat()},"
        f"endDate={(start + timedelta(days=14)).isoformat()}]"
    )


def _issue(key, sprints):
    issue = Mock()
    issue.key = key
    issue.fields.customfield_10104 = sprints
    return issue


class TestFutureSprintHorizon(unittest.TestCase):
    """Which sprints count as near enough to be today's work."""

    def setUp(self):
        repository = Mock()
        repository.jira_sprint_id = "customfield_10104"
        self.use_case = GetUserDailyTasksUseCase(
            task_manager_repository=repository,
        )

    def test_a_sprint_starting_soon_is_visible(self):
        issue = _issue("FOLLOWUP-109", [_sprint("FUTURE", starts_in_days=3)])

        self.assertFalse(self.use_case._starts_too_far_ahead(issue))

    def test_a_distant_sprint_is_left_out(self):
        """Work two months out is not a daily task."""
        issue = _issue("PARSCHAT-5936", [_sprint("FUTURE", starts_in_days=60)])

        self.assertTrue(self.use_case._starts_too_far_ahead(issue))

    def test_the_horizon_is_the_configured_window(self):
        inside = _issue("A-1", [_sprint("FUTURE", UPCOMING_SPRINT_DAYS - 1)])
        outside = _issue("A-2", [_sprint("FUTURE", UPCOMING_SPRINT_DAYS + 1)])

        self.assertFalse(self.use_case._starts_too_far_ahead(inside))
        self.assertTrue(self.use_case._starts_too_far_ahead(outside))

    def test_an_active_sprint_is_always_visible(self):
        issue = _issue("A-1", [_sprint("ACTIVE", starts_in_days=-2)])

        self.assertFalse(self.use_case._starts_too_far_ahead(issue))

    def test_an_issue_in_no_sprint_is_always_visible(self):
        """Kanban and backlog work has no sprint and must not be filtered."""
        self.assertFalse(self.use_case._starts_too_far_ahead(_issue("AVA-90", None)))
        self.assertFalse(self.use_case._starts_too_far_ahead(_issue("AVA-89", [])))

    def test_an_issue_in_both_an_active_and_a_distant_sprint_stays(self):
        """Being in this sprint is what matters, whatever else it is in."""
        issue = _issue("A-1", [
            _sprint("ACTIVE", starts_in_days=-2),
            _sprint("FUTURE", starts_in_days=60),
        ])

        self.assertFalse(self.use_case._starts_too_far_ahead(issue))

    def test_a_sprint_with_no_start_date_is_not_filtered_out(self):
        """Nothing is known about it, so it is not evidence for hiding work."""
        issue = _issue("A-1", [_sprint("FUTURE")])

        self.assertFalse(self.use_case._starts_too_far_ahead(issue))

    def test_an_unparsable_sprint_never_hides_the_issue(self):
        issue = _issue("A-1", ["not a sprint string at all"])

        self.assertFalse(self.use_case._starts_too_far_ahead(issue))


class TestTheDailyQueryCoversEverySprintState(unittest.IsolatedAsyncioTestCase):
    """The JQL must not silently drop a whole sprint state."""

    async def test_future_sprints_are_not_excluded_by_the_query(self):
        repository = Mock()
        repository.search_for_issues = Mock(return_value=[])
        use_case = GetUserDailyTasksUseCase(task_manager_repository=repository)

        await use_case.execute(jira_username="a_kazemi")

        jql = repository.search_for_issues.call_args.args[0]
        self.assertIn("closedSprints()", jql)
        self.assertNotIn("Sprint in openSprints()", jql)

    async def test_issues_with_no_sprint_are_still_included(self):
        """`Sprint not in closedSprints()` alone drops an empty sprint field."""
        repository = Mock()
        repository.search_for_issues = Mock(return_value=[])
        use_case = GetUserDailyTasksUseCase(task_manager_repository=repository)

        await use_case.execute(jira_username="a_kazemi")

        jql = repository.search_for_issues.call_args.args[0]
        self.assertIn("Sprint is EMPTY", jql)


if __name__ == "__main__":
    unittest.main()
