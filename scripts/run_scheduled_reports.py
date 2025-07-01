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
        self._running = False

    async def start(self) -> None:
        """Start the scheduled report service."""
        try:
            LOGGER.info("Starting scheduled Jira report service")
            
            # Setup signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # Setup scheduled reports with 30-minute intervals
            await self._scheduled_report_use_case.setup_scheduled_reports(
                interval_minutes=5
            )
            
            # Start the scheduler
            self._running = True
            await self._scheduled_report_use_case.start_scheduler()
            
        except Exception as e:
            LOGGER.error(f"Failed to start scheduled report service: {e}")
            sys.exit(1)

    async def stop(self) -> None:
        """Stop the scheduled report service."""
        if self._running:
            try:
                LOGGER.info("Stopping scheduled Jira report service")
                await self._scheduled_report_use_case.stop_scheduler()
                self._running = False
                LOGGER.info("Scheduled report service stopped")
                
            except Exception as e:
                LOGGER.error(f"Error during shutdown: {e}")

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        LOGGER.info(f"Received signal {signum}, initiating shutdown")
        self._running = False


async def main() -> None:
    """Main entry point for scheduled report service."""
    runner = ScheduledReportRunner()
    
    try:
        await runner.start()
    except KeyboardInterrupt:
        LOGGER.info("Keyboard interrupt received")
    finally:
        await runner.stop()


if __name__ == "__main__":
    asyncio.run(main())
