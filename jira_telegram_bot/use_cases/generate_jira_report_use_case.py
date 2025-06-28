"""Use case for generating comprehensive Jira reports."""
from __future__ import annotations

from datetime import datetime
from typing import List

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.jira_report import JiraIssueDetail
from jira_telegram_bot.entities.jira_report import ProjectReport
from jira_telegram_bot.use_cases.interfaces.jira_data_service_interface import JiraDataServiceInterface
from jira_telegram_bot.use_cases.interfaces.jira_report_repository_interface import JiraReportRepositoryInterface


class GenerateJiraReportUseCase:
    """Use case for generating and storing comprehensive Jira reports."""

    def __init__(
        self,
        jira_service: JiraDataServiceInterface,
        report_repository: JiraReportRepositoryInterface,
    ) -> None:
        """Initialize the use case with required dependencies.
        
        Args:
            jira_service: Service for fetching Jira data.
            report_repository: Repository for storing report data.
        """
        self._jira_service = jira_service
        self._report_repository = report_repository

    async def generate_project_report(self, project_key: str) -> ProjectReport:
        """Generate a comprehensive report for a Jira project.
        
        Args:
            project_key: The Jira project key to generate report for.
            
        Returns:
            Complete project report with all issues and details.
            
        Raises:
            ValueError: If project_key is empty or invalid.
            RuntimeError: If report generation fails.
        """
        if not project_key or not project_key.strip():
            raise ValueError("Project key cannot be empty")

        try:
            LOGGER.info(f"Generating report for project: {project_key}")
            
            issues = await self._jira_service.fetch_project_issues(project_key)
            
            await self._report_repository.store_issues(issues)
            
            report = ProjectReport(
                project_key=project_key,
                generated_at=datetime.now(),
                total_issues=len(issues),
                issues=issues,
            )
            
            LOGGER.info(
                f"Generated report for {project_key} with {len(issues)} issues"
            )
            
            return report
            
        except Exception as e:
            LOGGER.error(f"Failed to generate report for {project_key}: {e}")
            raise RuntimeError(f"Report generation failed: {e}") from e

    async def generate_multi_project_report(
        self, 
        project_keys: List[str]
    ) -> List[ProjectReport]:
        """Generate reports for multiple projects.
        
        Args:
            project_keys: List of Jira project keys.
            
        Returns:
            List of project reports.
            
        Raises:
            ValueError: If project_keys is empty.
            RuntimeError: If any report generation fails.
        """
        if not project_keys:
            raise ValueError("Project keys list cannot be empty")

        reports = []
        for project_key in project_keys:
            try:
                report = await self.generate_project_report(project_key)
                reports.append(report)
            except Exception as e:
                LOGGER.error(f"Failed to generate report for {project_key}: {e}")
                raise RuntimeError(
                    f"Multi-project report generation failed at {project_key}: {e}"
                ) from e
        
        return reports
