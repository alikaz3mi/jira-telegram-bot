#!/usr/bin/env python3
"""Backfill actual start and end dates for Jira issues.

This script reads actual_start_date and actual_end_date from Jira custom fields
(set by Jira listener) and syncs them to PostgreSQL for all projects.
"""
import asyncio
import os
import sys

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.sync_jira_issue_use_case import (
    SyncJiraIssueUseCase,
)


async def main():
    """Run the backfill for actual dates."""
    # Projects to process - can be overridden from command line
    if len(sys.argv) > 1:
        project_keys = sys.argv[1].split(",")
    else:
        project_keys = os.environ.get(
            "SYNC_PROJECT_KEYS", ""
        ).strip("[]").replace('"', '').split(",") if os.environ.get("SYNC_PROJECT_KEYS") else []
    
    LOGGER.info("=" * 60)
    LOGGER.info("Starting Actual Dates Backfill via Sync")
    LOGGER.info("=" * 60)
    LOGGER.info(f"Projects to process: {', '.join(project_keys)}")
    LOGGER.info("This will sync all issues and read actual dates from Jira")
    LOGGER.info("")
    
    # Get dependencies from container
    container = get_container()
    sync_use_case = container[SyncJiraIssueUseCase]
    
    total_synced = 0
    total_failed = 0
    
    # Process one project at a time
    for project_key in project_keys:
        LOGGER.info(f"\n{'='*60}")
        LOGGER.info(f"Processing project: {project_key}")
        LOGGER.info(f"{'='*60}")
        
        try:
            result = await sync_use_case.bulk_sync_issues(
                project_key=project_key,
                full_sync=True
            )
            total_synced += result.get('synced', 0)
            total_failed += result.get('failed', 0)
            
            LOGGER.info(
                f"✅ {project_key}: {result['synced']} issues synced, "
                f"{result['failed']} failed"
            )
        except Exception as e:
            LOGGER.error(f"❌ Failed to sync {project_key}: {e}")
            total_failed += 1
    
    # Print summary
    LOGGER.info("")
    LOGGER.info("=" * 60)
    LOGGER.info("Backfill Complete")
    LOGGER.info("=" * 60)
    LOGGER.info(f"Total synced: {total_synced}")
    LOGGER.info(f"Total failed: {total_failed}")
    LOGGER.info("=" * 60)
    
    if total_failed > 0:
        LOGGER.warning(
            f"⚠️  {total_failed} issues/projects failed. "
            "Check logs for details."
        )
    else:
        LOGGER.info("✅ All issues synced successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER.info("Backfill cancelled by user")
    except Exception as e:
        LOGGER.error(f"Backfill failed: {e}", exc_info=True)
        raise
