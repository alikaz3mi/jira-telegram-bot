from __future__ import annotations

from datetime import datetime
from datetime import timedelta

import requests

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.jira_server_repository import JiraRepository
from jira_telegram_bot.adapters.user_config import UserConfig
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.settings import TELEGRAM_SETTINGS


def get_effective_deadline(issue):
    """
    Returns a datetime object representing the deadline for an issue:
    1) If issue.fields.duedate is set, use that.
    2) Else if sprint's endDate is available, use that.
    3) Otherwise, return None or some fallback date.
    """
    due_date_str = getattr(issue.fields, "duedate", None)
    if due_date_str:
        return datetime.strptime(
            due_date_str,
            "%Y-%m-%d",
        )

    sprint_field = getattr(issue.fields, "customfield_10104", None)
    if sprint_field:
        for sprint_info in sprint_field:
            sprint_str = str(sprint_info)
            if "endDate=" in sprint_str:
                end_part = sprint_str.split("endDate=")[1].split(",")[0]
                # end_part might look like: "2022-07-05T02:34:00.000Z"
                try:
                    return datetime.strptime(
                        end_part.split(".")[0],
                        "%Y-%m-%dT%H:%M:%S",
                    )
                except Exception as e:
                    LOGGER.error(f"Error parsing sprint end date: {e}")
                    pass
    return None


def categorize_tasks_by_deadline(issues):
    """
    Group tasks by their date (YYYY-MM-DD). Returns dict: date_str -> list of issues
    """
    tasks_by_date = {}
    for issue in issues:
        deadline = get_effective_deadline(issue)
        if not deadline:
            date_str = "بدون مهلت"  # or "No Deadline"
        else:
            date_str = deadline.strftime("%Y-%m-%d")
        tasks_by_date.setdefault(date_str, []).append(issue)
    return tasks_by_date


def build_message(tasks_by_date):
    """
    Creates a single text message grouping tasks by date, each with hyperlink.
    """
    lines = []
    # Sort by date where possible (place "بدون مهلت" last)
    sorted_dates = sorted(d for d in tasks_by_date.keys() if d != "بدون مهلت")
    if "بدون مهلت" in tasks_by_date:
        sorted_dates.append("بدون مهلت")

    for date_str in sorted_dates:
        lines.append(f"**مهلت: {date_str}**")
        for issue in tasks_by_date[date_str]:
            key = issue.key
            summary = issue.fields.summary
            link = f"{JIRA_SETTINGS.domain}/browse/{key}"
            # In Markdown or HTML
            lines.append(f"- [{key}]({link}): {summary}")
        lines.append("")  # blank line
    return "\n".join(lines)


def send_telegram_message(chat_id: int, text: str):
    """
    Send a message to a single user via Telegram using bot token.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_SETTINGS.TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        LOGGER.error(f"Error sending Telegram message: {e}")


def main():
    jira_repo = JiraRepository(settings=JIRA_SETTINGS)
    user_config = UserConfig()

    threshold_date = datetime.now() + timedelta(days=3)

    all_users = user_config.list_all_users()
    for username in all_users:
        cfg = user_config.get_user_config(username)
        if not cfg or not cfg.jira_username or not cfg.telegram_user_chat_id:
            continue

        jql = f'assignee="{cfg.jira_username}" AND statusCategory != Done order by duedate ASC'
        issues = jira_repo.jira.search_issues(jql, maxResults=200)

        due_soon = []
        for issue in issues:
            eff_deadline = get_effective_deadline(issue)
            if eff_deadline is None or eff_deadline <= threshold_date:
                due_soon.append(issue)
            elif eff_deadline is None:
                due_soon.append(issue)

        if not due_soon:
            continue

        tasks_by_date = categorize_tasks_by_deadline(due_soon)
        message_text = build_message(tasks_by_date)

        send_telegram_message(cfg.telegram_user_chat_id, message_text)

        LOGGER.info(f"Sent deadline reminder to {username} for {len(due_soon)} tasks.")


if __name__ == "__main__":
    main()
