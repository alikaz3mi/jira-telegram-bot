"""Tests for daily task status use case."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from jira_telegram_bot.entities.daily_task_status import DelayReason, DailyStatusSession
from jira_telegram_bot.use_cases.telegram_commands.daily_task_status import DailyTaskStatus


class TestDailyTaskStatus(unittest.IsolatedAsyncioTestCase):
    """Test cases for DailyTaskStatus use case."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_jira_repo = MagicMock()
        self.mock_user_config = MagicMock()
        
        self.use_case = DailyTaskStatus(
            jira_repository=self.mock_jira_repo,
            user_config=self.mock_user_config,
        )

    async def test_a_start_daily_status_no_tasks(self):
        """Test starting daily status when user has no tasks."""
        # Arrange
        self.mock_user_config.get_user_config.return_value = MagicMock(
            jira_username="test_user"
        )
        self.mock_jira_repo.get_user_actionable_tasks.return_value = []
        
        update = MagicMock()
        update.effective_user.username = "test_telegram_user"
        update.message.reply_text = AsyncMock()
        
        context = MagicMock()
        context.user_data = {}
        
        # Act
        result = await self.use_case.start_daily_status(update, context)
        
        # Assert
        update.message.reply_text.assert_called_once()
        self.assertIn("تبریک", update.message.reply_text.call_args[0][0])

    async def test_a_start_daily_status_with_tasks(self):
        """Test starting daily status when user has tasks."""
        # Arrange
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Test task"
        mock_issue.fields.status.name = "To Do"
        mock_issue.fields.project.key = "TEST"
        
        self.mock_user_config.get_user_config.return_value = MagicMock(
            jira_username="test_user"
        )
        self.mock_jira_repo.get_user_actionable_tasks.return_value = [mock_issue]
        
        update = MagicMock()
        update.effective_user.username = "test_telegram_user"
        update.effective_user.id = 12345
        update.message.reply_text = AsyncMock()
        update.effective_chat.send_message = AsyncMock()
        
        context = MagicMock()
        context.user_data = {}
        
        # Act
        result = await self.use_case.start_daily_status(update, context)
        
        # Assert
        self.assertEqual(result, self.use_case.TASK_DISPLAY)
        self.assertIn("daily_status_session", context.user_data)
        self.assertIn("daily_status_issues", context.user_data)

    def test_build_hours_keyboard_has_correct_layout(self):
        """Test that hours keyboard has 3 buttons per row."""
        # Act
        keyboard = self.use_case._build_hours_keyboard()
        
        # Assert
        for row in keyboard.inline_keyboard[:-1]:
            self.assertLessEqual(len(row), 3)

    def test_format_task_message_persian(self):
        """Test that task messages are formatted in Persian."""
        # Arrange
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        mock_issue.fields.summary = "Test task"
        mock_issue.fields.status.name = "To Do"
        mock_issue.fields.customfield_10106 = 3
        mock_issue.fields.duedate = "2025-01-15"
        
        # Act
        message = self.use_case._format_task_message(mock_issue, 1, 5)
        
        # Assert
        self.assertIn("تسک", message)
        self.assertIn("TEST-123", message)

    async def test_a_handle_task_action_log_time(self):
        """Test handling log time action."""
        # Arrange
        query = MagicMock()
        query.data = "action|log_time"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        
        update = MagicMock()
        update.callback_query = query
        
        context = MagicMock()
        
        # Act
        result = await self.use_case.handle_task_action(update, context)
        
        # Assert
        self.assertEqual(result, self.use_case.TIME_SPENT)
        query.edit_message_text.assert_called_once()

    async def test_a_handle_time_spent(self):
        """Test handling time spent selection."""
        # Arrange
        query = MagicMock()
        query.data = "hours|2.5"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        
        update = MagicMock()
        update.callback_query = query
        
        session = DailyStatusSession(
            telegram_user_id=12345,
            telegram_username="test_user",
            jira_username="jira_user",
            tasks=["TEST-123", "TEST-456"],
            current_task_index=0,
        )
        
        context = MagicMock()
        context.user_data = {
            "daily_status_session": session,
            "daily_status_issues": {},
        }
        
        self.mock_jira_repo.log_work = MagicMock()
        
        # Act
        with patch.object(self.use_case, '_show_current_task', new=AsyncMock(return_value=self.use_case.TASK_DISPLAY)):
            result = await self.use_case.handle_time_spent(update, context)
        
        # Assert
        self.mock_jira_repo.log_work.assert_called_once()
        self.assertEqual(len(session.updates), 1)
        self.assertEqual(session.updates[0].time_spent_hours, 2.5)

    async def test_a_cancel(self):
        """Test canceling the session."""
        # Arrange
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        
        context = MagicMock()
        context.user_data = {
            "daily_status_session": MagicMock(),
            "daily_status_issues": {},
        }
        
        # Act
        from telegram.ext import ConversationHandler
        result = await self.use_case.cancel(update, context)
        
        # Assert
        self.assertEqual(result, ConversationHandler.END)
        update.message.reply_text.assert_called_once()
        self.assertNotIn("daily_status_session", context.user_data)

    def test_build_delay_reason_keyboard(self):
        """Test building delay reason keyboard."""
        # Act
        keyboard = self.use_case._build_delay_reason_keyboard()
        
        # Assert
        self.assertIsNotNone(keyboard)
        total_buttons = sum(len(row) for row in keyboard.inline_keyboard[:-1])
        self.assertEqual(total_buttons, len(DelayReason))

    def test_build_task_action_keyboard(self):
        """Test building task action keyboard."""
        # Act
        keyboard = self.use_case._build_task_action_keyboard()
        
        # Assert
        self.assertIsNotNone(keyboard)
        self.assertEqual(len(keyboard.inline_keyboard), 2)
        self.assertEqual(len(keyboard.inline_keyboard[0]), 3)
        self.assertEqual(len(keyboard.inline_keyboard[1]), 2)

    async def test_a_trigger_for_all_users(self):
        """Test triggering daily status for all users."""
        # Arrange
        mock_user = MagicMock()
        mock_user.telegram_user_chat_id = 12345
        mock_user.jira_username = "test_user"
        mock_user.telegram_username = "telegram_user"
        
        self.mock_user_config.get_all_users.return_value = [mock_user]
        
        mock_issue = MagicMock()
        mock_issue.key = "TEST-123"
        self.mock_jira_repo.get_user_actionable_tasks.return_value = [mock_issue]
        
        mock_application = MagicMock()
        mock_application.bot.send_message = AsyncMock()
        
        # Act
        await self.use_case.trigger_for_all_users(mock_application)
        
        # Assert
        mock_application.bot.send_message.assert_called_once()
        call_args = mock_application.bot.send_message.call_args
        self.assertEqual(call_args[1]["chat_id"], 12345)


if __name__ == "__main__":
    unittest.main()
