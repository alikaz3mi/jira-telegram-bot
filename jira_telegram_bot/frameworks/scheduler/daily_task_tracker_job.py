"""Scheduler job for daily task tracking using APSchedulerService."""
from __future__ import annotations

import asyncio
from datetime import datetime

from jira_telegram_bot import LOGGER
from jira_telegram_bot.frameworks.scheduler.ap_scheduler_service import (
    APSchedulerService,
)
from jira_telegram_bot.settings.daily_task_tracker_settings import (
    DailyTaskTrackerSettings,
)
from jira_telegram_bot.use_cases.daily_task_tracking.send_daily_task_reminders_use_case import (
    SendDailyTaskRemindersUseCase,
)


class DailyTaskTrackerJob:
    """Job for running daily task tracking on a schedule."""

    def __init__(
        self,
        send_daily_task_reminders_use_case: SendDailyTaskRemindersUseCase,
        settings: DailyTaskTrackerSettings,
        scheduler_service: APSchedulerService,
    ):
        """Initialize the job.

        Args:
            send_daily_task_reminders_use_case: Use case for sending reminders
            settings: Daily task tracker settings
            scheduler_service: Scheduler service
        """
        self.send_reminders = send_daily_task_reminders_use_case
        self.settings = settings
        self.scheduler = scheduler_service
        self.running = False

    async def start(self) -> None:
        """Start the scheduled job."""
        if not self.settings.ENABLED:
            LOGGER.info("Daily task tracker is disabled")
            return
        
        LOGGER.info(
            f"Starting daily task tracker with schedule: {self.settings.CRON_SCHEDULE}"
        )
        
        self.running = True
        
        try:
            await self.scheduler.schedule_cron_job(
                job_func=self._run_daily_check,
                cron_expression=self.settings.CRON_SCHEDULE,
                job_name="daily_task_tracker",
                timezone=self.settings.TIMEZONE,
            )
            
            await self.scheduler.start_scheduler()
            
            LOGGER.info("Daily task tracker scheduler started successfully")
            
            while self.running:
                await asyncio.sleep(60)
                
        except Exception as e:
            LOGGER.error(f"Error in daily task tracker job: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the scheduled job."""
        LOGGER.info("Stopping daily task tracker")
        self.running = False
        
        try:
            await self.scheduler.shutdown_scheduler()
        except Exception as e:
            LOGGER.error(f"Error stopping scheduler: {e}")

    async def _run_daily_check(self) -> None:
        """Run the daily task check."""
        try:
            if self._should_skip_today():
                LOGGER.info("Skipping daily check (weekend/holiday)")
                return
            
            LOGGER.info("Running daily task check")
            
            stats = await self.send_reminders.execute()
            
            LOGGER.info(f"Daily task check complete: {stats}")
            
        except Exception as e:
            LOGGER.error(f"Error running daily check: {e}")

    def _should_skip_today(self) -> bool:
        """Check if today should be skipped.

        Returns:
            True if today is a weekend or holiday and should be skipped
        """
        today = datetime.now()
        
        if self.settings.EXCLUDE_WEEKENDS:
            if today.weekday() >= 5:
                return True
        
        return False

    async def run_once(self) -> None:
        """Run the daily check once (for testing)."""
        LOGGER.info("Running daily task check once")
        await self._run_daily_check()
