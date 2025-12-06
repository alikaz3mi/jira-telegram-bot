#!/usr/bin/env python3
"""Test script to sync a few PCT issues and check epic extraction."""
import asyncio
from jira_telegram_bot import LOGGER
from jira_telegram_bot.config_dependency_injection import configure_container
from jira_telegram_bot.use_cases.sync_jira_issue_use_case import SyncJiraIssueUseCase

async def test_pct_epic_sync():
    """Test syncing PCT issues with epic links."""
    try:
        LOGGER.info("Testing PCT epic sync...")
        
        container = configure_container()
        sync_use_case = container[SyncJiraIssueUseCase]
        
        # Sync just a few recent PCT issues
        result = await sync_use_case.bulk_sync_issues(
            project_key="PCT",
            full_sync=False
        )
        
        LOGGER.info(f"Sync completed: {result['synced']} synced, {result['failed']} failed")
        
    except Exception as e:
        LOGGER.error(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_pct_epic_sync())
