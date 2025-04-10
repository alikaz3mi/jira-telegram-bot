from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from jira_telegram_bot.adapters.jira_server_repository import JiraRepository
from jira_telegram_bot.settings import JIRA_SETTINGS

jira = JiraRepository(JIRA_SETTINGS)


one_month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
jql = f"updated >= {one_month_ago} ORDER BY updated DESC"
recent_issues = jira.jira.search_issues(jql, maxResults=1000)

all_issues = []
block_size = 100  # You can adjust the block size as needed.
block_num = 0

while True:
    start_idx = block_num * block_size
    issues_block = jira.search_issues(jql, startAt=start_idx, maxResults=block_size)
    all_issues.extend(issues_block)
    print(
        f"Retrieved {len(issues_block)} issues (from {start_idx} to {start_idx + len(issues_block) - 1})",
    )
    if len(issues_block) < block_size:
        break
    block_num += 1
