"""Script to update epic links for specific MYPROJECT tasks.

This script updates the epic links of tasks that are linked to specific epics,
changing them to new epic values according to the mapping defined.
"""
from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import (
    JiraServerRepository,
)
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings


EPIC_MAPPING = {
    "A": "B"
}

JQL_QUERY = (
    ''
)


def update_epic_links():
    """Update epic links for tasks based on the mapping."""
    settings = JiraConnectionSettings()
    jira_repo = JiraServerRepository(settings=settings)
    
    LOGGER.info(f"Searching for issues with JQL: {JQL_QUERY}")
    issues = jira_repo.jira.search_issues(JQL_QUERY, maxResults=1000)
    
    LOGGER.info(f"Found {len(issues)} issues to process")
    
    updated_count = 0
    skipped_count = 0
    
    for issue in issues:
        issue_key = issue.key
        current_epic_link = getattr(issue.fields, jira_repo.jira_epic_link_id, None)
        
        if not current_epic_link:
            LOGGER.warning(f"Issue {issue_key} has no epic link, skipping")
            skipped_count += 1
            continue
        
        current_epic = jira_repo.jira.issue(current_epic_link)
        current_epic_name = getattr(
            current_epic.fields,
            jira_repo.jira_epic_name_id,
            None,
        )
        
        if not current_epic_name:
            LOGGER.warning(
                f"Issue {issue_key} epic {current_epic_link} has no name, skipping",
            )
            skipped_count += 1
            continue
        
        new_epic_name = None
        for old_name, new_name in EPIC_MAPPING.items():
            if old_name in current_epic_name:
                new_epic_name = new_name
                break
        
        if not new_epic_name:
            LOGGER.info(
                f"Issue {issue_key} epic '{current_epic_name}' "
                f"not in mapping, skipping",
            )
            skipped_count += 1
            continue
        
        epics = jira_repo.jira.search_issues(
            f'project = MYPROJECT AND issuetype = Epic AND '
            f'summary ~ "{new_epic_name}"',
            maxResults=10,
        )
        
        target_epic = None
        for epic in epics:
            epic_name = getattr(epic.fields, jira_repo.jira_epic_name_id, None)
            if epic_name and new_epic_name in epic_name:
                target_epic = epic.key
                break
        
        if not target_epic:
            LOGGER.error(f"Could not find epic with name '{new_epic_name}'")
            skipped_count += 1
            continue
        
        try:
            fields = {jira_repo.jira_epic_link_id: target_epic}
            jira_repo.update_issue_from_fields(issue_key, fields)
            LOGGER.info(
                f"Updated {issue_key}: '{current_epic_name}' -> '{new_epic_name}' "
                f"({current_epic_link} -> {target_epic})",
            )
            updated_count += 1
        except Exception as e:
            LOGGER.error(f"Failed to update {issue_key}: {e}")
            skipped_count += 1
    
    LOGGER.info(
        f"Update complete: {updated_count} updated, {skipped_count} skipped",
    )


if __name__ == "__main__":
    update_epic_links()
