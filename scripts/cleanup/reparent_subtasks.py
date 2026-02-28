#!/usr/bin/env python3
"""Re-parent subtasks from duplicate stories to their original parents.

The main cleanup script cannot move subtasks that are already Sub-tasks
under a different parent (convert_to_subtask refuses to re-parent).
This script uses the Jira REST API directly to change the parent field.

Usage:
    python -m scripts.cleanup.reparent_subtasks
    python -m scripts.cleanup.reparent_subtasks --execute
"""
import argparse
import asyncio
import json
import logging
import logging.handlers
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

os.makedirs("/tmp/jira_cleanup_logs", exist_ok=True)
_orig_init = logging.handlers.RotatingFileHandler.__init__


def _patched_init(self, filename, *args, **kwargs):
    if "logs/logs.log" in str(filename):
        filename = "/tmp/jira_cleanup_logs/logs.log"
    _orig_init(self, filename, *args, **kwargs)


logging.handlers.RotatingFileHandler.__init__ = _patched_init

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)


SUBTASKS_TO_REPARENT: Dict[str, Dict[str, str]] = {
    "PARSCHAT-5041": {
        "new_parent": "PARSCHAT-4786",
        "subtasks": ["PARSCHAT-5042", "PARSCHAT-5043", "PARSCHAT-5044"],
    },
    "PARSCHAT-5087": {
        "new_parent": "PARSCHAT-4786",
        "subtasks": ["PARSCHAT-5088"],
    },
    "PARSCHAT-5114": {
        "new_parent": "PARSCHAT-4786",
        "subtasks": ["PARSCHAT-5115"],
    },
    "PARSCHAT-5141": {
        "new_parent": "PARSCHAT-4786",
        "subtasks": ["PARSCHAT-5142"],
    },
    "PARSCHAT-5168": {
        "new_parent": "PARSCHAT-4786",
        "subtasks": ["PARSCHAT-5169"],
    },
    "PARSCHAT-5195": {
        "new_parent": "PARSCHAT-4786",
        "subtasks": ["PARSCHAT-5196"],
    },
    "PARSCHAT-5222": {
        "new_parent": "PARSCHAT-4786",
        "subtasks": ["PARSCHAT-5223"],
    },
    "PARSCHAT-5072": {
        "new_parent": "PARSCHAT-4842",
        "subtasks": ["PARSCHAT-5073", "PARSCHAT-5074", "PARSCHAT-5075", "PARSCHAT-5076", "PARSCHAT-5077"],
    },
    "PARSCHAT-5061": {
        "new_parent": "PARSCHAT-4844",
        "subtasks": ["PARSCHAT-5062"],
    },
    "PARSCHAT-5051": {
        "new_parent": "PARSCHAT-5036",
        "subtasks": ["PARSCHAT-5052", "PARSCHAT-5053"],
    },
    "PARSCHAT-5055": {
        "new_parent": "PARSCHAT-5037",
        "subtasks": ["PARSCHAT-5056", "PARSCHAT-5057", "PARSCHAT-5058"],
    },
    "PARSCHAT-5064": {
        "new_parent": "PARSCHAT-5038",
        "subtasks": ["PARSCHAT-5065"],
    },
    "PARSCHAT-5080": {
        "new_parent": "PARSCHAT-5039",
        "subtasks": ["PARSCHAT-5081", "PARSCHAT-5082", "PARSCHAT-5083", "PARSCHAT-5084", "PARSCHAT-5085"],
    },
}


def _reparent_via_rest(jira_repo, subtask_key: str, new_parent_key: str) -> bool:
    """Re-parent a subtask using the Jira REST API.

    Args:
        jira_repo: Jira repository with access to the jira client.
        subtask_key: Key of the subtask to reparent.
        new_parent_key: Key of the new parent issue.

    Returns:
        True if successful, False otherwise.
    """
    try:
        jira_client = jira_repo.jira
        server = jira_client._options["server"]
        url = f"{server}/rest/api/2/issue/{subtask_key}"
        payload = {
            "fields": {
                "parent": {"key": new_parent_key},
            },
        }
        response = jira_client._session.put(url, json=payload)
        if response.status_code in (200, 204):
            return True
        LOGGER.warning(
            f"REST PUT for {subtask_key} returned {response.status_code}: "
            f"{response.text[:300]}",
        )
        return False
    except Exception as e:
        LOGGER.error(f"Error reparenting {subtask_key}: {e}")
        return False


