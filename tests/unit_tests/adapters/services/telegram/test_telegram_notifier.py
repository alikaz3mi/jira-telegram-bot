from __future__ import annotations

import unittest
from datetime import datetime
from datetime import timedelta
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from jira_telegram_bot.adapters.services.telegram.telegram_notifier import TelegramNotifier
from jira_telegram_bot.entities.deadline_alert import DeadlineAlert


class TestTelegramNotifier(unittest.TestCase):
    """Test cases for TelegramNotifier."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.telegram_settings = MagicMock()
        self.telegram_settings.TOKEN = "test_token"
        
        self.user_config_repository = AsyncMock()
        
        self.notifier = TelegramNotifier(
            telegram_settings=self.telegram_settings,
            user_config_repository=self.user_config_repository,
        )
    
    def _create_deadline_alert(
        self,
        issue_key: str = "TEST-123",
        summary: str = "Test issue",
        assignee: str = "john.doe",
        days_remaining: int = 1,
        status: str = "In Progress",
        priority: str = "High",
        project_key: str = "TEST",
    ) -> DeadlineAlert:
        """Create a deadline alert for testing."""
        due_date = datetime.now() + timedelta(days=days_remaining)
        
        return DeadlineAlert(
            issue_key=issue_key,
            summary=summary,
            assignee=assignee,
            due_date=due_date,
            target_end=None,
            days_remaining=days_remaining,
            project_key=project_key,
            status=status,
            priority=priority,
            issue_url=f"https://test.atlassian.net/browse/{issue_key}",
        )
    
    async def test_format_alert_message_urgent(self):
        """Test formatting an urgent alert message."""
        # Arrange
        alert = self._create_deadline_alert(days_remaining=1)
        
        # Act
        message = await self.notifier.format_alert_message(alert)
        
        # Assert
        self.assertIn("⚡ *Deadline Alert*", message)
        self.assertIn("TEST-123", message)
        self.assertIn("Test issue", message)
        self.assertIn("Due tomorrow", message)
        self.assertIn("In Progress", message)
        self.assertIn("🟠 *Priority:* High", message)
    
    async def test_format_alert_message_overdue(self):
        """Test formatting an overdue alert message."""
        # Arrange
        alert = self._create_deadline_alert(days_remaining=-2)
        
        # Act
        message = await self.notifier.format_alert_message(alert)
        
        # Assert
        self.assertIn("🚨 *Deadline Alert*", message)
        self.assertIn("⚠️ OVERDUE by 2 days", message)
    
    async def test_format_alert_message_due_today(self):
        """Test formatting an alert for today."""
        # Arrange
        alert = self._create_deadline_alert(days_remaining=0)
        
        # Act
        message = await self.notifier.format_alert_message(alert)
        
        # Assert
        self.assertIn("🔥 *Deadline Alert*", message)
        self.assertIn("🔥 DUE TODAY", message)
    
    async def test_format_alert_message_with_mention(self):
        """Test formatting message with user mention."""
        # Arrange
        alert = self._create_deadline_alert()
        
        # Act
        message = await self.notifier.format_alert_message(
            alert,
            include_mention=True,
            telegram_username="johndoe",
        )
        
        # Assert
        self.assertIn("@johndoe", message)
    
    async def test_format_group_message_multiple_alerts(self):
        """Test formatting group message with multiple alerts."""
        # Arrange
        alerts = [
            self._create_deadline_alert(issue_key="TEST-1", days_remaining=-1),  # Overdue
            self._create_deadline_alert(issue_key="TEST-2", days_remaining=0),   # Today
            self._create_deadline_alert(issue_key="TEST-3", days_remaining=1),   # Urgent
        ]
        
        # Act
        message = await self.notifier._format_group_message(alerts, mention_users=False)
        
        # Assert
        self.assertIn("🚨 *Team Deadline Report* (3 issues)", message)
        self.assertIn("🚨 **OVERDUE**", message)
        self.assertIn("🔥 **TODAY**", message)
        self.assertIn("⚡ **URGENT**", message)
        self.assertIn("TEST-1", message)
        self.assertIn("TEST-2", message)
        self.assertIn("TEST-3", message)
    
    async def test_format_group_message_with_mentions(self):
        """Test formatting group message with user mentions."""
        # Arrange
        alerts = [
            self._create_deadline_alert(issue_key="TEST-1", assignee="john.doe"),
        ]
        
        # Mock user config lookup
        mock_config = MagicMock()
        mock_config.jira_username = "john.doe"
        mock_config.telegram_username = "johndoe"
        
        self.user_config_repository.get_all_user_configs.return_value = {
            "johndoe": mock_config
        }
        
        # Act
        message = await self.notifier._format_group_message(alerts, mention_users=True)
        
        # Assert
        self.assertIn("@johndoe", message)
    
    @patch('asyncio.get_event_loop')
    @patch('requests.post')
    async def test_send_message_success(self, mock_post, mock_loop):
        """Test successful message sending."""
        # Arrange
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        mock_executor = AsyncMock()
        mock_executor.return_value = mock_response
        mock_loop.return_value.run_in_executor = mock_executor
        
        # Act
        result = await self.notifier._send_message(12345, "Test message")
        
        # Assert
        self.assertTrue(result)
        mock_executor.assert_called_once()
    
    @patch('asyncio.get_event_loop')
    @patch('requests.post')
    async def test_send_message_failure(self, mock_post, mock_loop):
        """Test message sending failure."""
        # Arrange
        mock_post.side_effect = Exception("Network error")
        
        mock_executor = AsyncMock()
        mock_executor.side_effect = Exception("Network error")
        mock_loop.return_value.run_in_executor = mock_executor
        
        # Act
        result = await self.notifier._send_message(12345, "Test message")
        
        # Assert
        self.assertFalse(result)
    
    async def test_send_personal_notification(self):
        """Test sending personal notification."""
        # Arrange
        alert = self._create_deadline_alert()
        
        with patch.object(self.notifier, '_send_message', return_value=True) as mock_send:
            # Act
            result = await self.notifier.send_personal_notification(12345, alert)
            
            # Assert
            self.assertTrue(result)
            mock_send.assert_called_once_with(12345, unittest.mock.ANY)
    
    async def test_send_group_notification(self):
        """Test sending group notification."""
        # Arrange
        alerts = [self._create_deadline_alert()]
        
        with patch.object(self.notifier, '_send_message', return_value=True) as mock_send:
            # Act
            result = await self.notifier.send_group_notification(-12345, alerts)
            
            # Assert
            self.assertTrue(result)
            mock_send.assert_called_once_with(-12345, unittest.mock.ANY)
    
    async def test_send_group_notification_empty_alerts(self):
        """Test sending group notification with empty alerts list."""
        # Act
        result = await self.notifier.send_group_notification(-12345, [])
        
        # Assert
        self.assertTrue(result)
    
    def test_get_urgency_emoji(self):
        """Test urgency emoji mapping."""
        # Test cases
        test_cases = [
            ("overdue", "🚨"),
            ("today", "🔥"),
            ("urgent", "⚡"),
            ("high", "⚠️"),
            ("medium", "📅"),
            ("low", "ℹ️"),
            ("unknown", "📝"),
        ]
        
        for urgency, expected_emoji in test_cases:
            with self.subTest(urgency=urgency):
                emoji = self.notifier._get_urgency_emoji(urgency)
                self.assertEqual(emoji, expected_emoji)
    
    def test_get_priority_emoji(self):
        """Test priority emoji mapping."""
        # Test cases
        test_cases = [
            ("Highest", "🔴"),
            ("Critical", "🔴"),
            ("High", "🟠"),
            ("Medium", "🟡"),
            ("Low", "🟢"),
            ("Unknown", "⚪"),
        ]
        
        for priority, expected_emoji in test_cases:
            with self.subTest(priority=priority):
                emoji = self.notifier._get_priority_emoji(priority)
                self.assertEqual(emoji, expected_emoji)
    
    def test_get_short_deadline_text(self):
        """Test short deadline text generation."""
        # Test cases
        test_cases = [
            (-2, "⚠️ Overdue by 2 days"),
            (0, "🔥 Due today"),
            (1, "⏰ Due tomorrow"),
            (3, "📅 Due in 3 days"),
        ]
        
        for days_remaining, expected_text in test_cases:
            with self.subTest(days_remaining=days_remaining):
                alert = self._create_deadline_alert(days_remaining=days_remaining)
                text = self.notifier._get_short_deadline_text(alert)
                self.assertEqual(text, expected_text)
    
    async def test_get_telegram_username_found(self):
        """Test getting telegram username when user is found."""
        # Arrange
        mock_config = MagicMock()
        mock_config.jira_username = "john.doe"
        mock_config.telegram_username = "johndoe"
        
        self.user_config_repository.get_all_user_configs.return_value = {
            "johndoe": mock_config
        }
        
        # Act
        username = await self.notifier._get_telegram_username("john.doe")
        
        # Assert
        self.assertEqual(username, "johndoe")
    
    async def test_get_telegram_username_not_found(self):
        """Test getting telegram username when user is not found."""
        # Arrange
        self.user_config_repository.get_all_user_configs.return_value = {}
        
        # Act
        username = await self.notifier._get_telegram_username("unknown.user")
        
        # Assert
        self.assertIsNone(username)


if __name__ == "__main__":
    unittest.main()
