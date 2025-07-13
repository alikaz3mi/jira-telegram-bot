import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Update, Message, Chat, User, CallbackQuery
from telegram.ext import ContextTypes, ConversationHandler

from jira_telegram_bot.frameworks.telegram.get_current_stories_handler import GetCurrentStoriesHandler
from jira_telegram_bot.use_cases.telegram_commands.get_current_stories import GetCurrentStoriesUseCase
from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport, CurrentStoryItem


class TestGetCurrentStoriesHandler(unittest.IsolatedAsyncioTestCase):
    """Integration tests for GetCurrentStoriesHandler."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.use_case = AsyncMock(spec=GetCurrentStoriesUseCase)
        self.handler = GetCurrentStoriesHandler(get_current_stories_use_case=self.use_case)
        
        # Mock Telegram objects
        self.update = AsyncMock(spec=Update)
        self.context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
        self.context.user_data = {}
        
        # Mock message
        self.update.message = AsyncMock(spec=Message)
        self.update.message.reply_text = AsyncMock()
        
        # Mock callback query
        self.update.callback_query = AsyncMock(spec=CallbackQuery)
        self.update.callback_query.answer = AsyncMock()
        self.update.callback_query.edit_message_text = AsyncMock()
        self.update.callback_query.message = AsyncMock(spec=Message)
        self.update.callback_query.message.chat_id = 12345
        
        # Mock bot
        self.context.bot = AsyncMock()
        self.context.bot.send_document = AsyncMock()
    
    async def test_a_full_conversation_flow(self):
        """Test the full conversation flow from start to completion."""
        # Arrange
        mock_projects = [{"key": "TEST", "name": "Test Project"}]
        mock_sprints = [{"id": "123", "name": "Sprint 1"}]
        mock_story_item = CurrentStoryItem(
            issue_number="TEST-1",
            issue_name="Test Story",
            story_status="In Progress",
            remaining_hours=8.5,
            priority="High",
            assignees_abbr=["AK"],
            release="v1.0",
            label_feature="feature",
            epic_name="Test Epic",
            creation_date_jalali="1403/04/15",
            real_start_date_jalali="1403/04/16",
            complete_date_jalali=None,
            weeks_passed=2.5
        )
        mock_report = CurrentStoriesReport(
            project_key="TEST",
            sprint_name="Sprint 1",
            stories=[mock_story_item]
        )
        self.use_case.get_projects.return_value = mock_projects
        self.use_case.get_sprints_for_project.return_value = mock_sprints
        self.use_case.generate_current_stories_report.return_value = mock_report
        self.use_case.current_stories_service.generate_stories_xlsx.return_value = AsyncMock()
        
        # Act - Start conversation
        result = await self.handler.start_command(self.update, self.context)
        
        # Assert
        self.assertEqual(result, self.handler.SELECT_PROJECT)
        self.update.message.reply_text.assert_called_once()
        self.use_case.get_projects.assert_called_once()
        
        # Act - Select project
        self.update.callback_query.data = "project:TEST"
        result = await self.handler.select_project(self.update, self.context)
        
        # Assert
        self.assertEqual(result, self.handler.SELECT_SPRINT)
        self.assertEqual(self.context.user_data["selected_project"], "TEST")
        self.use_case.get_sprints_for_project.assert_called_once_with("TEST")
        
        # Act - Select sprint
        self.update.callback_query.data = "sprint:123"
        result = await self.handler.select_sprint(self.update, self.context)
        
        # Assert
        self.assertEqual(result, ConversationHandler.END)
        self.use_case.generate_current_stories_report.assert_called_once_with("TEST", "123")
        self.context.bot.send_document.assert_called_once()
    
    async def test_a_start_command_no_projects(self):
        """Test start command when no projects are available."""
        # Arrange
        self.use_case.get_projects.return_value = []
        
        # Act
        result = await self.handler.start_command(self.update, self.context)
        
        # Assert
        self.assertEqual(result, ConversationHandler.END)
        self.update.message.reply_text.assert_called_with("No projects available.")
    
    async def test_a_select_project_no_sprints(self):
        """Test project selection when no sprints are available."""
        # Arrange
        self.update.callback_query.data = "project:TEST"
        self.use_case.get_sprints_for_project.return_value = []
        
        # Act
        result = await self.handler.select_project(self.update, self.context)
        
        # Assert
        self.assertEqual(result, ConversationHandler.END)
        self.update.callback_query.edit_message_text.assert_called_with(
            "No active sprints found for project TEST."
        )
    
    async def test_a_select_sprint_no_stories(self):
        """Test sprint selection when no stories are found."""
        # Arrange
        self.update.callback_query.data = "sprint:123"
        self.context.user_data["selected_project"] = "TEST"
        
        mock_report = CurrentStoriesReport(
            project_key="TEST",
            sprint_name="Sprint 1",
            stories=[]
        )
        self.use_case.generate_current_stories_report.return_value = mock_report
        
        # Act
        result = await self.handler.select_sprint(self.update, self.context)
        
        # Assert
        self.assertEqual(result, ConversationHandler.END)
        self.update.callback_query.edit_message_text.assert_called_with(
            "No stories found in the selected sprint for project TEST."
        )
    
    async def test_a_concurrency_handling(self):
        """Test handling multiple concurrent requests."""
        # Arrange
        mock_projects = [{"key": "TEST", "name": "Test Project"}]
        self.use_case.get_projects.return_value = mock_projects
        
        # Act - Create multiple concurrent requests
        tasks = []
        for i in range(5):
            update_copy = AsyncMock(spec=Update)
            update_copy.message = AsyncMock(spec=Message)
            update_copy.message.reply_text = AsyncMock()
            context_copy = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
            context_copy.user_data = {}
            
            tasks.append(self.handler.start_command(update_copy, context_copy))
        
        # Execute all concurrently
        results = await asyncio.gather(*tasks)
        
        # Assert
        self.assertEqual(len(results), 5)
        self.assertEqual(self.use_case.get_projects.call_count, 5)
    
    async def test_a_error_handling_in_start_command(self):
        """Test error handling in start command."""
        # Arrange
        self.use_case.get_projects.side_effect = Exception("Database error")
        
        # Act
        result = await self.handler.start_command(self.update, self.context)
        
        # Assert
        self.assertEqual(result, ConversationHandler.END)
        self.update.message.reply_text.assert_called_with("Error: Database error")
    
    async def test_a_error_handling_in_select_project(self):
        """Test error handling in project selection."""
        # Arrange
        self.update.callback_query.data = "project:TEST"
        self.use_case.get_sprints_for_project.side_effect = Exception("API error")
        
        # Act
        result = await self.handler.select_project(self.update, self.context)
        
        # Assert
        self.assertEqual(result, ConversationHandler.END)
        self.update.callback_query.edit_message_text.assert_called_with("Error: API error")
    
    async def test_a_error_handling_in_select_sprint(self):
        """Test error handling in sprint selection."""
        # Arrange
        self.update.callback_query.data = "sprint:123"
        self.context.user_data["selected_project"] = "TEST"
        self.use_case.generate_current_stories_report.side_effect = Exception("Report error")
        
        # Act
        result = await self.handler.select_sprint(self.update, self.context)
        
        # Assert
        self.assertEqual(result, ConversationHandler.END)
        # Check that an error message was sent
        args, kwargs = self.update.callback_query.edit_message_text.call_args
        self.assertIn("Error generating report", args[0])
    
    async def test_a_cancel_command(self):
        """Test cancel command."""
        # Act
        result = await self.handler.cancel(self.update, self.context)
        
        # Assert
        self.assertEqual(result, ConversationHandler.END)
        self.update.message.reply_text.assert_called_once_with(
            "Get current stories command cancelled."
        )


if __name__ == '__main__':
    unittest.main()
