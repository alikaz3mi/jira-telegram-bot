"""Tests for daily task status use case."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram.ext import ConversationHandler

from jira_telegram_bot.entities.daily_task_status import DelayReason, DailyStatusSession
from jira_telegram_bot.use_cases.telegram_commands.daily_task_status import DailyTaskStatus


def _make_issue(
    key: str = "TEST-123",
    summary: str = "Test task",
    status: str = "To Do",
    issue_type: str = "Task",
    project_key: str = "TEST",
    story_points: int = 3,
    duedate: str = "2025-01-15",
    epic_link: str = None,
    parent_key: str = None,
) -> MagicMock:
    """Create a mock Jira issue for tests.

    Args:
        key: Issue key.
        summary: Issue summary.
        status: Issue status name.
        issue_type: Issue type name.
        project_key: Project key.
        story_points: Story points value.
        duedate: Due date string.
        epic_link: Epic link custom field value.
        parent_key: Parent issue key (for subtasks).

    Returns:
        Configured MagicMock issue.
    """
    issue = MagicMock()
    issue.key = key
    issue.fields.summary = summary
    issue.fields.status.name = status
    issue.fields.issuetype.name = issue_type
    issue.fields.project.key = project_key
    issue.fields.customfield_10106 = story_points
    issue.fields.duedate = duedate
    issue.fields.customfield_10100 = epic_link
    if parent_key:
        issue.fields.parent.key = parent_key
    else:
        del issue.fields.parent
    return issue


class TestDailyTaskStatus(unittest.IsolatedAsyncioTestCase):
    """Test cases for DailyTaskStatus use case."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_repo = MagicMock()
        self.mock_jira_repo.settings.domain.scheme = "https"
        self.mock_jira_repo.settings.domain.host = "jira.example.com"
        self.mock_user_config = MagicMock()

        self.use_case = DailyTaskStatus(
            jira_repository=self.mock_jira_repo,
            user_config=self.mock_user_config,
        )

    async def test_a_start_daily_status_no_tasks(self):
        """Test starting daily status when user has no tasks."""
        self.mock_user_config.get_user_config.return_value = MagicMock(
            jira_username="test_user"
        )
        self.mock_jira_repo.get_user_actionable_tasks.return_value = []

        update = MagicMock()
        update.effective_user.username = "test_telegram_user"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.user_data = {}

        result = await self.use_case.start_daily_status(update, context)

        update.message.reply_text.assert_called_once()
        self.assertIn("تبریک", update.message.reply_text.call_args[0][0])

    async def test_a_start_daily_status_with_tasks(self):
        """Test starting daily status when user has tasks."""
        mock_issue = _make_issue()

        self.mock_user_config.get_user_config.return_value = MagicMock(
            jira_username="test_user"
        )
        self.mock_jira_repo.get_user_actionable_tasks.return_value = [mock_issue]
        self.mock_jira_repo.get_issue.return_value = None

        update = MagicMock()
        update.effective_user.username = "test_telegram_user"
        update.effective_user.id = 12345
        update.message.reply_text = AsyncMock()
        update.effective_chat.send_message = AsyncMock()
        update.callback_query = None

        context = MagicMock()
        context.user_data = {}

        result = await self.use_case.start_daily_status(update, context)

        self.assertEqual(result, self.use_case.TASK_DISPLAY)
        self.assertIn("daily_status_session", context.user_data)
        self.assertIn("daily_status_issues", context.user_data)

    def test_build_hours_keyboard_has_correct_layout(self):
        """Test that hours keyboard has 3 buttons per row."""
        keyboard = self.use_case._build_hours_keyboard()

        for row in keyboard.inline_keyboard[:-1]:
            self.assertLessEqual(len(row), 3)

    def test_format_task_message_persian(self):
        """Test that task messages are formatted in Persian with issue type."""
        mock_issue = _make_issue()
        self.mock_jira_repo.get_issue.return_value = None

        message = self.use_case._format_task_message(mock_issue, 1, 5)

        self.assertIn("تسک", message)
        self.assertIn("TEST-123", message)
        self.assertIn("📋", message)
        self.assertIn("Task", message)

    def test_format_task_message_with_epic(self):
        """Test task message includes epic name when available."""
        mock_issue = _make_issue(epic_link="EPIC-1")
        epic_issue = _make_issue(key="EPIC-1", summary="My Epic", issue_type="Epic")
        self.mock_jira_repo.get_issue.return_value = epic_issue

        message = self.use_case._format_task_message(mock_issue, 1, 5)

        self.assertIn("اپیک", message)
        self.assertIn("My Epic", message)

    def test_format_task_message_subtask_with_parent(self):
        """Test task message includes parent story for subtasks."""
        mock_issue = _make_issue(
            key="TEST-456",
            issue_type="Sub-task",
            parent_key="TEST-100",
        )
        parent_issue = _make_issue(key="TEST-100", summary="Parent Story")
        self.mock_jira_repo.get_issue.side_effect = lambda k: (
            parent_issue if k == "TEST-100" else None
        )

        message = self.use_case._format_task_message(mock_issue, 1, 3)

        self.assertIn("🔹", message)
        self.assertIn("استوری والد", message)
        self.assertIn("Parent Story", message)

    def test_format_task_message_bug_icon(self):
        """Test that bug issues get the bug icon."""
        mock_issue = _make_issue(issue_type="Bug")
        self.mock_jira_repo.get_issue.return_value = None

        message = self.use_case._format_task_message(mock_issue, 1, 1)

        self.assertIn("🐛", message)

    async def test_a_handle_task_action_log_time(self):
        """Test handling log time action goes to date selection."""
        query = MagicMock()
        query.data = "action|log_time"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()

        result = await self.use_case.handle_task_action(update, context)

        self.assertEqual(result, self.use_case.TIME_SPENT_DATE)
        query.edit_message_text.assert_called_once()

    async def test_a_handle_time_spent_transitions_to_work_description(self):
        """Test that time spent selection transitions to work description."""
        query = MagicMock()
        query.data = "hours|2.5"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()
        context.user_data = {}

        result = await self.use_case.handle_time_spent(update, context)

        self.assertEqual(result, self.use_case.WORK_DESCRIPTION)
        self.assertEqual(context.user_data["pending_hours"], 2.5)
        query.edit_message_text.assert_called_once()

    async def test_a_handle_work_description_logs_work_with_comment(self):
        """Test that work description handler logs work with comment."""
        session = DailyStatusSession(
            telegram_user_id=12345,
            telegram_username="test_user",
            jira_username="jira_user",
            tasks=["TEST-123", "TEST-456"],
            current_task_index=0,
        )

        update = MagicMock()
        update.message.text = "Fixed the login bug"
        update.effective_chat.send_message = AsyncMock()
        update.callback_query = None

        context = MagicMock()
        context.user_data = {
            "daily_status_session": session,
            "daily_status_issues": {"TEST-456": _make_issue(key="TEST-456")},
            "pending_hours": 2.5,
            "selected_work_date": "2025-01-10",
        }
        self.mock_jira_repo.log_work = MagicMock()
        self.mock_jira_repo.get_issue.return_value = None

        result = await self.use_case.handle_work_description(update, context)

        self.mock_jira_repo.log_work.assert_called_once_with(
            "TEST-123",
            9000,
            started_date="2025-01-10",
            comment="Fixed the login bug",
        )
        self.assertEqual(len(session.updates), 1)
        self.assertEqual(session.updates[0].work_description, "Fixed the login bug")
        self.assertEqual(session.updates[0].time_spent_hours, 2.5)

    async def test_a_handle_work_description_skip(self):
        """Test that /skip logs work without comment."""
        session = DailyStatusSession(
            telegram_user_id=12345,
            telegram_username="test_user",
            jira_username="jira_user",
            tasks=["TEST-123"],
            current_task_index=0,
        )

        update = MagicMock()
        update.message.text = "/skip"
        update.effective_chat.send_message = AsyncMock()
        update.callback_query = None

        context = MagicMock()
        context.user_data = {
            "daily_status_session": session,
            "daily_status_issues": {},
            "pending_hours": 1.0,
        }
        self.mock_jira_repo.log_work = MagicMock()
        self.mock_jira_repo.get_user_upcoming_tasks.return_value = []

        result = await self.use_case.handle_work_description(update, context)

        self.mock_jira_repo.log_work.assert_called_once_with(
            "TEST-123",
            3600,
            started_date=None,
            comment=None,
        )
        self.assertIsNone(session.updates[0].work_description)

    async def test_a_handle_task_action_prev(self):
        """Test that prev action decrements current_task_index."""
        session = DailyStatusSession(
            telegram_user_id=12345,
            telegram_username="test_user",
            jira_username="jira_user",
            tasks=["TEST-1", "TEST-2", "TEST-3"],
            current_task_index=2,
        )

        query = MagicMock()
        query.data = "action|prev"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()
        context.user_data = {
            "daily_status_session": session,
            "daily_status_issues": {
                "TEST-2": _make_issue(key="TEST-2"),
            },
        }
        self.mock_jira_repo.get_issue.return_value = None

        result = await self.use_case.handle_task_action(update, context)

        self.assertEqual(session.current_task_index, 1)
        self.assertEqual(result, self.use_case.TASK_DISPLAY)

    async def test_a_handle_task_action_prev_at_first_task(self):
        """Test that prev at first task stays at index 0."""
        session = DailyStatusSession(
            telegram_user_id=12345,
            telegram_username="test_user",
            jira_username="jira_user",
            tasks=["TEST-1", "TEST-2"],
            current_task_index=0,
        )

        query = MagicMock()
        query.data = "action|prev"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query

        context = MagicMock()
        context.user_data = {
            "daily_status_session": session,
            "daily_status_issues": {
                "TEST-1": _make_issue(key="TEST-1"),
            },
        }
        self.mock_jira_repo.get_issue.return_value = None

        result = await self.use_case.handle_task_action(update, context)

        self.assertEqual(session.current_task_index, 0)
        self.assertEqual(result, self.use_case.TASK_DISPLAY)

    def test_build_task_action_keyboard_without_previous(self):
        """Test building task action keyboard without previous button."""
        keyboard = self.use_case._build_task_action_keyboard(show_previous=False)

        self.assertEqual(len(keyboard.inline_keyboard), 2)
        self.assertEqual(len(keyboard.inline_keyboard[0]), 3)
        self.assertEqual(len(keyboard.inline_keyboard[1]), 2)

    def test_build_task_action_keyboard_with_previous(self):
        """Test building task action keyboard with previous button."""
        keyboard = self.use_case._build_task_action_keyboard(show_previous=True)

        self.assertEqual(len(keyboard.inline_keyboard), 2)
        self.assertEqual(len(keyboard.inline_keyboard[0]), 3)
        self.assertEqual(len(keyboard.inline_keyboard[1]), 3)
        self.assertIn("قبلی", keyboard.inline_keyboard[1][0].text)

    def test_escape_markdown(self):
        """Test that special Markdown chars are escaped."""
        raw = "hello_world *bold* [link](url)"
        escaped = DailyTaskStatus._escape_markdown(raw)

        self.assertIn("\\_", escaped)
        self.assertIn("\\*", escaped)
        self.assertIn("\\[", escaped)
        self.assertIn("\\]", escaped)
        self.assertNotIn("hello_world", escaped)

    def test_escape_markdown_no_special_chars(self):
        """Test that plain text is returned unchanged."""
        raw = "simple text 123"
        escaped = DailyTaskStatus._escape_markdown(raw)

        self.assertEqual(raw, escaped)

    async def test_a_finish_session_with_work_descriptions(self):
        """Test finish session includes work descriptions in summary."""
        from jira_telegram_bot.entities.daily_task_status import TaskStatusUpdate

        session = DailyStatusSession(
            telegram_user_id=12345,
            telegram_username="test_user",
            jira_username="jira_user",
            tasks=["TEST-1"],
            current_task_index=1,
        )
        session.updates.append(TaskStatusUpdate(
            issue_key="TEST-1",
            action="log_time",
            time_spent_hours=2.0,
            work_description="Implemented auth",
        ))

        update = MagicMock()
        update.callback_query = None
        update.effective_chat.send_message = AsyncMock()

        context = MagicMock()
        context.user_data = {
            "daily_status_session": session,
            "daily_status_issues": {},
        }
        self.mock_jira_repo.get_user_upcoming_tasks.return_value = []

        result = await self.use_case._finish_session(update, context)

        self.assertEqual(result, ConversationHandler.END)
        sent_msg = update.effective_chat.send_message.call_args[0][0]
        self.assertIn("Implemented auth", sent_msg)
        self.assertIn("2.0", sent_msg)

    async def test_a_finish_session_with_upcoming_tasks(self):
        """Test finish session shows upcoming tasks."""
        session = DailyStatusSession(
            telegram_user_id=12345,
            telegram_username="test_user",
            jira_username="jira_user",
            tasks=[],
            current_task_index=0,
        )

        upcoming_issue = _make_issue(
            key="UPCOMING-1",
            summary="Future task",
            issue_type="Story",
        )
        upcoming_issue.fields.customfield_10109 = "2025-01-20"
        self.mock_jira_repo.get_user_upcoming_tasks.return_value = [upcoming_issue]
        self.mock_jira_repo.get_issue.return_value = None

        update = MagicMock()
        update.callback_query = None
        update.effective_chat.send_message = AsyncMock()

        context = MagicMock()
        context.user_data = {
            "daily_status_session": session,
            "daily_status_issues": {},
        }

        result = await self.use_case._finish_session(update, context)

        self.assertEqual(result, ConversationHandler.END)
        sent_msg = update.effective_chat.send_message.call_args[0][0]
        self.assertIn("UPCOMING-1", sent_msg)
        self.assertIn("Future task", sent_msg)
        self.assertIn("پیش رو", sent_msg)

    async def test_a_finish_session_no_upcoming(self):
        """Test finish session shows empty notice when no upcoming tasks."""
        session = DailyStatusSession(
            telegram_user_id=12345,
            telegram_username="test_user",
            jira_username="jira_user",
            tasks=[],
            current_task_index=0,
        )

        self.mock_jira_repo.get_user_upcoming_tasks.return_value = []

        update = MagicMock()
        update.callback_query = None
        update.effective_chat.send_message = AsyncMock()

        context = MagicMock()
        context.user_data = {
            "daily_status_session": session,
            "daily_status_issues": {},
        }

        await self.use_case._finish_session(update, context)

        sent_msg = update.effective_chat.send_message.call_args[0][0]
        self.assertIn("هیچ تسک جدیدی", sent_msg)

    async def test_a_cancel(self):
        """Test canceling the session."""
        update = MagicMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.user_data = {
            "daily_status_session": MagicMock(),
            "daily_status_issues": {},
        }

        result = await self.use_case.cancel(update, context)

        self.assertEqual(result, ConversationHandler.END)
        update.message.reply_text.assert_called_once()
        self.assertNotIn("daily_status_session", context.user_data)

    def test_build_delay_reason_keyboard(self):
        """Test building delay reason keyboard."""
        keyboard = self.use_case._build_delay_reason_keyboard()

        self.assertIsNotNone(keyboard)
        total_buttons = sum(len(row) for row in keyboard.inline_keyboard[:-1])
        self.assertEqual(total_buttons, len(DelayReason))

    def test_get_epic_name_for_issue_no_epic(self):
        """Test _get_epic_name_for_issue returns None when no epic link."""
        issue = _make_issue(epic_link=None)

        result = self.use_case._get_epic_name_for_issue(issue)

        self.assertIsNone(result)

    def test_get_epic_name_for_issue_with_epic(self):
        """Test _get_epic_name_for_issue returns epic summary."""
        issue = _make_issue(epic_link="EPIC-10")
        epic = _make_issue(key="EPIC-10", summary="My Epic")
        self.mock_jira_repo.get_issue.return_value = epic

        result = self.use_case._get_epic_name_for_issue(issue)

        self.assertEqual(result, "My Epic")

    def test_get_parent_summary_no_parent(self):
        """Test _get_parent_summary returns None when no parent."""
        issue = _make_issue()

        result = self.use_case._get_parent_summary(issue)

        self.assertIsNone(result)

    def test_get_parent_summary_with_parent(self):
        """Test _get_parent_summary returns parent summary."""
        issue = _make_issue(parent_key="PARENT-5")
        parent = _make_issue(key="PARENT-5", summary="Parent Story")
        self.mock_jira_repo.get_issue.return_value = parent

        result = self.use_case._get_parent_summary(issue)

        self.assertEqual(result, "Parent Story")


if __name__ == "__main__":
    unittest.main()
