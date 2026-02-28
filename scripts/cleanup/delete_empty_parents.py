#!/usr/bin/env python3
"""Delete the 13 remaining empty duplicate story parents."""
import argparse
import asyncio
import logging
import logging.handlers
import os

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

DUPLICATE_PARENTS = [
    "PARSCHAT-5041", "PARSCHAT-5087", "PARSCHAT-5114",
    "PARSCHAT-5141", "PARSCHAT-5168", "PARSCHAT-5195",
    "PARSCHAT-5222", "PARSCHAT-5072", "PARSCHAT-5061",
    "PARSCHAT-5051", "PARSCHAT-5055", "PARSCHAT-5064",
    "PARSCHAT-5080",
]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    container = get_container()
    jira_repo = container[TaskManagerRepositoryInterface]

    print(f"Checking {len(DUPLICATE_PARENTS)} duplicate parents...")
    empty = []
    not_empty = []
    for key in DUPLICATE_PARENTS:
        try:
            issue = jira_repo.jira.issue(key)
            subtasks = issue.fields.subtasks
            if not subtasks:
                empty.append(key)
                print(f"  {key}: EMPTY (summary: {issue.fields.summary[:60]})")
            else:
                not_empty.append((key, [s.key for s in subtasks]))
                print(f"  {key}: {len(subtasks)} subtasks: {[s.key for s in subtasks]}")
        except Exception as e:
            print(f"  {key}: ERROR — {e}")

    if not_empty:
        print(f"\n{len(not_empty)} parents still have subtasks!")

    if not args.execute:
        print(f"\n{len(empty)} empty parents ready to delete. Run with --execute.")
        return

    print(f"\nDeleting {len(empty)} empty duplicate parents...")
    deleted = []
    failed = []
    for key in empty:
        try:
            jira_repo.jira.issue(key).delete()
            print(f"  DELETED: {key}")
            deleted.append(key)
        except Exception as e:
            print(f"  FAILED: {key} — {e}")
            failed.append(key)

    print(f"\nDeleted: {len(deleted)}, Failed: {len(failed)}")


if __name__ == "__main__":
    asyncio.run(main())
