#!/usr/bin/env python3
"""Verify subtask re-parenting and delete empty duplicate parents."""
import argparse
import asyncio
import json
import logging
import logging.handlers
import os
from pathlib import Path

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

SUBTASK_KEYS = [
    "PARSCHAT-5042", "PARSCHAT-5043", "PARSCHAT-5044",
    "PARSCHAT-5088", "PARSCHAT-5115", "PARSCHAT-5142",
    "PARSCHAT-5169", "PARSCHAT-5196", "PARSCHAT-5223",
    "PARSCHAT-5073", "PARSCHAT-5074", "PARSCHAT-5075",
    "PARSCHAT-5076", "PARSCHAT-5077",
    "PARSCHAT-5062",
    "PARSCHAT-5052", "PARSCHAT-5053",
    "PARSCHAT-5056", "PARSCHAT-5057", "PARSCHAT-5058",
    "PARSCHAT-5065",
    "PARSCHAT-5081", "PARSCHAT-5082", "PARSCHAT-5083",
    "PARSCHAT-5084", "PARSCHAT-5085",
]

EXPECTED_NEW_PARENT = {
    "PARSCHAT-5042": "PARSCHAT-4786", "PARSCHAT-5043": "PARSCHAT-4786",
    "PARSCHAT-5044": "PARSCHAT-4786", "PARSCHAT-5088": "PARSCHAT-4786",
    "PARSCHAT-5115": "PARSCHAT-4786", "PARSCHAT-5142": "PARSCHAT-4786",
    "PARSCHAT-5169": "PARSCHAT-4786", "PARSCHAT-5196": "PARSCHAT-4786",
    "PARSCHAT-5223": "PARSCHAT-4786",
    "PARSCHAT-5073": "PARSCHAT-4842", "PARSCHAT-5074": "PARSCHAT-4842",
    "PARSCHAT-5075": "PARSCHAT-4842", "PARSCHAT-5076": "PARSCHAT-4842",
    "PARSCHAT-5077": "PARSCHAT-4842",
    "PARSCHAT-5062": "PARSCHAT-4844",
    "PARSCHAT-5052": "PARSCHAT-5036", "PARSCHAT-5053": "PARSCHAT-5036",
    "PARSCHAT-5056": "PARSCHAT-5037", "PARSCHAT-5057": "PARSCHAT-5037",
    "PARSCHAT-5058": "PARSCHAT-5037",
    "PARSCHAT-5065": "PARSCHAT-5038",
    "PARSCHAT-5081": "PARSCHAT-5039", "PARSCHAT-5082": "PARSCHAT-5039",
    "PARSCHAT-5083": "PARSCHAT-5039", "PARSCHAT-5084": "PARSCHAT-5039",
    "PARSCHAT-5085": "PARSCHAT-5039",
}

OLD_PARENTS = [
    "PARSCHAT-5041", "PARSCHAT-5087", "PARSCHAT-5114",
    "PARSCHAT-5141", "PARSCHAT-5168", "PARSCHAT-5195",
    "PARSCHAT-5222", "PARSCHAT-5072", "PARSCHAT-5061",
    "PARSCHAT-5051", "PARSCHAT-5055", "PARSCHAT-5064",
    "PARSCHAT-5080",
]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true")
    args = parser.parse_args()

    container = get_container()
    jira_repo = container[TaskManagerRepositoryInterface]

    print("=" * 70)
    print("VERIFYING SUBTASK PARENTS")
    print("=" * 70)

    wrong = []
    ok = []
    missing = []
    for key in SUBTASK_KEYS:
        expected = EXPECTED_NEW_PARENT[key]
        try:
            issue = jira_repo.jira.issue(key)
            parent = getattr(issue.fields, "parent", None)
            actual = parent.key if parent else "NONE"
            if actual == expected:
                print(f"  OK   {key} -> {actual}")
                ok.append(key)
            else:
                print(f"  WRONG {key} -> {actual} (expected {expected})")
                wrong.append((key, actual, expected))
        except Exception as exc:
            print(f"  MISSING {key}: {exc}")
            missing.append(key)

    print(f"\nOK: {len(ok)}, WRONG: {len(wrong)}, MISSING: {len(missing)}")

    print("\n" + "=" * 70)
    print("CHECKING OLD PARENT SUBTASKS")
    print("=" * 70)

    empty_parents = []
    nonempty_parents = []
    for parent_key in OLD_PARENTS:
        try:
            subs = jira_repo.get_issue_subtasks(parent_key)
            sub_keys = [s.key for s in subs]
            if not sub_keys:
                print(f"  EMPTY  {parent_key}")
                empty_parents.append(parent_key)
            else:
                print(f"  HAS {len(sub_keys)} subtasks  {parent_key}: {sub_keys}")
                nonempty_parents.append((parent_key, sub_keys))
        except Exception as exc:
            print(f"  ERROR  {parent_key}: {exc}")

    if args.delete and empty_parents:
        print(f"\n--- DELETING {len(empty_parents)} empty duplicate parents ---")
        deleted = []
        failed = []
        for key in empty_parents:
            try:
                jira_repo.jira.issue(key).delete()
                print(f"  DELETED {key}")
                deleted.append(key)
            except Exception as exc:
                print(f"  FAILED  {key}: {exc}")
                failed.append(key)
        print(f"\nDeleted: {len(deleted)}, Failed: {len(failed)}")

    if nonempty_parents:
        print(f"\n--- {len(nonempty_parents)} parents still have subtasks ---")
        print("These subtasks still need re-parenting before parent can be deleted.")


if __name__ == "__main__":
    asyncio.run(main())
