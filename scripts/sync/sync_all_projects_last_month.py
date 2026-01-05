"""Script to sync all configured Jira projects from the last month.

This script syncs issues updated in the last 30 days across all configured
projects. It uses the existing upsert mechanism (session.merge) to prevent
duplicates in the database.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import timedelta

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.settings.jira_sync_settings import JiraSyncSettings
from jira_telegram_bot.use_cases.interfaces.jira_data_service_interface import (
    JiraDataServiceInterface,
)
from jira_telegram_bot.use_cases.interfaces.jira_report_repository_interface import (
    JiraReportRepositoryInterface,
)


async def sync_all_projects_last_month():
    """Sync all configured projects for issues updated in the last month.
    
    This function:
    1. Loads all configured project keys from settings
    2. Fetches issues updated in the last 30 days for each project
    3. Stores them using upsert logic (no duplicates created)
    4. Updates sync status for each project
    
    Returns:
        None
        
    Raises:
        Exception: If sync fails for critical reasons
    """
    try:
        LOGGER.info("=" * 80)
        LOGGER.info("Starting multi-project synchronization for last month")
        LOGGER.info("=" * 80)
        
        container = get_container()
        jira_service = container[JiraDataServiceInterface]
        report_repository = container[JiraReportRepositoryInterface]
        settings = JiraSyncSettings()
        
        projects = settings.sync_project_keys
        
        if not projects:
            LOGGER.warning("No projects configured in sync_project_keys")
            return
        
        since_date = datetime.now() - timedelta(days=30)
        LOGGER.info(
            f"Syncing {len(projects)} project(s) for issues updated since: "
            f"{since_date.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        total_synced = 0
        total_failed = 0
        
        for project_key in projects:
            try:
                LOGGER.info("-" * 80)
                LOGGER.info(f"Processing project: {project_key}")
                
                issues = await jira_service.fetch_updated_issues(
                    project_key=project_key,
                    since=since_date
                )
                
                if not issues:
                    LOGGER.info(f"No updated issues found for {project_key}")
                    continue
                
                LOGGER.info(
                    f"Found {len(issues)} updated issue(s) for {project_key}, "
                    f"storing to database..."
                )
                
                await report_repository.store_issues(issues)
                
                total_synced += len(issues)
                
                LOGGER.info(
                    f"✓ Successfully synced {len(issues)} issue(s) for {project_key}"
                )
                
            except Exception as e:
                total_failed += 1
                LOGGER.error(
                    f"✗ Failed to sync project {project_key}: {e}",
                    exc_info=True
                )
        
        LOGGER.info("=" * 80)
        LOGGER.info("Multi-project synchronization completed")
        LOGGER.info(f"Total issues synced: {total_synced}")
        LOGGER.info(f"Projects failed: {total_failed}")
        LOGGER.info("=" * 80)
        
        if total_failed > 0:
            LOGGER.warning(
                f"Sync completed with {total_failed} project failure(s). "
                f"Check logs above for details."
            )
        
    except Exception as e:
        LOGGER.error(f"Critical error in multi-project sync: {e}", exc_info=True)
        raise


def main():
    """Run the synchronization."""
    asyncio.run(sync_all_projects_last_month())


if __name__ == "__main__":
    main()
