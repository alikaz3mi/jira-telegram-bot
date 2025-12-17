"""Unit tests for SynthPM multi-project sync service."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

from jira_telegram_bot.adapters.services.synth_pm_multi_project_sync import (
    SynthPMMultiProjectSyncService,
)
from jira_telegram_bot.entities.synth_pm.project_config import (
    BoardConfig,
    ProjectBoardsConfig,
    ProjectConfig,
    SynthPMMultiProjectConfig,
    SyncSettings,
    TelegramConfig,
)
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings


class TestMultiProjectSyncService(unittest.TestCase):
    """Test multi-project sync service."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock settings
        self.settings = Mock(spec=SynthPMSettings)
        
        # Create test projects
        self.project1 = ProjectConfig(
            project_key="PROJECT1",
            spreadsheet_id="sheet1",
            boards=ProjectBoardsConfig(
                developer_board=BoardConfig(
                    jira_board_key="PROJ1",
                    sheet_name="Sheet1",
                    data_range="A2:AY",
                    enabled=True,
                ),
            ),
            telegram=TelegramConfig(
                bot_token_env="BOT1",
                channel_id_env="CHANNEL1",
                group_id_env="GROUP1",
            ),
            sync_settings=SyncSettings(
                sync_interval_minutes=5,
            ),
        )
        
        self.project2 = ProjectConfig(
            project_key="PROJECT2",
            spreadsheet_id="sheet2",
            boards=ProjectBoardsConfig(
                developer_board=BoardConfig(
                    jira_board_key="PROJ2",
                    sheet_name="Sheet2",
                    data_range="A2:AY",
                    enabled=True,
                ),
            ),
            telegram=TelegramConfig(
                bot_token_env="BOT2",
                channel_id_env="CHANNEL2",
                group_id_env="GROUP2",
            ),
            sync_settings=SyncSettings(
                sync_interval_minutes=10,
            ),
        )
        
        self.multi_config = SynthPMMultiProjectConfig(
            projects=[self.project1, self.project2],
        )
        
        self.settings.load_multi_project_config.return_value = self.multi_config

    @patch('jira_telegram_bot.adapters.services.synth_pm_multi_project_sync.get_container')
    async def test_initialize_all_projects(self, mock_get_container):
        """Test initialization of all projects."""
        # Create service without specific projects
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            project_keys=None,
        )
        
        # Mock container
        container = MagicMock()
        mock_get_container.return_value = container
        
        # Mock repository and use case creation
        with patch('jira_telegram_bot.adapters.services.synth_pm_multi_project_sync.SynthPMRepository'):
            with patch('jira_telegram_bot.adapters.services.synth_pm_multi_project_sync.SynthPMUseCase'):
                await service.initialize()
        
        # Should initialize both projects
        self.assertEqual(len(service.use_cases), 2)
        self.assertIn("PROJECT1", service.use_cases)
        self.assertIn("PROJECT2", service.use_cases)

    @patch('jira_telegram_bot.adapters.services.synth_pm_multi_project_sync.get_container')
    async def test_initialize_specific_projects(self, mock_get_container):
        """Test initialization of specific projects only."""
        # Create service with specific project
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            project_keys=["PROJECT1"],
        )
        
        container = MagicMock()
        mock_get_container.return_value = container
        
        with patch('jira_telegram_bot.adapters.services.synth_pm_multi_project_sync.SynthPMRepository'):
            with patch('jira_telegram_bot.adapters.services.synth_pm_multi_project_sync.SynthPMUseCase'):
                await service.initialize()
        
        # Should only initialize PROJECT1
        self.assertEqual(len(service.use_cases), 1)
        self.assertIn("PROJECT1", service.use_cases)
        self.assertNotIn("PROJECT2", service.use_cases)

    @patch('jira_telegram_bot.adapters.services.synth_pm_multi_project_sync.get_container')
    async def test_start_creates_tasks_for_each_project(self, mock_get_container):
        """Test that start creates sync tasks for each project."""
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            project_keys=None,
        )
        
        container = MagicMock()
        mock_get_container.return_value = container
        
        # Create mock use cases
        mock_use_case1 = MagicMock()
        mock_use_case1.repository.project_config = self.project1
        mock_use_case1.sync_developer_board_features = AsyncMock(
            return_value={"status": "success", "results": {}}
        )
        
        mock_use_case2 = MagicMock()
        mock_use_case2.repository.project_config = self.project2
        mock_use_case2.sync_developer_board_features = AsyncMock(
            return_value={"status": "success", "results": {}}
        )
        
        with patch('jira_telegram_bot.adapters.services.synth_pm_multi_project_sync.SynthPMRepository'):
            with patch('jira_telegram_bot.adapters.services.synth_pm_multi_project_sync.SynthPMUseCase') as mock_uc:
                mock_uc.side_effect = [mock_use_case1, mock_use_case2]
                
                await service.initialize()
                await service.start()
        
        # Should have tasks for both projects
        self.assertEqual(len(service.tasks), 2)
        self.assertIn("PROJECT1", service.tasks)
        self.assertIn("PROJECT2", service.tasks)
        self.assertTrue(service.running)
        
        # Cleanup
        await service.stop()

    async def test_get_status(self):
        """Test status reporting."""
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            project_keys=None,
        )
        
        # Mock use cases
        mock_use_case1 = MagicMock()
        mock_use_case1.repository.project_config = self.project1
        
        mock_use_case2 = MagicMock()
        mock_use_case2.repository.project_config = self.project2
        
        service.use_cases = {
            "PROJECT1": mock_use_case1,
            "PROJECT2": mock_use_case2,
        }
        
        status = service.get_status()
        
        self.assertFalse(status["running"])
        self.assertEqual(len(status["projects"]), 2)
        self.assertIn("PROJECT1", status["projects"])
        self.assertIn("PROJECT2", status["projects"])
        self.assertEqual(status["projects"]["PROJECT1"]["sync_interval_minutes"], 5)
        self.assertEqual(status["projects"]["PROJECT2"]["sync_interval_minutes"], 10)

    @patch('jira_telegram_bot.adapters.services.synth_pm_multi_project_sync.get_container')
    async def test_trigger_sync_specific_project(self, mock_get_container):
        """Test manual sync trigger for specific project."""
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            project_keys=None,
        )
        
        # Create mock use cases
        mock_use_case1 = MagicMock()
        mock_use_case1.repository.project_config = self.project1
        mock_use_case1.sync_developer_board_features = AsyncMock(
            return_value={"status": "success", "results": {"created": 5}}
        )
        
        service.use_cases = {"PROJECT1": mock_use_case1}
        
        # Trigger sync for PROJECT1
        results = await service.trigger_sync("PROJECT1")
        
        self.assertIn("PROJECT1", results)
        self.assertEqual(results["PROJECT1"]["status"], "success")
        mock_use_case1.sync_developer_board_features.assert_called_once()

    @patch('jira_telegram_bot.adapters.services.synth_pm_multi_project_sync.get_container')
    async def test_trigger_sync_all_projects(self, mock_get_container):
        """Test manual sync trigger for all projects."""
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            project_keys=None,
        )
        
        # Create mock use cases
        mock_use_case1 = MagicMock()
        mock_use_case1.sync_developer_board_features = AsyncMock(
            return_value={"status": "success"}
        )
        
        mock_use_case2 = MagicMock()
        mock_use_case2.sync_developer_board_features = AsyncMock(
            return_value={"status": "success"}
        )
        
        service.use_cases = {
            "PROJECT1": mock_use_case1,
            "PROJECT2": mock_use_case2,
        }
        
        # Trigger sync for all
        results = await service.trigger_sync(None)
        
        self.assertEqual(len(results), 2)
        self.assertIn("PROJECT1", results)
        self.assertIn("PROJECT2", results)
        mock_use_case1.sync_developer_board_features.assert_called_once()
        mock_use_case2.sync_developer_board_features.assert_called_once()

    async def test_stop_cancels_all_tasks(self):
        """Test that stop cancels all running tasks."""
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            project_keys=None,
        )
        
        # Create mock tasks
        task1 = MagicMock()
        task1.cancel = MagicMock()
        task1.done.return_value = False
        
        task2 = MagicMock()
        task2.cancel = MagicMock()
        task2.done.return_value = False
        
        service.tasks = {
            "PROJECT1": task1,
            "PROJECT2": task2,
        }
        service.running = True
        
        await service.stop()
        
        self.assertFalse(service.running)
        task1.cancel.assert_called_once()
        task2.cancel.assert_called_once()
        self.assertEqual(len(service.tasks), 0)


def async_test(coro):
    """Decorator to run async tests."""
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper


# Apply async decorator to all test methods
for name in dir(TestMultiProjectSyncService):
    if name.startswith('test_'):
        method = getattr(TestMultiProjectSyncService, name)
        if asyncio.iscoroutinefunction(method):
            setattr(TestMultiProjectSyncService, name, async_test(method))


if __name__ == "__main__":
    unittest.main()
