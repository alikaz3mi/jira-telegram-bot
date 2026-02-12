#!/usr/bin/env python3
"""Debug script to check epic fields in Jira issues."""
from jira_telegram_bot.config_dependency_injection import configure_container
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraServerRepository

def check_epic_issue():
    """Check what an epic issue looks like."""
    container = configure_container()
    jira_repo = container[JiraServerRepository]
    
    print("Fetching MYPROJECT epic...")
    epic_key = "MYPROJECT-3340"
    
    try:
        epic = jira_repo._jira.issue(epic_key)
        print(f"\n{'='*60}")
        print(f"Epic Key: {epic.key}")
        print(f"Epic Summary: {epic.fields.summary}")
        print(f"Epic Type: {epic.fields.issuetype.name}")
        print(f"Epic Status: {epic.fields.status.name}")
    except Exception as e:
        print(f"Error fetching epic: {e}")

if __name__ == "__main__":
    check_epic_issue()
