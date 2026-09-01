"""Delivery dates live on versions, and nothing could read them.

Asked when the Instagram account would be verified, the assistant searched
sprint contents and reported finding nothing. The answer — 2026-09-14 — was
on an unreleased Jira version the whole time, along with the note that every
other Instagram effort is blocked until it lands.

"What work is there" and "when does it ship" are two questions with two
sources. Answering one and dropping the other leaves half the message
unanswered.
"""
import unittest
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.assistant_entities import UserRole
from jira_telegram_bot.use_cases.assistant.agent_context import AssistantContext
from jira_telegram_bot.use_cases.assistant.assistant_tools import AssistantTools


def _version(name, released=False, due="2026-09-14", start=None,
             description="", archived=False, overdue=False):
    version = Mock()
    version.name = name
    version.released = released
    version.archived = archived
    version.releaseDate = due
    version.startDate = start
    version.description = description
    version.overdue = overdue
    return version


def _issue(key, summary="کار", assignee="a_bahrami", status="Backlog"):
    issue = Mock()
    issue.key = key
    issue.fields.summary = summary
    issue.fields.status.name = status
    if assignee:
        issue.fields.assignee = Mock()
        issue.fields.assignee.name = assignee
    else:
        issue.fields.assignee = None
    return issue


class TestReleases(unittest.IsolatedAsyncioTestCase):
    """Upcoming releases, their dates, and what still gates them."""

    def setUp(self):
        self.versions = [
            _version("قدیمی", released=True, due="2025-01-01"),
            _version(
                "R-1405-06 — اعتبارسنجی اینستاگرام",
                due="2026-09-14", start="2026-08-31",
                description="مجوز از متا گرفته می‌شود.",
            ),
            _version("R-1405-06 — وایت‌لیبل", due="2026-09-30"),
        ]
        self.repo = Mock()
        self.repo.get_project_versions = Mock(return_value=self.versions)
        self.repo.search_issues = Mock(return_value=[_issue("PARSCHAT-5999")])

        self.aliases = Mock()
        self.aliases.resolve.return_value = Mock(
            resolved=Mock(canonical="PARSCHAT", display_name="ParsChat"),
            matches=[], is_ambiguous=False,
        )
        self.tasks = AsyncMock()
        self.tasks.execute.return_value = []

    def _tools(self, role=UserRole.CTO, ranker=None):
        return AssistantTools(
            context=AssistantContext(
                jira_username="a_kazemi", telegram_username="a", role=role,
            ),
            get_user_daily_tasks_use_case=self.tasks,
            alias_repository=self.aliases,
            base_url="https://jira.example.com",
            task_manager_repository=self.repo,
            rank_candidates_use_case=ranker,
        )

    async def test_released_versions_are_not_reported_as_upcoming(self):
        result = await self._tools().releases(project="پارسچت")

        self.assertNotIn("قدیمی", result)
        self.assertIn("اعتبارسنجی", result)

    async def test_the_delivery_date_is_stated(self):
        result = await self._tools().releases(project="پارسچت")

        self.assertIn("2026-09-14", result)

    async def test_the_date_carries_its_weekday(self):
        """A bare date is hard to place; a weekday is a commitment."""
        result = await self._tools().releases(project="پارسچت")

        self.assertIn("دوشنبه", result)

    async def test_the_description_explains_what_the_release_means(self):
        result = await self._tools().releases(project="پارسچت")

        self.assertIn("متا", result)

    async def test_open_work_gating_the_release_is_listed(self):
        result = await self._tools().releases(project="پارسچت")

        self.assertIn("PARSCHAT-5999", result)

    async def test_only_unfinished_work_counts_as_gating(self):
        jql = None
        await self._tools().releases(project="پارسچت")
        jql = self.repo.search_issues.call_args.kwargs["jql"]

        self.assertIn("statusCategory != Done", jql)
        self.assertIn("fixVersion", jql)

    async def test_a_release_with_no_open_work_says_so(self):
        self.repo.search_issues.return_value = []

        result = await self._tools().releases(project="پارسچت")

        self.assertIn("نمانده", result)

    async def test_a_failed_issue_lookup_is_not_shown_as_empty(self):
        """An empty release and an unreadable one must not look alike."""
        self.repo.search_issues.side_effect = Exception("504")

        result = await self._tools().releases(project="پارسچت")

        self.assertIn("ناموفق", result)

    async def test_releases_are_ordered_by_date(self):
        result = await self._tools().releases(project="پارسچت")

        self.assertLess(result.index("اعتبارسنجی"), result.index("وایت‌لیبل"))

    async def test_a_project_with_nothing_planned_says_so(self):
        self.repo.get_project_versions.return_value = [
            _version("قدیمی", released=True),
        ]

        result = await self._tools().releases(project="پارسچت")

        self.assertIn("ثبت نشده", result)

    async def test_an_archived_version_is_ignored(self):
        self.repo.get_project_versions.return_value = [
            _version("بایگانی", archived=True),
        ]

        result = await self._tools().releases(project="پارسچت")

        self.assertIn("ثبت نشده", result)

    async def test_an_overdue_release_is_flagged(self):
        self.repo.get_project_versions.return_value = [
            _version("دیرکرد", overdue=True),
        ]

        result = await self._tools().releases(project="پارسچت")

        self.assertIn("عقب‌افتاده", result)

    async def test_a_topic_narrows_which_releases_are_shown(self):
        ranker = AsyncMock()
        ranker.rank_texts.return_value = [(0, 0.6)]

        result = await self._tools(ranker=ranker).releases(
            project="پارسچت", topic="اینستاگرام",
        )

        self.assertIn("اعتبارسنجی", result)
        self.assertNotIn("وایت‌لیبل", result)

    async def test_a_topic_matching_no_release_says_so(self):
        ranker = AsyncMock()
        ranker.rank_texts.return_value = []

        result = await self._tools(ranker=ranker).releases(
            project="پارسچت", topic="بلاکچین",
        )

        self.assertIn("پیدا نشد", result)

    async def test_version_lookup_failure_is_reported(self):
        self.repo.get_project_versions.side_effect = Exception("504")

        result = await self._tools().releases(project="پارسچت")

        self.assertIn("ناموفق", result)

    async def test_a_malformed_version_field_does_not_lose_the_task(self):
        """A release line is a nice-to-have; the description is the answer.

        The first version of this read only guarded the fetch, so a field
        that was present but not iterable raised straight through
        task_details and lost the whole reply.
        """
        tools = self._tools()
        tools.task_manager_repository.jira = Mock()
        issue = Mock()
        issue.fields.fixVersions = Mock()
        tools.task_manager_repository.jira.issue = Mock(return_value=issue)

        self.assertIsNone(tools._release_of("PARSCHAT-1"))

    async def test_a_version_without_a_name_is_skipped(self):
        tools = self._tools()
        tools.task_manager_repository.jira = Mock()
        issue = Mock()
        issue.fields.fixVersions = [_version("", due=None)]
        tools.task_manager_repository.jira.issue = Mock(return_value=issue)

        self.assertIsNone(tools._release_of("PARSCHAT-1"))

    async def test_a_member_outside_the_project_is_refused(self):
        result = await self._tools(role=UserRole.MEMBER).releases(
            project="پارسچت",
        )

        self.repo.get_project_versions.assert_not_called()
        self.assertIn("دسترسی", result)


if __name__ == "__main__":
    unittest.main()
