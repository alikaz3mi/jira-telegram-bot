#!/usr/bin/env python3
"""Show details of pre-existing (older) duplicate issues for user review."""
import os
import logging
import logging.handlers

os.makedirs("/tmp/jira_cleanup_logs", exist_ok=True)
_orig_init = logging.handlers.RotatingFileHandler.__init__


def _patched_init(self, filename, *args, **kwargs):
    if "logs/logs.log" in str(filename):
        filename = "/tmp/jira_cleanup_logs/logs.log"
    _orig_init(self, filename, *args, **kwargs)


logging.handlers.RotatingFileHandler.__init__ = _patched_init

from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)

container = get_container()
jira_repo = container[TaskManagerRepositoryInterface]

old_story_dups = {
    "فروشنده اول: آیلا مارکت": {
        "original": "PARSCHAT-3452",
        "dups": ["PARSCHAT-3874"],
    },
    "بهبود فیلترهای صفحه تاریخچه": {
        "original": "PARSCHAT-3498",
        "dups": ["PARSCHAT-3663", "PARSCHAT-3813"],
    },
    "گزارش های آماری": {
        "original": "PARSCHAT-3958",
        "dups": ["PARSCHAT-4375"],
    },
    "پیکربندی اکشن پیگیری سفارش": {
        "original": "PARSCHAT-4927",
        "dups": ["PARSCHAT-5003"],
    },
}

print("=" * 80)
print("OLD DUPLICATE STORIES (pre-existing, NOT from broken sync)")
print("=" * 80)

for name, info in old_story_dups.items():
    print(f"\n--- {name} ---")
    orig_key = info["original"]
    issue = jira_repo.get_issue(orig_key)
    if issue:
        print(
            f"  Original {orig_key}: "
            f"status={issue.fields.status.name}, "
            f"created={issue.fields.created[:10]}"
        )
        subs = jira_repo.get_issue_subtasks(orig_key)
        print(f"    Subtasks ({len(subs)}): {[s.key for s in subs]}")

    for dk in info["dups"]:
        issue = jira_repo.get_issue(dk)
        if issue:
            print(
                f"  Dup {dk}: "
                f"status={issue.fields.status.name}, "
                f"created={issue.fields.created[:10]}"
            )
            subs = jira_repo.get_issue_subtasks(dk)
            print(f"    Subtasks ({len(subs)}): {[s.key for s in subs]}")

old_epic_dups = {
    "تنظیمات ربات": {
        "original": "PARSCHAT-282",
        "suspect": "PARSCHAT-3297",
    },
    "آموزش ربات": {
        "original": "PARSCHAT-2065",
        "suspect": "PARSCHAT-2356",
    },
}

print("\n" + "=" * 80)
print("OLD DUPLICATE EPICS (pre-existing)")
print("=" * 80)

for name, info in old_epic_dups.items():
    print(f"\n--- {name} ---")
    for label, key in [("Original", info["original"]), ("Suspect dup", info["suspect"])]:
        issue = jira_repo.get_issue(key)
        if issue:
            print(
                f"  {label} {key}: "
                f"status={issue.fields.status.name}, "
                f"created={issue.fields.created[:10]}"
            )
            jql = f'project = "PARSCHAT" AND "Epic Link" = {key}'
            linked = jira_repo.search_issues(jql, max_results=5)
            print(f"    Issues linked to this epic: {len(linked)}")

print("\n" + "=" * 80)
print("RECENT DUPLICATE STORIES (from broken sync - safe to delete)")
print("=" * 80)

recent_story_dups = {
    "مشاهده برخط وضعیت آموزش": {
        "original": "PARSCHAT-4786",
        "dups": ["PARSCHAT-5041", "PARSCHAT-5087", "PARSCHAT-5114",
                 "PARSCHAT-5141", "PARSCHAT-5168", "PARSCHAT-5195", "PARSCHAT-5222"],
    },
    "اتصال به ژاکت": {
        "original": "PARSCHAT-5037",
        "dups": ["PARSCHAT-5055", "PARSCHAT-5097", "PARSCHAT-5124",
                 "PARSCHAT-5151", "PARSCHAT-5178", "PARSCHAT-5205", "PARSCHAT-5232"],
    },
}

for name, info in recent_story_dups.items():
    print(f"\n--- {name} ---")
    orig_key = info["original"]
    issue = jira_repo.get_issue(orig_key)
    if issue:
        print(
            f"  Original {orig_key}: "
            f"status={issue.fields.status.name}, "
            f"created={issue.fields.created[:10]}"
        )
        subs = jira_repo.get_issue_subtasks(orig_key)
        print(f"    Subtasks ({len(subs)}): {[s.key for s in subs]}")

    for dk in info["dups"][:2]:
        issue = jira_repo.get_issue(dk)
        if issue:
            print(
                f"  Dup {dk}: "
                f"status={issue.fields.status.name}, "
                f"created={issue.fields.created[:10]}"
            )
            subs = jira_repo.get_issue_subtasks(dk)
            print(f"    Subtasks ({len(subs)}): {[s.key for s in subs]}")
    if len(info["dups"]) > 2:
        print(f"  ... and {len(info['dups']) - 2} more duplicates")
