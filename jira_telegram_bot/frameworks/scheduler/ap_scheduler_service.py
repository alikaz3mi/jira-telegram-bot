"""APScheduler implementation of scheduler service."""
from __future__ import annotations

import asyncio
from typing import Callable

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.scheduler_service_interface import SchedulerServiceInterface


class APSchedulerService(SchedulerServiceInterface):
    """APScheduler-based implementation of scheduler service."""

    def __init__(self) -> None:
        """Initialize the scheduler service."""
        # Configure executors to allow concurrent job execution
        executors = {
            'default': AsyncIOExecutor()
        }
        # Configure job defaults to allow multiple instances
        job_defaults = {
            'coalesce': False,  # Don't combine missed executions
            'max_instances': 10,  # Allow up to 10 concurrent instances per job
            'misfire_grace_time': 300  # Allow 5 minutes grace for missed jobs
        }
        self._scheduler = AsyncIOScheduler(
            executors=executors,
            job_defaults=job_defaults
        )
        self._is_running = False

    async def schedule_recurring_job(
        self,
        job_func: Callable,
        interval_minutes: int,
        job_name: str,
    ) -> None:
        """Schedule a recurring job.
        
        Args:
            job_func: The function to execute.
            interval_minutes: Interval between executions in minutes.
            job_name: Unique name for the job.
        """
        try:
            self._scheduler.add_job(
                job_func,
                'interval',
                minutes=interval_minutes,
                id=job_name,
                replace_existing=True,
            )
            
            LOGGER.info(
                f"Scheduled job '{job_name}' to run every {interval_minutes} minutes"
            )
            
        except Exception as e:
            LOGGER.error(f"Failed to schedule job '{job_name}': {e}")
            raise

    async def schedule_daily_job(
        self,
        job_func: Callable,
        hour: int,
        minute: int,
        job_name: str,
    ) -> None:
        """Schedule a daily job using cron trigger.
        
        Args:
            job_func: The function to execute.
            hour: Hour to run (0-23).
            minute: Minute to run (0-59).
            job_name: Unique name for the job.
        """
        try:
            self._scheduler.add_job(
                job_func,
                'cron',
                hour=hour,
                minute=minute,
                id=job_name,
                replace_existing=True,
            )
            
            LOGGER.info(
                f"Scheduled daily job '{job_name}' to run at {hour:02d}:{minute:02d}"
            )
            
        except Exception as e:
            LOGGER.error(f"Failed to schedule daily job '{job_name}': {e}")
            raise

    async def start_scheduler(self) -> None:
        """Start the scheduler service."""
        if not self._is_running:
            try:
                self._scheduler.start()
                self._is_running = True
                LOGGER.info("Scheduler service started successfully")
                    
            except Exception as e:
                LOGGER.error(f"Failed to start scheduler: {e}")
                raise

    async def stop_scheduler(self) -> None:
        """Stop the scheduler service."""
        if self._is_running:
            try:
                self._scheduler.shutdown()
                self._is_running = False
                LOGGER.info("Scheduler service stopped successfully")
                
            except Exception as e:
                LOGGER.error(f"Failed to stop scheduler: {e}")
                raise
