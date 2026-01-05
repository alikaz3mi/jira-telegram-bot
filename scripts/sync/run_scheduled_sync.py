#!/usr/bin/env python3
"""Scheduled sync service for Jira data to PostgreSQL.

This script runs continuously, syncing Jira data to PostgreSQL at regular intervals.
Similar pattern to run_scheduled_reports.py.
"""
import asyncio
import signal
from datetime import datetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.settings.jira_sync_settings import JiraSyncSettings
from jira_telegram_bot.use_cases.sync_jira_issue_use_case import SyncJiraIssueUseCase


class ScheduledSyncRunner:
    """Runner for scheduled Jira synchronization service."""

    def __init__(self):
        """Initialize the scheduled sync runner."""
        self._container = get_container()
        self._sync_use_case = self._container[SyncJiraIssueUseCase]
        self._sync_settings = JiraSyncSettings()
        self._running = False
        self._projects = self._sync_settings.sync_project_keys
        self._interval_minutes = self._sync_settings.sync_interval_minutes

    async def start(self) -> None:
        """Start the scheduled sync service."""
        try:
            LOGGER.info(
                f"Starting scheduled Jira sync service "
                f"(every {self._interval_minutes} minutes)"
            )
            self._running = True

            # Setup signal handlers for graceful shutdown
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self.stop())
                )

            # Run sync loop
            await self._sync_loop()

        except Exception as e:
            LOGGER.error(f"Failed to start scheduled sync service: {e}")
            raise

    async def stop(self) -> None:
        """Stop the scheduled sync service."""
        if self._running:
            LOGGER.info("Stopping scheduled Jira sync service...")
            self._running = False
            LOGGER.info("Scheduled sync service stopped")

    async def _sync_loop(self) -> None:
        """Main sync loop."""
        while self._running:
            try:
                sync_start = datetime.now()
                LOGGER.info(f"Starting sync iteration at {sync_start}")

                # Sync all projects
                total_synced = 0
                total_failed = 0

                for project_key in self._projects:
                    LOGGER.info(f"Syncing project: {project_key}")

                    result = await self._sync_use_case.bulk_sync_issues(
                        project_key=project_key,
                        full_sync=self._sync_settings.sync_full_sync
                    )

                    total_synced += result.get('synced', 0)
                    total_failed += result.get('failed', 0)

                    LOGGER.info(
                        f"Project {project_key} sync completed: "
                        f"{result['synced']} synced, {result['failed']} failed"
                    )

                sync_duration = (datetime.now() - sync_start).total_seconds()
                LOGGER.info(
                    f"✅ Sync iteration completed in {sync_duration:.1f}s: "
                    f"{total_synced} synced, {total_failed} failed"
                )

                # Sleep for configured interval
                if self._running:
                    LOGGER.info(f"Sleeping for {self._interval_minutes} minutes...")
                    await asyncio.sleep(self._interval_minutes * 60)

            except asyncio.CancelledError:
                LOGGER.info("Sync loop cancelled")
                break
            except Exception as e:
                LOGGER.error(f"Error in sync iteration: {e}")
                LOGGER.info("Waiting 1 minute before retry...")
                await asyncio.sleep(60)


async def main():
    """Run the scheduled sync service."""
    runner = ScheduledSyncRunner()
    await runner.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER.info("Sync service stopped by user")
    except Exception as e:
        LOGGER.error(f"Sync service failed: {e}")
        raise
