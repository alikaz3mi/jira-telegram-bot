from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraRepository
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import JIRA_SETTINGS


def batch_task_creation(
    jira_repository: JiraRepository,
    task_data: list,
):
    """
    Create multiple tasks in Jira using the provided task data.

    :param jira_repository: An instance of JiraServerRepository to interact with Jira.
    :param task_data: A list of dictionaries containing task data.
    """
    for task in task_data:
        issue = jira_repository.create_task(TaskData(**task))
        LOGGER.debug(f"Created issue: {issue.key}")


if __name__ == "__main__":
    # Example usage
    jira_repository = JiraRepository(JIRA_SETTINGS)
    tasks = [
        {
            "summary": "بازطراحی دیالوگ‌های تأیید (مانند حذف ربات)",
            "description": "طراحی جدید برای پنجره‌های پاپ‌آپ تأیید عملیات با تأکید بر وضوح پیام، هماهنگی رنگ و ابعاد، و بهبود تجربه کاربری برای عملیات حساس نظیر حذف ربات.",
        },
        {
            "summary": "بازطراحی صفحه اشتراک‌ها",
            "description": "بازنگری UI/UX صفحه پلن‌های اشتراک با افزودن لینک ویدیو معرفی، برجسته‌سازی گزینه پشتیبانی رایگان و اضافه کردن بخشی برای نمایش تعداد صفحات PDF و لینک به اطلاعات حساب کاربری.",
        },
    ]

    tasks = [
        {
            **task,
            "assignee": "xx",
            "project_key": "PARxxCHAT",
            "component": "UI / UX",
            "task_type": "Task",
        }
        for task in tasks
    ]
    batch_task_creation(jira_repository, tasks)
