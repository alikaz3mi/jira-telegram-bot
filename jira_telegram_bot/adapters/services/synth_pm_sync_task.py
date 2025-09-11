from __future__ import annotations

import asyncio
import contextlib

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.synth_pm import SynthPMUseCase


class SynthPMSyncTask:
    """Background task for periodic synchronization of features."""

    def __init__(
        self,
        synth_developer_board_use_case: SynthPMUseCase,
        settings: SynthPMSettings,
    ):
        """Initialize the sync task.

        Args:
            synth_developer_board_use_case: SynthPM use case
            settings: SynthPM settings
        """
        self.synth_developer_board_use_case = synth_developer_board_use_case
        self.settings = settings
        self.running = False
        self.task: asyncio.Task = None

    async def start(self):
        """Start the background sync task."""
        if self.running:
            LOGGER.warning("SynthPM sync task is already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._sync_loop())
        LOGGER.info("Started SynthPM sync background task")

    async def stop(self):
        """Stop the background sync task."""
        if not self.running:
            return

        self.running = False
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task

        LOGGER.info("Stopped SynthPM sync background task")

    async def _sync_loop(self):
        """Main sync loop that runs periodically."""
        while self.running:
            try:
                LOGGER.debug("Starting SynthPM sync cycle")
                result = (
                    await self.synth_developer_board_use_case.sync_developer_board_features()
                )

                if result["status"] == "success":
                    LOGGER.info(f"SynthPM sync completed: {result.get('results', {})}")
                else:
                    LOGGER.error(f"SynthPM sync failed: {result.get('message')}")

                # Wait for the next sync interval
                await asyncio.sleep(self.settings.sync_interval_minutes * 60)

            except asyncio.CancelledError:
                LOGGER.info("SynthPM sync task cancelled")
                break
            except Exception as e:
                LOGGER.error(f"Error in SynthPM sync loop: {e}", exc_info=True)
                # Wait a bit before retrying to avoid rapid error loops
                await asyncio.sleep(60)

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
