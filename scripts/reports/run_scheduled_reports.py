"""Main script for scheduled Jira report generation."""
from __future__ import annotations

import asyncio
import signal
import sys

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.scheduled_report_use_case import ScheduledReportUseCase


class ScheduledReportRunner:
    """Runner for scheduled Jira report generation service."""

    def __init__(self) -> None:
        """Initialize the runner."""
        self._container = get_container()
        self._scheduled_report_use_case = self._container[ScheduledReportUseCase]
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the scheduled report service and block until shutdown."""
        try:
            LOGGER.info("Starting scheduled Jira report service")
            
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self._signal_handler)
            
            await self._scheduled_report_use_case.setup_scheduled_reports(
                interval_minutes=30
            )
            
            await self._scheduled_report_use_case.start_scheduler()
            
            await self._shutdown_event.wait()
            
        except Exception as e:
            LOGGER.error(f"Failed to start scheduled report service: {e}")
            sys.exit(1)

    async def stop(self) -> None:
        """Stop the scheduled report service."""
        try:
            LOGGER.info("Stopping scheduled Jira report service")
            await self._scheduled_report_use_case.stop_scheduler()
            LOGGER.info("Scheduled report service stopped")
            
        except Exception as e:
            LOGGER.error(f"Error during shutdown: {e}")

    def _signal_handler(self) -> None:
        """Handle shutdown signals."""
        LOGGER.info("Received shutdown signal, initiating shutdown")
        self._shutdown_event.set()


async def main() -> None:
    """Main entry point for scheduled report service."""
    runner = ScheduledReportRunner()
    
    try:
        await runner.start()
    finally:
        await runner.stop()


if __name__ == "__main__":
    asyncio.run(main())
