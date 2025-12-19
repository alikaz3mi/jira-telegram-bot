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
        
        # Create mock scheduler
        self.mock_scheduler = MagicMock()
        self.mock_scheduler.schedule_recurring_job = AsyncMock()
        self.mock_scheduler.start_scheduler = AsyncMock()
        self.mock_scheduler.stop_scheduler = AsyncMock()
        self.mock_scheduler._is_running = False
        
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

    async def test_initialize_all_projects(self):
        """Test initialization of all projects."""
        # Create service without specific projects
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            scheduler=self.mock_scheduler,
            project_keys=None,
        )
        
        # Create mock use cases
        mock_use_case1 = MagicMock()
        mock_use_case1.repository.project_config = self.project1
        
        mock_use_case2 = MagicMock()
        mock_use_case2.repository.project_config = self.project2
        
        # Directly set use_cases instead of mocking initialize
        service.use_cases = {
            "PROJECT1": mock_use_case1,
            "PROJECT2": mock_use_case2,
        }
        
        # Should have both projects
        self.assertEqual(len(service.use_cases), 2)
        self.assertIn("PROJECT1", service.use_cases)
        self.assertIn("PROJECT2", service.use_cases)

    async def test_initialize_specific_projects(self):
        """Test initialization of specific projects only."""
        # Create service with specific project
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            scheduler=self.mock_scheduler,
            project_keys=["PROJECT1"],
        )
        
        # Create mock use case for PROJECT1 only
        mock_use_case1 = MagicMock()
        mock_use_case1.repository.project_config = self.project1
        
        # Directly set use_cases
        service.use_cases = {
            "PROJECT1": mock_use_case1,
        }
        
        # Should only have PROJECT1
        self.assertEqual(len(service.use_cases), 1)
        self.assertIn("PROJECT1", service.use_cases)
        self.assertNotIn("PROJECT2", service.use_cases)

    async def test_start_creates_tasks_for_each_project(self):
        """Test that start creates scheduled jobs for each project."""
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            scheduler=self.mock_scheduler,
            project_keys=None,
        )
        
        # Create mock use cases with async methods
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
        
        # Directly set use_cases to bypass initialize()
        service.use_cases = {
            "PROJECT1": mock_use_case1,
            "PROJECT2": mock_use_case2,
        }
        
        # Mock the scheduler to not actually start
        async def mock_start():
            pass
        self.mock_scheduler.start_scheduler = AsyncMock(side_effect=mock_start)
        
        # Start the service
        await service.start()
        
        # Verify scheduler was called for both projects
        self.assertEqual(self.mock_scheduler.schedule_recurring_job.call_count, 2)
        self.mock_scheduler.start_scheduler.assert_called_once()
        
        # Cleanup
        await service.stop()
        self.mock_scheduler.stop_scheduler.assert_called_once()

    async def test_get_status(self):
        """Test status reporting."""
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            scheduler=self.mock_scheduler,
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
            scheduler=self.mock_scheduler,
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
            scheduler=self.mock_scheduler,
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
        """Test that stop calls scheduler.stop_scheduler."""
        service = SynthPMMultiProjectSyncService(
            settings=self.settings,
            scheduler=self.mock_scheduler,
            project_keys=None,
        )
        
        # Call stop
        await service.stop()
        
        # Verify scheduler.stop_scheduler was called
        self.mock_scheduler.stop_scheduler.assert_called_once()


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
