from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraServerRepository
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings

JIRA_SETTINGS = JiraConnectionSettings()

jira = JiraServerRepository(JIRA_SETTINGS)

# issue = jira.jira.issue('AK-32')

# # Time spent in seconds
# issue.fields.worklog.worklogs[0].timeSpentSeconds

# # Original estimate in seconds
# issue.fields.timetracking.originalEstimateSeconds

# # Remaining estimate in seconds
# issue.fields.timetracking.remainingEstimateSeconds

# # story points
# issue.fields.customfield_10106

# # update duedate of an issue
# issue.update(duedate='2022-01-01')

# # set time trackings for an issue
# issue.update(timetracking={'originalEstimate': '3d', 'remainingEstimate': '2d'})
if __name__ == "__main__":

    issues = jira.jira.search_issues("project = AK", maxResults=1000)

    for issue in issues:
        try:
            if issue.fields.customfield_10106:
                spent_time = (
                    sum(
                        [
                            worklog.timeSpentSeconds
                            for worklog in issue.fields.worklog.worklogs
                        ],
                    )
                    / 3600
                )
                # if task is done or in review, set remaining time to 0
                if issue.fields.status.name in ["Done", "Review"]:
                    issue.update(
                        timetracking={
                            "originalEstimate": f"{int(issue.fields.customfield_10106 * 8)}h",
                            "remainingEstimate": "0h",
                        },
                    )
                else:
                    remaining_time = (
                        int(issue.fields.customfield_10106 * 8 - spent_time)
                        if int(issue.fields.customfield_10106 * 8 - spent_time) > 0
                        else 0
                    )
                    issue.update(
                        timetracking={
                            "originalEstimate": f"{int(issue.fields.customfield_10106 * 8)}h",
                            "remainingEstimate": f"{remaining_time}h",
                        },
                    )
        except Exception as e:
            LOGGER.error(f"{issue.key} failed: {e}")