def _reparent_via_recreate(jira_repo, subtask_key: str, new_parent_key: str) -> Optional[str]:
    """Re-parent a subtask by recreating it under the new parent.

    Migrates worklogs, comments, and time fields.

    Args:
        jira_repo: Jira repository.
        subtask_key: Key of the subtask to reparent.
        new_parent_key: Key of the new parent issue.

    Returns:
        New subtask key on success, None on failure.
    """
    try:
        old_issue = jira_repo.jira.issue(subtask_key)
        subtask_type_id = jira_repo._get_subtask_type_id()
        if not subtask_type_id:
            return None
        new_key = jira_repo._recreate_as_subtask(
            old_issue, subtask_key, new_parent_key, subtask_type_id,
        )
        return new_key
    except Exception as e:
        LOGGER.error(f"Error recreating {subtask_key}: {e}")
        return None


async def main() -> None:
    """Re-parent subtasks from duplicate parents to original parents."""
    parser = argparse.ArgumentParser(description="Re-parent subtasks")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform re-parenting (default is dry-run)",
    )
    args = parser.parse_args()

    container = get_container()
    jira_repo = container[TaskManagerRepositoryInterface]

    all_subtasks = []
    for old_parent, info in SUBTASKS_TO_REPARENT.items():
        for subtask_key in info["subtasks"]:
            all_subtasks.append((subtask_key, old_parent, info["new_parent"]))

    print("=" * 80)
    print(f"SUBTASKS TO RE-PARENT ({len(all_subtasks)})")
    print("=" * 80)
    for subtask_key, old_parent, new_parent in all_subtasks:
        print(f"  {subtask_key}: {old_parent} -> {new_parent}")

    if not args.execute:
        print("\n--- DRY RUN --- Run with --execute to re-parent.")
        return

    print("\n--- EXECUTING ---")

    moved = {}
    failed = []

    for subtask_key, old_parent, new_parent in all_subtasks:
        print(f"\n  Re-parenting {subtask_key}: {old_parent} -> {new_parent}")

        issue = jira_repo.get_issue(subtask_key)
        if not issue:
            print(f"    ERROR: Issue {subtask_key} not found")
            failed.append(subtask_key)
            continue

        current_parent = getattr(issue.fields, "parent", None)
        if current_parent and current_parent.key == new_parent:
            print(f"    SKIP: Already under {new_parent}")
            moved[subtask_key] = subtask_key
            continue

        # REST PUT silently ignores parent field on Jira Server.
        # Go directly to recreation approach.
        new_key = _reparent_via_recreate(jira_repo, subtask_key, new_parent)
        if new_key:
            print(f"    OK (recreated): {subtask_key} -> {new_key} under {new_parent}")
            moved[subtask_key] = new_key
        else:
            print(f"    FAILED: Could not reparent {subtask_key}")
            failed.append(subtask_key)

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"  Moved:  {len(moved)}")
    print(f"  Failed: {len(failed)}")
    if failed:
        print(f"  Failed keys: {failed}")

    report_path = Path("data/reparent_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(
        {"moved": moved, "failed": failed},
        ensure_ascii=False,
        indent=2,
    ))
    print(f"  Report: {report_path}")

    if moved:
        print("\n--- Next step: delete empty duplicate parents ---")
        parents_to_check = set()
        for old_parent in SUBTASKS_TO_REPARENT:
            parents_to_check.add(old_parent)
        for parent_key in sorted(parents_to_check):
            remaining = jira_repo.get_issue_subtasks(parent_key)
            if not remaining:
                print(f"  {parent_key}: EMPTY — ready to delete")
            else:
                print(f"  {parent_key}: still has {len(remaining)} subtasks")


if __name__ == "__main__":
    asyncio.run(main())
