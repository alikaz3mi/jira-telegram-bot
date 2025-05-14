from __future__ import annotations

from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraServerRepository
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings

# JIRA_SETTINGS = JiraConnectionSettings()


def main():
    # Instantiate your Jira repository (adjust as needed for your environment)
    jira = JiraServerRepository(JIRA_SETTINGS)

    # Search JIRA for story issues in project PARSCHAT
    # Adjust JQL if you want to refine search further
    jql = "project = PARSCHAT AND issuetype = Story"
    issues = jira.jira.search_issues(jql, maxResults=1000)

    for issue in issues:
        # 1. Update labels based on fixVersions
        try:
            fix_versions = [fv.name for fv in issue.fields.fixVersions]
            if fix_versions:
                # Here we simply create a label for each fixVersion like `fixversion_2.0`
                new_labels = {f"{v.replace(' ', '-')}" for v in fix_versions}

                # Merge and update if there are any new labels
                issue.update(fields={"labels": list(new_labels)})
                print(f"Updated labels on {issue.key}: {new_labels}")

        except Exception as label_ex:
            print(f"Failed to update labels for {issue.key}: {label_ex}")


if __name__ == "__main__":
    main()
