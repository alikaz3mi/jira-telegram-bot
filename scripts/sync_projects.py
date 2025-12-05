"""Script to sync Jira projects to PostgreSQL database."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from jira_telegram_bot import LOGGER
from jira_telegram_bot.config_dependency_injection import configure_container
from jira_telegram_bot.settings.jira_sync_settings import JiraSyncSettings
from jira_telegram_bot.use_cases.sync_jira_issue_use_case import SyncJiraIssueUseCase


async def sync_projects():
    """Sync configured Jira projects to PostgreSQL."""
    try:
        LOGGER.info("Starting project synchronization")
        
        # Use base container without Telegram bot setup
        container = configure_container()
        sync_use_case = container[SyncJiraIssueUseCase]
        sync_settings = JiraSyncSettings()
        
        projects = sync_settings.sync_project_keys
        
        for project_key in projects:
            LOGGER.info(f"Syncing project: {project_key}")
            
            result = await sync_use_case.bulk_sync_issues(
                project_key=project_key,
                full_sync=True
            )
            
            LOGGER.info(
                f"Project {project_key} sync completed: "
                f"{result['synced']} issues synced, {result['failed']} failed"
            )
        
        LOGGER.info("All projects synchronized successfully")
        
    except Exception as e:
        LOGGER.error(f"Project synchronization failed: {e}")
        raise


def main():
    """Run the synchronization."""
    asyncio.run(sync_projects())


if __name__ == "__main__":
    main()
