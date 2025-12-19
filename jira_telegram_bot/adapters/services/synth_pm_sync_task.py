from __future__ import annotations

from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.frameworks.scheduler.ap_scheduler_service import APSchedulerService
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase


class SynthPMSyncTask:
    """Background task for periodic synchronization of features using APScheduler."""

    def __init__(
        self,
        synth_developer_board_use_case: SynthPMUseCase,
        settings: SynthPMSettings,
        scheduler: Optional[APSchedulerService] = None,
    ):
        """Initialize the sync task.

        Args:
            synth_developer_board_use_case: SynthPM use case
            settings: SynthPM settings
            scheduler: Optional APScheduler service (will be created if not provided)
        """
        self.synth_developer_board_use_case = synth_developer_board_use_case
        self.settings = settings
        self.scheduler = scheduler or APSchedulerService()

    async def start(self):
        """Start the background sync task using APScheduler."""
        # Schedule the recurring sync job
        await self.scheduler.schedule_recurring_job(
            job_func=self._execute_sync,
            interval_minutes=self.settings.sync_interval_minutes,
            job_name="synth_pm_developer_board_sync",
        )
        
        LOGGER.info("Starting APScheduler for SynthPM sync task")
        await self.scheduler.start_scheduler()

    async def stop(self):
        """Stop the background sync task."""
        LOGGER.info("Stopping SynthPM sync task...")
        await self.scheduler.stop_scheduler()
        LOGGER.info("Stopped SynthPM sync background task")

    async def _execute_sync(self):
        """Execute a single sync cycle."""
        try:
            LOGGER.debug("Starting SynthPM sync cycle")
            result = (
                await self.synth_developer_board_use_case.sync_developer_board_features()
            )

            if result["status"] == "success":
                LOGGER.info(f"SynthPM sync completed: {result.get('results', {})}")
            else:
                LOGGER.error(f"SynthPM sync failed: {result.get('message')}")

        except Exception as e:
            LOGGER.error(f"Error in SynthPM sync execution: {e}", exc_info=True)

    async def trigger_sync(self) -> dict:
        """Manually trigger a sync operation.

        Returns:
            Sync result
        """
        try:
            LOGGER.info("Manually triggering SynthPM sync")
            result = (
                await self.synth_developer_board_use_case.sync_developer_board_features()
            )
            return result
        except Exception as e:
            error_msg = f"Error in manual sync trigger: {e}"
            LOGGER.error(error_msg)
            return {"status": "error", "message": error_msg}
