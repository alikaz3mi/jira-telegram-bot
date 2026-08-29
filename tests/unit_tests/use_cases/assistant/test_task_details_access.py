"""task_details must not become a way to read other people's work."""
import unittest
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.assistant_entities import UserRole
from jira_telegram_bot.use_cases.assistant.agent_context import AssistantContext
from jira_telegram_bot.use_cases.assistant.assistant_tools import AssistantTools


def _issue(key="FOLLOWUP-107", assignee="z_lotfian", description="کار"):
    issue = Mock()
    issue.key = key
    issue.fields.summary = "عنوان"
    issue.fields.status.name = "Backlog"
    issue.fields.assignee.name = assignee
    issue.fields.description = description
    issue.fields.issuelinks = []
    issue.fields.attachment = []
    return issue


class TestTaskDetailsAccess(unittest.IsolatedAsyncioTestCase):
    """The direct-key fallback reaches issues outside the daily list."""

    def setUp(self):
        self.repo = Mock()
        self.repo.jira.issue = Mock(return_value=_issue())
        self.tasks = AsyncMock()
        self.tasks.execute.return_value = []

    def _tools(self, who, role):
        return AssistantTools(
            context=AssistantContext(
                jira_username=who, telegram_username=who, role=role,
            ),
            get_user_daily_tasks_use_case=self.tasks,
            alias_repository=Mock(),
            base_url="https://jira.example.com",
            task_manager_repository=self.repo,
        )

    async def test_owner_may_read_their_own_backlog_task(self):
        """Backlog work is absent from the daily list but still theirs."""
        result = await self._tools("z_lotfian", UserRole.MEMBER).task_details(
            "FOLLOWUP-107",
        )

        self.assertIn("FOLLOWUP-107", result)
        self.assertIn("عنوان", result)

    async def test_member_is_refused_someone_elses_task(self):
        """The fallback must not bypass the permission check."""
        result = await self._tools("m_Mousavi", UserRole.MEMBER).task_details(
            "FOLLOWUP-107",
        )

        self.assertNotIn("عنوان", result)

    async def test_cto_may_read_anyone(self):
        """A role that may read others still can."""
        result = await self._tools("boss", UserRole.CTO).task_details(
            "FOLLOWUP-107",
        )

        self.assertIn("FOLLOWUP-107", result)

    async def test_unknown_key_is_reported_not_crashed(self):
        self.repo.jira.issue.side_effect = Exception("no such issue")

        result = await self._tools("z_lotfian", UserRole.MEMBER).task_details(
            "NOPE-1",
        )

        self.assertIn("NOPE-1", result)

    async def test_blank_key_asks_rather_than_guessing(self):
        result = await self._tools("z_lotfian", UserRole.MEMBER).task_details("")

        self.assertIn("کدام تسک", result)


class TestBoardLink(unittest.IsolatedAsyncioTestCase):
    """A link is the honest answer when a chat list would be truncated."""

    def setUp(self):
        self.aliases = Mock()
        self.aliases.resolve.return_value = Mock(
            resolved=Mock(canonical="PARSCHAT"), is_ambiguous=False, matches=[],
        )
        self.tools = AssistantTools(
            context=AssistantContext(
                jira_username="a_kazemi", telegram_username="ali",
                role=UserRole.MEMBER,
            ),
            get_user_daily_tasks_use_case=AsyncMock(),
            alias_repository=self.aliases,
            base_url="https://jira.example.com",
            task_manager_repository=Mock(),
        )

    async def test_own_link_targets_the_caller(self):
        link = await self.tools.board_link()

        self.assertIn("a_kazemi", link)
        self.assertIn("Unresolved", link)

    async def test_project_filter_is_applied(self):
        link = await self.tools.board_link(project="پارسچت")

        self.assertIn("PARSCHAT", link)

    async def test_unknown_project_is_reported(self):
        self.aliases.resolve.return_value = Mock(
            resolved=None, is_ambiguous=False, matches=[],
        )

        self.assertIn("نشناختم", await self.tools.board_link(project="چیز"))

    async def test_member_cannot_link_to_someone_elses_board(self):
        """The link must obey the same rule as reading the tasks."""
        self.aliases.resolve.return_value = Mock(
            resolved=Mock(canonical="z_lotfian"), is_ambiguous=False, matches=[],
        )

        link = await self.tools.board_link(person="زهرا")

        self.assertNotIn("z_lotfian", link)


