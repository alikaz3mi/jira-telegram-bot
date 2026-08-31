"""Epics are project data, not assignee data.

The assistant once answered "there are no epics in Kheradyar's sprint" while
ten existed, because every tool it had ran ``assignee = <caller>`` and epics
carry no assignee. These tests hold the two properties that fixes it: the
query is project-scoped, and nothing it finds is silently dropped.
"""
import unittest
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.assistant_entities import UserRole
from jira_telegram_bot.use_cases.assistant.agent_context import AssistantContext
from jira_telegram_bot.use_cases.assistant.assistant_tools import (
    AssistantTools,
    EPIC_LINK_FIELD,
)


def _story(key, summary, epic_key, status="Backlog"):
    issue = Mock()
    issue.key = key
    issue.fields.summary = summary
    issue.fields.status.name = status
    setattr(issue.fields, EPIC_LINK_FIELD, Mock(value=epic_key) if epic_key else None)
    return issue


def _epic(key, summary):
    issue = Mock()
    issue.key = key
    issue.fields.summary = summary
    return issue


def _task(project_key):
    task = Mock()
    task.project_key = project_key
    return task


class TestSprintEpics(unittest.IsolatedAsyncioTestCase):
    """Rolling a sprint up to the epics it advances."""

    def setUp(self):
        self.stories = [
            _story("KHERADYAR-11", "کیت پایه", "KHERADYAR-1", status="Review"),
            _story("KHERADYAR-12", "معماری RTL", "KHERADYAR-1"),
            _story("KHERADYAR-19", "حالت خالی گفت‌وگو", "KHERADYAR-3"),
        ]
        self.epics = {
            "KHERADYAR-1": _epic("KHERADYAR-1", "سیستم طراحی"),
            "KHERADYAR-3": _epic("KHERADYAR-3", "صفحه گفت‌وگو"),
        }
        self.repo = Mock()
        self.repo.search_issues = Mock(return_value=self.stories)
        self.repo.get_issue = Mock(side_effect=lambda key: self.epics.get(key))

        self.aliases = Mock()
        self.aliases.resolve.return_value = Mock(
            resolved=Mock(canonical="KHERADYAR", display_name="Kheradyar"),
            matches=[],
            is_ambiguous=False,
        )
        self.tasks = AsyncMock()
        self.tasks.execute.return_value = []

    def _tools(self, role=UserRole.CTO, who="alikaz3mi"):
        return AssistantTools(
            context=AssistantContext(
                jira_username=who, telegram_username=who, role=role,
            ),
            get_user_daily_tasks_use_case=self.tasks,
            alias_repository=self.aliases,
            base_url="https://jira.example.com",
            task_manager_repository=self.repo,
        )

    async def test_query_is_scoped_to_the_project_not_the_caller(self):
        """The bug was an assignee filter; it must not come back."""
        await self._tools().sprint_epics("خردیار")

        jql = self.repo.search_issues.call_args.kwargs["jql"]
        self.assertIn('project = "KHERADYAR"', jql)
        self.assertIn("openSprints()", jql)
        self.assertNotIn("assignee", jql)

    async def test_epics_are_reported_with_their_stories(self):
        result = await self._tools().sprint_epics("خردیار")

        self.assertIn("KHERADYAR-1", result)
        self.assertIn("سیستم طراحی", result)
        self.assertIn("KHERADYAR-3", result)
        self.assertIn("KHERADYAR-11", result)

    async def test_epics_are_ordered_by_how_much_of_them_is_in_the_sprint(self):
        result = await self._tools().sprint_epics("خردیار")

        self.assertLess(result.index("KHERADYAR-1"), result.index("KHERADYAR-3"))

    async def test_counts_are_stated(self):
        result = await self._tools().sprint_epics("خردیار")

        self.assertIn("3", result)
        self.assertIn("2", result)

    async def test_a_story_without_an_epic_is_still_reported(self):
        """Dropping it would make the epic list read as the whole sprint."""
        self.repo.search_issues.return_value = self.stories + [
            _story("KHERADYAR-99", "کار بی‌اپیک", None),
        ]

        result = await self._tools().sprint_epics("خردیار")

        self.assertIn("KHERADYAR-99", result)
        self.assertIn("بدون اپیک", result)

    async def test_stories_present_but_no_epic_links_says_so(self):
        """Saying "no epics" when stories exist is what the user was told."""
        self.repo.search_issues.return_value = [
            _story("KHERADYAR-99", "کار بی‌اپیک", None),
        ]

        result = await self._tools().sprint_epics("خردیار")

        self.assertIn("وصل نیستند", result)

    async def test_empty_sprint_is_reported_plainly(self):
        self.repo.search_issues.return_value = []

        result = await self._tools().sprint_epics("خردیار")

        self.assertIn("استوری‌ای نیست", result)

    async def test_jira_failure_is_reported_not_raised(self):
        self.repo.search_issues.side_effect = Exception("504")

        result = await self._tools().sprint_epics("خردیار")

        self.assertIn("ناموفق", result)

    async def test_unreadable_epic_title_does_not_lose_the_epic(self):
        """A failed title lookup must not drop the epic from the summary."""
        self.repo.get_issue.side_effect = Exception("gone")

        result = await self._tools().sprint_epics("خردیار")

        self.assertIn("KHERADYAR-1", result)

    async def test_unknown_project_is_not_guessed(self):
        self.aliases.resolve.return_value = Mock(
            resolved=None, matches=[], is_ambiguous=False,
        )

        result = await self._tools().sprint_epics("یه چیز بی‌ربط")

        self.repo.search_issues.assert_not_called()
        self.assertIn("پیدا نکردم", result)

    async def test_member_without_work_in_the_project_is_refused(self):
        """Sprint contents are not scoped to a person, so may_read cannot rule."""
        self.tasks.execute.return_value = [_task("PARSCHAT")]

        result = await self._tools(role=UserRole.MEMBER).sprint_epics("خردیار")

        self.repo.search_issues.assert_not_called()
        self.assertIn("دسترسی", result)

    async def test_member_with_work_in_the_project_may_look(self):
        self.tasks.execute.return_value = [_task("KHERADYAR")]

        result = await self._tools(role=UserRole.MEMBER).sprint_epics("خردیار")

        self.assertIn("KHERADYAR-1", result)

    async def test_issue_keys_are_rendered_as_links(self):
        result = await self._tools().sprint_epics("خردیار")

        self.assertIn('<a href="https://jira.example.com/browse/KHERADYAR-1"', result)


if __name__ == "__main__":
    unittest.main()
