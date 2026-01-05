"""Script to sync delay_reason from Jira to database using dependency injection."""
from __future__ import annotations

import asyncio

from jira_telegram_bot import LOGGER
from jira_telegram_bot.config_dependency_injection import configure_container
from jira_telegram_bot.use_cases.interfaces.jira_data_service_interface import JiraDataServiceInterface
from jira_telegram_bot.use_cases.interfaces.jira_report_repository_interface import JiraReportRepositoryInterface


async def sync_delay_reasons():
    """Sync delay_reason from Jira to database."""
    try:
        LOGGER.info("Starting delay_reason sync from Jira to database")
        
        # Create a minimal container with only what we need (skip full setup_container to avoid SynthPM)
        container = configure_container()
        
        # Get required services from container
        jira_service = container[JiraDataServiceInterface]
        jira_repo = container[JiraReportRepositoryInterface]
        
        # Query database directly to get all task keys
        session = jira_repo.db_connection.get_session()
        try:
            from jira_telegram_bot.adapters.repositories.postgres.jira_report_repository import JiraTaskModel
            tasks = session.query(JiraTaskModel.key).all()
            task_keys = [task[0] for task in tasks]
        finally:
            session.close()
        
        LOGGER.info(f"Found {len(task_keys)} tasks in database to update")
        
        updated_count = 0
        has_delay_reason = 0
        errors = []
        
        for i, task_key in enumerate(task_keys, 1):
            try:
                # Fetch fresh data from Jira
                issue_detail = await jira_service.fetch_issue_details(task_key)
                
                # Update database
                await jira_repo.store_issues([issue_detail])
                
                updated_count += 1
                if issue_detail.delay_reason:
                    has_delay_reason += 1
                    LOGGER.info(f"[{i}/{len(task_keys)}] {task_key}: '{issue_detail.delay_reason}'")
                else:
                    if i % 20 == 0:  # Log every 20th task without delay_reason
                        LOGGER.info(f"[{i}/{len(task_keys)}] {task_key}: (no delay reason)")
                
            except Exception as e:
                error_msg = f"Failed to update {task_key}: {e}"
                LOGGER.warning(error_msg)
                errors.append(error_msg)
        
        LOGGER.info("="*80)
        LOGGER.info(f"Sync complete!")
        LOGGER.info(f"  Total tasks processed: {updated_count}")
        LOGGER.info(f"  Tasks with delay_reason: {has_delay_reason}")
        LOGGER.info(f"  Tasks without delay_reason: {updated_count - has_delay_reason}")
        LOGGER.info(f"  Errors: {len(errors)}")
        
        if errors:
            LOGGER.warning(f"\nErrors encountered:")
            for error in errors[:10]:  # Show first 10 errors
                LOGGER.warning(f"  - {error}")
        
    except Exception as e:
        LOGGER.error(f"Sync failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(sync_delay_reasons())
