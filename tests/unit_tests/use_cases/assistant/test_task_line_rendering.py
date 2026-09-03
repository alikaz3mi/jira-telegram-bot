"""Every task list renders a task the same way: a linked title, then detail.

`my_briefing` was given a linked title while `list_tasks` kept leading with a
bare issue key and an unlinked summary, so the same task looked like two
different things depending on which question found it. The rendering lives in
one place now, and this pins it there.
"""
import unittest
from unittest.mock import AsyncMock, Mock

from jira_telegram_bot.entities.assistant_entities import UserRole
from jira_telegram_bot.entities.daily_task_tracking.daily_task_check import (
    DailyTaskCheck,
)
from jira_telegram_bot.entities.daily_task_tracking.daily_task_status import (
    TaskCheckStatus,
)
from jira_telegram_bot.use_cases.assistant.agent_context import AssistantContext
from jira_telegram_bot.use_cases.assistant.assistant_tools import AssistantTools


def _task(key, summary, status="Backlog", parent=None, issue_type="Task"):
    return DailyTaskCheck(
        issue_key=key, summary=summary, status=status, assignee="a_kazemi",
        check_status=TaskCheckStatus.IN_PROGRESS, project_key="PARSCHAT",
        parent_key=parent, issue_type=issue_type,
    )


class TestTaskLineRendering(unittest.IsolatedAsyncioTestCase):
    """What a single task looks like wherever it is listed."""

    def setUp(self):
        self.tasks = AsyncMock()
        self.tasks.execute.return_value = [_task("PARSCHAT-1", "یک کار")]

    def _tools(self, base_url="https://jira.example.com"):
        return AssistantTools(
            context=AssistantContext(
                jira_username="a_kazemi", telegram_username="a_kazemi",
                role=UserRole.CTO,
            ),
            get_user_daily_tasks_use_case=self.tasks,
            alias_repository=Mock(),
            base_url=base_url,
            task_manager_repository=Mock(),
            user_config_repository=Mock(),
            media_sink=[],
        )

    async def test_the_title_is_the_link(self):
        result = await self._tools().list_tasks()

        self.assertIn(
            '<a href="https://jira.example.com/browse/PARSCHAT-1">یک کار</a>',
            result,
        )

    async def test_the_key_is_not_the_link(self):
        """A bare key was never what anyone recognised the work by."""
        result = await self._tools().list_tasks()

        self.assertNotIn('">PARSCHAT-1</a>', result)

    async def test_the_key_still_appears_on_the_detail_line(self):
        result = await self._tools().list_tasks()

        self.assertIn("· PARSCHAT-1", result)

    async def test_no_markdown_is_emitted(self):
        result = await self._tools().list_tasks()

        self.assertNotIn("**", result)
        self.assertNotIn("](", result)

    async def test_a_summary_with_html_characters_is_escaped(self):
        """One unescaped & costs the whole message, not one character."""
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", "پاسخ‌گویی & <b>کاهش</b> هزینه"),
        ]

        result = await self._tools().list_tasks()

        self.assertIn("&amp;", result)
        self.assertNotIn("<b>کاهش</b>", result)

    async def test_a_subtask_is_indented_under_its_parent(self):
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", "والد"),
            _task(
                "PARSCHAT-2", "فرزند",
                parent="PARSCHAT-1", issue_type="Sub-task",
            ),
        ]

        result = await self._tools().list_tasks()
        child = [line for line in result.split("\n") if "↳" in line]

        self.assertTrue(child)
        self.assertIn("فرزند", child[0])

    async def test_a_subtasks_detail_lines_up_under_its_own_title(self):
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", "والد"),
            _task(
                "PARSCHAT-2", "فرزند",
                parent="PARSCHAT-1", issue_type="Sub-task",
            ),
        ]

        result = await self._tools().list_tasks()

        self.assertIn("      ⚪️ Backlog · PARSCHAT-2", result)

    async def test_a_status_carries_its_stage_as_an_icon(self):
        self.tasks.execute.return_value = [
            _task("PARSCHAT-1", "یک کار", status="In Progress"),
        ]

        result = await self._tools().list_tasks()

        self.assertIn("🔵 In Progress", result)

    async def test_without_a_base_url_the_title_survives_unlinked(self):
        result = await self._tools(base_url="").list_tasks()

        self.assertIn("یک کار", result)
        self.assertNotIn("<a href", result)

    async def test_an_empty_summary_falls_back_to_the_key(self):
        self.tasks.execute.return_value = [_task("PARSCHAT-1", "")]

        result = await self._tools().list_tasks()

        self.assertIn(">PARSCHAT-1</a>", result)


if __name__ == "__main__":
    unittest.main()
