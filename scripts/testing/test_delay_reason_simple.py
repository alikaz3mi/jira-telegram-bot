"""Simple script to test delay_reason extraction from Jira."""
from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraServerRepository


def main():
    """Test delay_reason extraction."""
    try:
        settings = JiraConnectionSettings()
        jira_repo = JiraServerRepository(settings=settings)
        
        # Search for issues with delay_reason set
        LOGGER.info("Searching for MYPROJECT issues with Delay Reason...")
        jql = "project = MYPROJECT AND 'Delay Reason' is not EMPTY ORDER BY updated DESC"
        
        issues = jira_repo.search_for_issues(jql, max_results=10)
        
        if not issues:
            LOGGER.warning("No issues found with Delay Reason set")
            LOGGER.info("Trying any recent MYPROJECT issues...")
            jql = "project = MYPROJECT ORDER BY updated DESC"
            issues = jira_repo.search_for_issues(jql, max_results=10)
        
        LOGGER.info(f"Found {len(issues)} issues")
        
        for issue in issues:
            LOGGER.info(f"\n{'='*80}")
            LOGGER.info(f"Issue: {issue.key}")
            LOGGER.info(f"Summary: {issue.fields.summary}")
            LOGGER.info(f"Status: {issue.fields.status.name}")
            
            # Check delay_reason custom field
            delay_reason_field = getattr(issue.fields, 'customfield_10600', None)
            if delay_reason_field:
                # It's an option field, so get the value attribute
                delay_value = getattr(delay_reason_field, 'value', str(delay_reason_field))
                LOGGER.info(f"✓ Delay Reason: {delay_value}")
            else:
                LOGGER.info("✗ Delay Reason: NOT SET")
        
        LOGGER.info(f"\n{'='*80}")
        LOGGER.info("Test complete!")
        LOGGER.info(f"\nNote: delay_reason is customfield_10600 (type: option)")
        LOGGER.info("The field is now being extracted and will be saved when tasks are synced.")
        
    except Exception as e:
        LOGGER.error(f"Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
