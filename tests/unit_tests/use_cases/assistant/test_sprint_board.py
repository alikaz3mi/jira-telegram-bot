"""Team-wide sprint questions cannot be answered from one person's list.

Asked which design work was in ParsChat's sprint, the assistant returned
the caller's own backend stories and called them design. The per-person
tools query `assignee = <caller>`, so the question was unanswerable — and
the model filled the gap with a label the data never carried.
"""
import unittest
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.assistant_entities import UserRole
from jira_telegram_bot.use_cases.assistant.agent_context import AssistantContext
from jira_telegram_bot.use_cases.assistant.assistant_tools import AssistantTools


def _issue(key, summary, assignee, kind="Story", status="Backlog"):
    issue = Mock()
    issue.key = key
    issue.fields.summary = summary
    issue.fields.status.name = status
    issue.fields.issuetype.name = kind
    if assignee:
        issue.fields.assignee = Mock()
        issue.fields.assignee.name = assignee
    else:
        issue.fields.assignee = None
    return issue


def _config(jira_username, unit=None, project="PARSCHAT"):
    config = Mock()
    config.jira_username = jira_username
    config.user_components = {project: unit} if unit else {}
    return config


class TestSprintBoard(unittest.IsolatedAsyncioTestCase):
    """A project-scoped view of the sprint, filtered by unit or person."""

    def setUp(self):
        self.issues = [
            _issue("PARSCHAT-5724", "طراحی رابط کاربری", "n_emamdadi"),
            _issue("PARSCHAT-5836", "طراحی پروگرس‌بار", "n_emamdadi", "Sub-task"),
            _issue("PARSCHAT-5715", "بهینه‌سازی بکند", "a_kazemi"),
            _issue("PARSCHAT-5721", "نمایش پلن", "z_lotfian"),
            _issue("PARSCHAT-9999", "بی‌مسئول", None),
        ]
        self.repo = Mock()
        self.repo.search_issues = Mock(return_value=self.issues)

        self.configs = Mock()
        self.configs.get_all_user_configs = Mock(return_value={
            "a": _config("n_emamdadi", "UI/UX"),
            "b": _config("a_kazemi", "DevOps"),
            "c": _config("z_lotfian", "Front-end"),
        })

        self.aliases = Mock()
        self.aliases.resolve.return_value = Mock(
            resolved=Mock(canonical="PARSCHAT", display_name="ParsChat"),
            matches=[], is_ambiguous=False,
        )
        self.tasks = AsyncMock()
        self.tasks.execute.return_value = []

    def _tools(self, role=UserRole.CTO, who="a_kazemi"):
        return AssistantTools(
            context=AssistantContext(
                jira_username=who, telegram_username=who, role=role,
            ),
            get_user_daily_tasks_use_case=self.tasks,
            alias_repository=self.aliases,
            base_url="https://jira.example.com",
            task_manager_repository=self.repo,
            user_config_repository=self.configs,
        )

    async def test_the_query_is_project_scoped_not_caller_scoped(self):
        """The whole bug was an assignee filter; it must not return."""
        await self._tools().sprint_board(project="پارسچت")

        jql = self.repo.search_issues.call_args.kwargs["jql"]
        self.assertIn('project = "PARSCHAT"', jql)
        self.assertIn("openSprints()", jql)
        self.assertNotIn("assignee", jql)

    async def test_design_resolves_to_the_people_recorded_in_that_unit(self):
        result = await self._tools().sprint_board(project="پارسچت", unit="طراحی")

        self.assertIn("PARSCHAT-5724", result)
        self.assertIn("PARSCHAT-5836", result)
        self.assertNotIn("PARSCHAT-5715", result)
        self.assertNotIn("PARSCHAT-5721", result)

    async def test_sub_tasks_are_included(self):
        """Most design work here is sub-tasks; dropping them hides it."""
        result = await self._tools().sprint_board(project="پارسچت", unit="طراحی")

        self.assertIn("PARSCHAT-5836", result)

    async def test_an_unknown_unit_is_refused_rather_than_ignored(self):
        """Ignoring the filter answers a different question than was asked."""
        result = await self._tools().sprint_board(project="پارسچت", unit="آشپزی")

        self.repo.search_issues.assert_not_called()
        self.assertIn("نمی‌شناسم", result)

    async def test_a_unit_nobody_is_recorded_in_says_so(self):
        result = await self._tools().sprint_board(project="پارسچت", unit="بک‌اند")

        self.repo.search_issues.assert_not_called()
        self.assertIn("ثبت نشده", result)

    async def test_english_and_persian_unit_names_both_resolve(self):
        for spoken in ("طراحی", "UI/UX", "design", "ux"):
            with self.subTest(spoken=spoken):
                result = await self._tools().sprint_board(
                    project="پارسچت", unit=spoken,
                )
                self.assertIn("PARSCHAT-5724", result)

    async def test_a_zero_width_non_joiner_does_not_break_matching(self):
        result = await self._tools().sprint_board(project="پارسچت", unit="بک‌اند")

        self.assertIn("ثبت نشده", result)

    async def test_filtering_by_person_works(self):
        self.aliases.resolve.side_effect = [
            Mock(resolved=Mock(canonical="PARSCHAT", display_name="ParsChat"),
                 matches=[], is_ambiguous=False),
            Mock(resolved=Mock(canonical="n_emamdadi", display_name="نفیسه"),
                 matches=[], is_ambiguous=False),
        ]

        result = await self._tools().sprint_board(
            project="پارسچت", person="نفیسه",
        )

        self.assertIn("PARSCHAT-5724", result)
        self.assertNotIn("PARSCHAT-5715", result)

    async def test_issue_type_filter_is_applied(self):
        result = await self._tools().sprint_board(
            project="پارسچت", unit="طراحی", issue_type="Story",
        )

        self.assertIn("PARSCHAT-5724", result)
        self.assertNotIn("PARSCHAT-5836", result)

    async def test_the_total_is_reported_alongside_the_matches(self):
        """A filtered count read as the whole sprint misleads."""
        result = await self._tools().sprint_board(project="پارسچت", unit="طراحی")

        self.assertIn("5", result)

    async def test_an_unassigned_issue_is_still_shown_when_unfiltered(self):
        result = await self._tools().sprint_board(project="پارسچت")

        self.assertIn("PARSCHAT-9999", result)

    async def test_a_filter_matching_nothing_names_the_filter(self):
        self.repo.search_issues.return_value = [
            _issue("PARSCHAT-1", "کار", "a_kazemi"),
        ]

        result = await self._tools().sprint_board(project="پارسچت", unit="طراحی")

        self.assertIn("طراحی", result)
        self.assertIn("پیدا نشد", result)

    async def test_a_member_outside_the_project_is_refused(self):
        self.tasks.execute.return_value = []

        result = await self._tools(role=UserRole.MEMBER).sprint_board(
            project="پارسچت",
        )

        self.repo.search_issues.assert_not_called()
        self.assertIn("دسترسی", result)

    async def test_jira_failure_is_reported_not_raised(self):
        self.repo.search_issues.side_effect = Exception("504")

        result = await self._tools().sprint_board(project="پارسچت")

        self.assertIn("ناموفق", result)

    async def test_issue_keys_are_linked(self):
        result = await self._tools().sprint_board(project="پارسچت", unit="طراحی")

        self.assertIn(
            '<a href="https://jira.example.com/browse/PARSCHAT-5724"', result,
        )


if __name__ == "__main__":
    unittest.main()
