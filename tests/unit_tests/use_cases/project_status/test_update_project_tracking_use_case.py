"""Unit tests for UpdateProjectTrackingUseCase."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.user_config_interface import UserConfigInterface
from jira_telegram_bot.use_cases.project_status.update_project_tracking_use_case import UpdateProjectTrackingUseCase


class TestUpdateProjectTrackingUseCase(unittest.IsolatedAsyncioTestCase):
    """Test suite for UpdateProjectTrackingUseCase."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.task_manager_repository = AsyncMock(spec=TaskManagerRepositoryInterface)
        self.user_config = MagicMock(spec=UserConfigInterface)
        self.use_case = UpdateProjectTrackingUseCase(
            task_manager_repository=self.task_manager_repository,
            user_config=self.user_config
        )
    
    async def test_update_tracking_enable(self):
        """Test enabling tracking for a project."""
        # Arrange
        self.task_manager_repository.get_project.return_value = {
            "key": "TEST", 
            "name": "Test Project"
        }
        
        # Act
        result = await self.use_case.update_tracking(
            project_key="TEST",
            track=True,
            notification_channel="123456789"
        )
        
        # Assert
        self.assertEqual(result["project_key"], "TEST")
        self.assertEqual(result["tracking_enabled"], True)
        self.assertEqual(result["notification_channel"], "123456789")
        
        self.task_manager_repository.get_project.assert_called_once_with("TEST")
        self.user_config.set_value.assert_called_once_with(
            "project_tracking.TEST",
            {"tracking_enabled": True, "notification_channel": "123456789"}
        )
        self.user_config.save_config.assert_called_once()
    
    async def test_update_tracking_disable(self):
        """Test disabling tracking for a project."""
        # Arrange
        self.task_manager_repository.get_project.return_value = {
            "key": "TEST", 
            "name": "Test Project"
        }
        
        # Act
        result = await self.use_case.update_tracking(
            project_key="TEST",
            track=False
        )
        
        # Assert
        self.assertEqual(result["project_key"], "TEST")
        self.assertEqual(result["tracking_enabled"], False)
        self.assertIsNone(result["notification_channel"])
        
        self.task_manager_repository.get_project.assert_called_once_with("TEST")
        self.user_config.set_value.assert_called_once_with(
            "project_tracking.TEST",
            {"tracking_enabled": False}
        )
        self.user_config.save_config.assert_called_once()
    
    async def test_update_tracking_project_not_found(self):
        """Test updating tracking for a non-existent project."""
        # Arrange
        self.task_manager_repository.get_project.return_value = None
        
        # Act/Assert
        with self.assertRaises(ValueError) as context:
            await self.use_case.update_tracking(
                project_key="NOTFOUND",
                track=True
            )
        
        self.assertEqual(str(context.exception), "Project NOTFOUND not found")
        self.task_manager_repository.get_project.assert_called_once_with("NOTFOUND")
        self.user_config.set_value.assert_not_called()
        self.user_config.save_config.assert_not_called()
    
    async def test_get_tracking_status_enabled(self):
        """Test getting tracking status when enabled."""
        # Arrange
        self.user_config.get_value.return_value = {
            "tracking_enabled": True,
            "notification_channel": "123456789"
        }
        
        # Act
        result = await self.use_case.get_tracking_status("TEST")
        
        # Assert
        self.assertEqual(result["project_key"], "TEST")
        self.assertEqual(result["tracking_enabled"], True)
        self.assertEqual(result["notification_channel"], "123456789")
        
        self.user_config.get_value.assert_called_once_with(
            "project_tracking.TEST",
            default={"tracking_enabled": False}
        )
    
    async def test_get_tracking_status_disabled(self):
        """Test getting tracking status when disabled."""
        # Arrange
        self.user_config.get_value.return_value = {
            "tracking_enabled": False
        }
        
        # Act
        result = await self.use_case.get_tracking_status("TEST")
        
        # Assert
        self.assertEqual(result["project_key"], "TEST")
        self.assertEqual(result["tracking_enabled"], False)
        self.assertIsNone(result["notification_channel"])
        
        self.user_config.get_value.assert_called_once_with(
            "project_tracking.TEST",
            default={"tracking_enabled": False}
        )
    
    async def test_get_tracking_status_not_configured(self):
        """Test getting tracking status when not configured."""
        # Arrange
        self.user_config.get_value.return_value = {"tracking_enabled": False}
        
        # Act
        result = await self.use_case.get_tracking_status("TEST")
        
        # Assert
        self.assertEqual(result["project_key"], "TEST")
        self.assertEqual(result["tracking_enabled"], False)
        self.assertIsNone(result["notification_channel"])
        
        self.user_config.get_value.assert_called_once_with(
            "project_tracking.TEST",
            default={"tracking_enabled": False}
        )
    
    async def test_get_tracking_status_with_error(self):
        """Test getting tracking status with an error."""
        # Arrange
        self.user_config.get_value.side_effect = Exception("Test error")
        
        # Act
        result = await self.use_case.get_tracking_status("TEST")
        
        # Assert
        self.assertEqual(result["project_key"], "TEST")
        self.assertEqual(result["tracking_enabled"], False)
        self.assertIsNone(result["notification_channel"])
        
        self.user_config.get_value.assert_called_once_with(
            "project_tracking.TEST",
            default={"tracking_enabled": False}
        )
