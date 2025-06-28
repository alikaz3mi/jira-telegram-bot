"""Scheduler service interface."""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Callable


class SchedulerServiceInterface(ABC):
    """Interface for scheduling jobs."""

    @abstractmethod
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

    @abstractmethod
    async def start_scheduler(self) -> None:
        """Start the scheduler service."""

    @abstractmethod
    async def stop_scheduler(self) -> None:
        """Stop the scheduler service."""
