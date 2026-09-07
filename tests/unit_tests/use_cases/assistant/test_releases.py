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
from jira_telegram_bot.use_cases.assistant.assistant_tools import EPIC_LINK_FIELD


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

        self.assertIn("۲۳ شهریور", result)
        self.assertNotIn("2026-09-14", result)

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
        """Rendering also counts epic progress, so find the release query."""
        await self._tools().releases(project="پارسچت")

        version_queries = [
            call.kwargs["jql"]
            for call in self.repo.search_issues.call_args_list
            if "fixVersion" in call.kwargs.get("jql", "")
        ]

        self.assertTrue(version_queries)
        self.assertIn("statusCategory != Done", version_queries[0])

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


class TestReleaseWorkIsGroupedByEpic(unittest.TestCase):
    """A release lists its epics, not a flat run of issue keys.

    Reported: the release report ran stories and epics together in one list,
    so the shape of the release — which deliverable is where — had to be
    reconstructed by the reader.
    """

    def setUp(self):
        self.tools = AssistantTools.__new__(AssistantTools)
        self.tools.base_url = "https://jira.example.com"
        self.tools.task_manager_repository = Mock()
        self.tools.task_manager_repository.search_issues = Mock(return_value=[])
        self.tools.task_manager_repository.get_issue = Mock(
            return_value=Mock(**{"fields.summary": "اعتبارسنجی اینستاگرام"}),
        )

    def _issue(self, key, summary, epic, status="Backlog", assignee="a_kazemi"):
        issue = Mock()
        issue.key = key
        issue.fields.summary = summary
        issue.fields.status.name = status
        issue.fields.status.statusCategory.name = "To Do"
        issue.fields.assignee.displayName = assignee
        issue.fields.assignee.name = assignee
        setattr(issue.fields, EPIC_LINK_FIELD, Mock(value=epic))
        return issue

    def test_stories_sit_under_their_epic(self):
        issues = [
            self._issue("PARSCHAT-1", "کار یک", "E1"),
            self._issue("PARSCHAT-2", "کار دو", "E1"),
        ]

        rendered = "\n".join(self.tools._render_release_work(issues))

        self.assertLess(
            rendered.index("اعتبارسنجی اینستاگرام"),
            rendered.index("کار یک"),
        )

    def test_the_epic_carries_its_progress(self):
        self.tools.task_manager_repository.search_issues = Mock(
            return_value=[Mock(**{"fields.status.statusCategory.name": "Done"})] * 2
            + [Mock(**{"fields.status.statusCategory.name": "To Do"})] * 3,
        )

        rendered = "\n".join(
            self.tools._render_release_work([self._issue("P-1", "کار", "E1")]),
        )

        self.assertIn("۲ از ۵ انجام شده", rendered)

    def test_the_title_carries_the_link_not_the_key(self):
        rendered = "\n".join(
            self.tools._render_release_work([self._issue("P-1", "کار یک", "E1")]),
        )

        self.assertIn(
            '<a href="https://jira.example.com/browse/P-1">کار یک</a>', rendered,
        )
        self.assertNotIn('">P-1</a>', rendered)

    def test_the_key_still_appears_on_the_detail_line(self):
        rendered = "\n".join(
            self.tools._render_release_work([self._issue("P-1", "کار", "E1")]),
        )

        detail = [line for line in rendered.split("\n") if "Backlog" in line]
        self.assertTrue(detail)
        self.assertIn("P-1", detail[0])

    def test_work_without_an_epic_is_still_reported(self):
        """A story with no epic link must not vanish from the release."""
        orphan = self._issue("P-9", "بدون اپیک", None)
        setattr(orphan.fields, EPIC_LINK_FIELD, None)

        rendered = "\n".join(self.tools._render_release_work([orphan]))

        self.assertIn("بدون اپیک", rendered)
        self.assertIn("P-9", rendered)

    def test_a_summary_with_html_characters_is_escaped(self):
        rendered = "\n".join(
            self.tools._render_release_work([self._issue("P-1", "A & B", "E1")]),
        )

        self.assertIn("A &amp; B", rendered)

    def test_an_unreadable_epic_count_falls_back_to_what_is_known(self):
        self.tools.task_manager_repository.search_issues = Mock(
            side_effect=Exception("504"),
        )

        rendered = "\n".join(
            self.tools._render_release_work([self._issue("P-1", "کار", "E1")]),
        )

        self.assertIn("۰ از ۱", rendered)

