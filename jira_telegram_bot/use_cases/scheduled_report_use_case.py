"""Use case for managing scheduled Jira report generation."""
from __future__ import annotations

from typing import List

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.generate_jira_report_use_case import GenerateJiraReportUseCase
from jira_telegram_bot.use_cases.interfaces.scheduler_service_interface import SchedulerServiceInterface


class ScheduledReportUseCase:
    """Use case for managing scheduled Jira report generation."""

    def __init__(
        self,
        report_use_case: GenerateJiraReportUseCase,
        scheduler_service: SchedulerServiceInterface,
        project_keys: List[str],
    ) -> None:
        """Initialize the scheduled report use case.
        
        Args:
            report_use_case: The report generation use case.
            scheduler_service: The scheduler service.
            project_keys: List of project keys to generate reports for.
        """
        self._report_use_case = report_use_case
        self._scheduler_service = scheduler_service
        self._project_keys = project_keys

    async def setup_scheduled_reports(self, interval_minutes: int = 30) -> None:
        """Setup scheduled report generation.
        
        Args:
            interval_minutes: Interval between report generations in minutes.
        """
        await self._scheduler_service.schedule_recurring_job(
            job_func=self._generate_all_reports,
            interval_minutes=interval_minutes,
            job_name="jira_report_generation",
        )
        
        LOGGER.info(
            f"Scheduled Jira report generation every {interval_minutes} minutes "
            f"for projects: {', '.join(self._project_keys)}"
        )

    async def start_scheduler(self) -> None:
        """Start the scheduler service."""
        await self._scheduler_service.start_scheduler()
        LOGGER.info("Scheduler service started")

    async def stop_scheduler(self) -> None:
        """Stop the scheduler service."""
        await self._scheduler_service.stop_scheduler()
        LOGGER.info("Scheduler service stopped")

    async def _generate_all_reports(self) -> None:
        """Generate reports for all configured projects."""
        try:
            LOGGER.info("Starting scheduled report generation")
            reports = await self._report_use_case.generate_multi_project_report(
                self._project_keys
            )
            
            total_issues = sum(report.total_issues for report in reports)
            LOGGER.info(
                f"Completed scheduled report generation: "
                f"{len(reports)} projects, {total_issues} total issues"
            )
            
        except Exception as e:
            LOGGER.error(f"Scheduled report generation failed: {e}")
            raise
