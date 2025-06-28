"""One-time execution script for Jira report generation."""
from __future__ import annotations

import asyncio

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.generate_jira_report_use_case import GenerateJiraReportUseCase


async def main() -> None:
    """Generate reports for all configured projects once."""
    try:
        LOGGER.info("Starting one-time Jira report generation")
        
        container = get_container()
        report_use_case = container[GenerateJiraReportUseCase]
        
        # Configure project keys as needed
        project_keys = ["PARSCHAT", "PCT"]
        
        reports = await report_use_case.generate_multi_project_report(project_keys)
        
        total_issues = sum(report.total_issues for report in reports)
        LOGGER.info(
            f"Completed report generation: "
            f"{len(reports)} projects, {total_issues} total issues"
        )
        
        for report in reports:
            LOGGER.info(
                f"Project {report.project_key}: {report.total_issues} issues"
            )
        
    except Exception as e:
        LOGGER.error(f"Report generation failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
