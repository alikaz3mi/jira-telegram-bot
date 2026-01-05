"""Script to test delay_reason extraction from Jira and saving to database."""
from __future__ import annotations

import asyncio
from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.jira_data_service_interface import JiraDataServiceInterface
from jira_telegram_bot.use_cases.interfaces.jira_report_repository_interface import JiraReportRepositoryInterface


async def test_delay_reason_extraction():
    """Test extracting delay_reason from Jira and saving to database."""
    try:
        container = get_container()
        jira_service = container[JiraDataServiceInterface]
        jira_repo = container[JiraReportRepositoryInterface]
        
        # Find some PARSCHAT issues to test
        LOGGER.info("Searching for PARSCHAT issues with delay_reason...")
        jql = "project = PARSCHAT AND 'Delay Reason' is not EMPTY ORDER BY updated DESC"
        
        issues = jira_service._jira_repository.search_for_issues(jql, max_results=5)
        
        if not issues:
            LOGGER.warning("No issues found with delay_reason field set")
            LOGGER.info("Trying to fetch any recent PARSCHAT issues...")
            jql = "project = PARSCHAT ORDER BY updated DESC"
            issues = jira_service._jira_repository.search_for_issues(jql, max_results=5)
        
        LOGGER.info(f"Found {len(issues)} issues to test")
        
        for issue in issues:
            LOGGER.info(f"\n{'='*80}")
            LOGGER.info(f"Processing: {issue.key}")
            LOGGER.info(f"Summary: {issue.fields.summary}")
            
            # Check if delay_reason exists in the raw issue
            delay_reason_raw = getattr(issue.fields, 'customfield_10600', None)
            if delay_reason_raw:
                delay_value = getattr(delay_reason_raw, 'value', str(delay_reason_raw))
                LOGGER.info(f"Delay Reason (raw): {delay_value}")
            else:
                LOGGER.info("Delay Reason (raw): NOT SET")
            
            # Fetch detailed issue through service
            issue_detail = await jira_service.fetch_issue_details(issue.key)
            LOGGER.info(f"Delay Reason (extracted): {issue_detail.delay_reason}")
            
            # Save to database
            await jira_repo.upsert_issue(issue_detail)
            LOGGER.info(f"✓ Saved {issue.key} to database")
        
        LOGGER.info(f"\n{'='*80}")
        LOGGER.info("Testing complete! Checking database...")
        
        # Verify in database
        for issue in issues:
            retrieved = await jira_repo.get_issue(issue.key)
            if retrieved:
                LOGGER.info(f"{retrieved.key}: delay_reason = '{retrieved.delay_reason}'")
        
    except Exception as e:
        LOGGER.error(f"Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(test_delay_reason_extraction())
