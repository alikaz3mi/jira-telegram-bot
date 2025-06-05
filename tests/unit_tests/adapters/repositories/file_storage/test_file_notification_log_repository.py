from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from jira_telegram_bot.adapters.repositories.file_storage.file_notification_log_repository import FileNotificationLogRepository
from jira_telegram_bot.entities.deadline_alert import DeadlineAlert


class TestFileNotificationLogRepository(unittest.TestCase):
    """Test cases for FileNotificationLogRepository."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file_path = Path(self.temp_dir) / "test_notifier_log.jsonl"
        self.repository = FileNotificationLogRepository(str(self.log_file_path))
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        # Use shutil.rmtree to remove directory and all its contents
        shutil.rmtree(self.temp_dir)
    
    def _create_deadline_alert(
        self,
        issue_key: str = "TEST-123",
        summary: str = "Test issue",
        assignee: str = "john.doe",
        days_remaining: int = 1,
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
            project_key="TEST",
            status="In Progress",
            priority="High",
            issue_url=f"https://test.atlassian.net/browse/{issue_key}",
        )
    
    async def test_log_notification_sent(self):
        """Test logging a sent notification."""
        # Arrange
        alert = self._create_deadline_alert()
        notification_date = datetime.now()
        
        # Act
        await self.repository.log_notification_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=notification_date,
            alert=alert,
        )
        
        # Assert
        self.assertTrue(self.log_file_path.exists())
        
        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            self.assertTrue(content)
            
            log_entry = json.loads(content)
            self.assertEqual(log_entry["issue_key"], "TEST-123")
            self.assertEqual(log_entry["chat_id"], 12345)
            self.assertEqual(log_entry["notification_date"], notification_date.date().isoformat())
            self.assertIn("alert_data", log_entry)
            self.assertEqual(log_entry["alert_data"]["summary"], "Test issue")
    
    async def test_has_notification_been_sent_true(self):
        """Test checking for sent notification that exists."""
        # Arrange
        alert = self._create_deadline_alert()
        notification_date = datetime.now()
        
        await self.repository.log_notification_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=notification_date,
            alert=alert,
        )
        
        # Act
        result = await self.repository.has_notification_been_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=notification_date,
        )
        
        # Assert
        self.assertTrue(result)
    
    async def test_has_notification_been_sent_false(self):
        """Test checking for sent notification that doesn't exist."""
        # Act
        result = await self.repository.has_notification_been_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=datetime.now(),
        )
        
        # Assert
        self.assertFalse(result)
    
    async def test_has_notification_been_sent_different_issue(self):
        """Test checking for different issue."""
        # Arrange
        alert = self._create_deadline_alert()
        notification_date = datetime.now()
        
        await self.repository.log_notification_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=notification_date,
            alert=alert,
        )
        
        # Act
        result = await self.repository.has_notification_been_sent(
            issue_key="TEST-456",  # Different issue
            chat_id=12345,
            notification_date=notification_date,
        )
        
        # Assert
        self.assertFalse(result)
    
    async def test_has_notification_been_sent_different_chat(self):
        """Test checking for different chat ID."""
        # Arrange
        alert = self._create_deadline_alert()
        notification_date = datetime.now()
        
        await self.repository.log_notification_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=notification_date,
            alert=alert,
        )
        
        # Act
        result = await self.repository.has_notification_been_sent(
            issue_key="TEST-123",
            chat_id=67890,  # Different chat
            notification_date=notification_date,
        )
        
        # Assert
        self.assertFalse(result)
    
    async def test_has_notification_been_sent_different_date(self):
        """Test checking for different date."""
        # Arrange
        alert = self._create_deadline_alert()
        notification_date = datetime.now()
        
        await self.repository.log_notification_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=notification_date,
            alert=alert,
        )
        
        # Act
        result = await self.repository.has_notification_been_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=notification_date + timedelta(days=1),  # Different date
        )
        
        # Assert
        self.assertFalse(result)
    
    async def test_get_notification_history_empty(self):
        """Test getting notification history when empty."""
        # Act
        history = await self.repository.get_notification_history()
        
        # Assert
        self.assertEqual(history, [])
    
    async def test_get_notification_history_with_entries(self):
        """Test getting notification history with entries."""
        # Arrange
        alert1 = self._create_deadline_alert(issue_key="TEST-123")
        alert2 = self._create_deadline_alert(issue_key="TEST-456")
        notification_date = datetime.now()
        
        await self.repository.log_notification_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=notification_date,
            alert=alert1,
        )
        await self.repository.log_notification_sent(
            issue_key="TEST-456",
            chat_id=67890,
            notification_date=notification_date,
            alert=alert2,
        )
        
        # Act
        history = await self.repository.get_notification_history()
        
        # Assert
        self.assertEqual(len(history), 2)
        issue_keys = [entry["issue_key"] for entry in history]
        self.assertIn("TEST-123", issue_keys)
        self.assertIn("TEST-456", issue_keys)
    
    async def test_get_notification_history_filtered_by_issue(self):
        """Test getting notification history filtered by issue key."""
        # Arrange
        alert1 = self._create_deadline_alert(issue_key="TEST-123")
        alert2 = self._create_deadline_alert(issue_key="TEST-456")
        notification_date = datetime.now()
        
        await self.repository.log_notification_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=notification_date,
            alert=alert1,
        )
        await self.repository.log_notification_sent(
            issue_key="TEST-456",
            chat_id=67890,
            notification_date=notification_date,
            alert=alert2,
        )
        
        # Act
        history = await self.repository.get_notification_history(issue_key="TEST-123")
        
        # Assert
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["issue_key"], "TEST-123")
    
    async def test_get_notification_history_filtered_by_chat(self):
        """Test getting notification history filtered by chat ID."""
        # Arrange
        alert1 = self._create_deadline_alert(issue_key="TEST-123")
        alert2 = self._create_deadline_alert(issue_key="TEST-456")
        notification_date = datetime.now()
        
        await self.repository.log_notification_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=notification_date,
            alert=alert1,
        )
        await self.repository.log_notification_sent(
            issue_key="TEST-456",
            chat_id=67890,
            notification_date=notification_date,
            alert=alert2,
        )
        
        # Act
        history = await self.repository.get_notification_history(chat_id=12345)
        
        # Assert
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["chat_id"], 12345)
    
    async def test_get_notification_history_with_cutoff(self):
        """Test getting notification history with date cutoff."""
        # Arrange
        alert = self._create_deadline_alert()
        old_date = datetime.now() - timedelta(days=35)  # Older than 30 days
        recent_date = datetime.now()
        
        # Mock old entry by writing directly to file
        old_entry = {
            "timestamp": old_date.isoformat(),
            "issue_key": "TEST-OLD",
            "chat_id": 12345,
            "notification_date": old_date.date().isoformat(),
            "alert_data": {"summary": "Old issue"},
        }
        
        with open(self.log_file_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(old_entry) + '\n')
        
        # Add recent entry
        await self.repository.log_notification_sent(
            issue_key="TEST-RECENT",
            chat_id=12345,
            notification_date=recent_date,
            alert=alert,
        )
        
        # Act
        history = await self.repository.get_notification_history(days_back=30)
        
        # Assert
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["issue_key"], "TEST-RECENT")
    
    async def test_cleanup_old_logs(self):
        """Test cleaning up old logs."""
        # Arrange
        alert = self._create_deadline_alert()
        old_date = datetime.now() - timedelta(days=100)  # Older than 90 days
        recent_date = datetime.now()
        
        # Mock old entry by writing directly to file
        old_entry = {
            "timestamp": old_date.isoformat(),
            "issue_key": "TEST-OLD",
            "chat_id": 12345,
            "notification_date": old_date.date().isoformat(),
            "alert_data": {"summary": "Old issue"},
        }
        
        with open(self.log_file_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(old_entry) + '\n')
        
        # Add recent entry
        await self.repository.log_notification_sent(
            issue_key="TEST-RECENT",
            chat_id=12345,
            notification_date=recent_date,
            alert=alert,
        )
        
        # Act
        removed_count = await self.repository.cleanup_old_logs(days_to_keep=90)
        
        # Assert
        self.assertEqual(removed_count, 1)
        
        # Verify only recent entry remains
        with open(self.log_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["issue_key"], "TEST-RECENT")
    
    async def test_cleanup_old_logs_no_file(self):
        """Test cleanup when log file doesn't exist."""
        # Arrange
        self.log_file_path.unlink()  # Remove the file
        
        # Act
        removed_count = await self.repository.cleanup_old_logs()
        
        # Assert
        self.assertEqual(removed_count, 0)
    
    async def test_invalid_json_in_log_file(self):
        """Test handling invalid JSON in log file."""
        # Arrange
        with open(self.log_file_path, 'w', encoding='utf-8') as f:
            f.write('invalid json line\n')
            f.write('{"valid": "json"}\n')
        
        # Act
        result = await self.repository.has_notification_been_sent(
            issue_key="TEST-123",
            chat_id=12345,
            notification_date=datetime.now(),
        )
        
        # Assert
        self.assertFalse(result)  # Should handle gracefully
    
    def test_ensure_log_file_exists(self):
        """Test that log file and directory are created."""
        # Arrange
        test_path = Path(self.temp_dir) / "subdir" / "test.jsonl"
        
        # Act
        repo = FileNotificationLogRepository(str(test_path))
        
        # Assert
        self.assertTrue(test_path.exists())
        self.assertTrue(test_path.parent.exists())


if __name__ == "__main__":
    unittest.main()