class TestListTaskFilters(unittest.IsolatedAsyncioTestCase):
    """Sprint and type are separate questions from status."""

    def setUp(self):
        from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
            DailyTaskCheck,
        )
        from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
            TaskCheckStatus,
        )

        def task(key, kind, sprint, status="In Progress"):
            return DailyTaskCheck(
                issue_key=key, summary="کار", status=status, assignee="ali",
                check_status=TaskCheckStatus.IN_PROGRESS, project_key="PARSCHAT",
                issue_type=kind, sprint_name=sprint,
            )

        self.tasks = AsyncMock()
        self.tasks.execute.return_value = [
            task("PARSCHAT-1", "Story", "S-1405-06-A"),
            task("PARSCHAT-2", "Task", "S-1405-06-A"),
            task("PARSCHAT-4208", "Task", None, status="Backlog"),
        ]
        self.tools = AssistantTools(
            context=AssistantContext(
                jira_username="ali", telegram_username="ali", role=UserRole.MEMBER,
            ),
            get_user_daily_tasks_use_case=self.tasks,
            alias_repository=Mock(),
            base_url="https://jira.example.com",
            task_manager_repository=Mock(),
        )

    async def test_active_sprint_excludes_sprintless_work(self):
        """The list mixes sprint and non-sprint work; the filter separates them."""
        result = await self.tools.list_tasks(in_active_sprint=True)

        self.assertNotIn("PARSCHAT-4208", result)
        self.assertIn("PARSCHAT-1", result)

    async def test_issue_type_is_not_status(self):
        """Asking for Stories must not fall back to filtering by status."""
        result = await self.tools.list_tasks(issue_type="Story")

        self.assertIn("PARSCHAT-1", result)
        self.assertNotIn("PARSCHAT-2", result)

    async def test_type_and_sprint_combine(self):
        result = await self.tools.list_tasks(
            issue_type="Task", in_active_sprint=True,
        )

        self.assertIn("PARSCHAT-2", result)
        self.assertNotIn("PARSCHAT-4208", result)

    async def test_no_sprint_filter_keeps_everything(self):
        result = await self.tools.list_tasks()

        self.assertIn("PARSCHAT-4208", result)


class TestNestedRendering(unittest.IsolatedAsyncioTestCase):
    """Sub-tasks belong under their parent, not in a flat wall of keys."""

    def setUp(self):
        from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
            DailyTaskCheck,
        )
        from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
            TaskCheckStatus,
        )

        def task(key, kind, parent=None):
            return DailyTaskCheck(
                issue_key=key, summary="کار", status="Backlog", assignee="ali",
                check_status=TaskCheckStatus.SHOULD_BE_STARTED,
                project_key="KHERADYAR", issue_type=kind, parent_key=parent,
            )

        self.tasks = AsyncMock()
        self.tasks.execute.return_value = [
            task("KHERADYAR-37", "Story"),
            task("KHERADYAR-192", "Sub-task", "KHERADYAR-37"),
            task("KHERADYAR-193", "Sub-task", "KHERADYAR-37"),
            task("KHERADYAR-50", "Bug"),
        ]
        self.tools = AssistantTools(
            context=AssistantContext(
                jira_username="ali", telegram_username="ali", role=UserRole.MEMBER,
            ),
            get_user_daily_tasks_use_case=self.tasks,
            alias_repository=Mock(),
            base_url="https://jira.example.com",
            task_manager_repository=Mock(),
        )

    async def test_subtasks_are_nested_under_their_parent(self):
        lines = (await self.tools.list_tasks()).splitlines()

        self.assertFalse(lines[0].startswith("   ↳"))
        self.assertIn("KHERADYAR-37", lines[0])
        self.assertTrue(lines[1].startswith("   ↳"))
        self.assertTrue(lines[2].startswith("   ↳"))

    async def test_top_level_types_are_not_indented(self):
        """A Bug with no parent stays at the first level."""
        lines = (await self.tools.list_tasks()).splitlines()
        bug = [line for line in lines if "KHERADYAR-50" in line][0]

        self.assertFalse(bug.startswith("   ↳"))

    async def test_no_task_is_lost(self):
        """Nesting must not drop anything from the count."""
        rendered = await self.tools.list_tasks()

        for key in ("KHERADYAR-37", "KHERADYAR-192", "KHERADYAR-193", "KHERADYAR-50"):
            self.assertIn(key, rendered)

    async def test_orphan_subtask_still_appears(self):
        """A sub-task whose parent is absent is shown under its parent key."""
        from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
            DailyTaskCheck,
        )
        from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
            TaskCheckStatus,
        )
        self.tasks.execute.return_value = [
            DailyTaskCheck(
                issue_key="KHERADYAR-9", summary="کار", status="Backlog",
                assignee="ali", check_status=TaskCheckStatus.IN_PROGRESS,
                project_key="KHERADYAR", issue_type="Sub-task",
                parent_key="KHERADYAR-1",
            ),
        ]

        rendered = await self.tools.list_tasks()

        self.assertIn("KHERADYAR-9", rendered)
        self.assertIn("KHERADYAR-1", rendered)


if __name__ == "__main__":
    unittest.main()
