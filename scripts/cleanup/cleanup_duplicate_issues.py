#!/usr/bin/env python3
"""Cleanup duplicate Jira stories and epics created by broken sync.

This script:
1. Connects to Jira via the app container
2. Finds all duplicate stories and epics by summary comparison
3. Identifies which duplicates have subtasks that need moving
4. Moves subtasks from duplicate parents to original parents
5. Deletes empty duplicate stories/epics
6. Updates Google Sheet with correct issue keys

Usage:
    # Dry-run (default) — only reports what would happen
    python -m scripts.cleanup.cleanup_duplicate_issues

    # Actually perform cleanup
    python -m scripts.cleanup.cleanup_duplicate_issues --execute
"""
import argparse
import asyncio
import json
import logging
import logging.handlers
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
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
from jira_telegram_bot.utils.text_normalization import normalize_persian_text


PROJECT_KEY = "PARSCHAT"
RECENT_ISSUE_THRESHOLD = 5000
DONE_STATUSES = {"Done", "Closed", "Resolved"}

PROTECTED_EPIC_KEYS = {"PARSCHAT-3297", "PARSCHAT-2356"}


@dataclass
class DuplicateGroup:
    """Tracks a set of duplicate issues sharing the same summary."""

    summary: str
    original_key: str
    duplicate_keys: List[str] = field(default_factory=list)
    original_subtask_count: int = 0
    issue_type: str = "Story"


@dataclass
class CleanupPlan:
    """Full cleanup plan built from Jira discovery."""

    duplicate_stories: List[DuplicateGroup] = field(default_factory=list)
    duplicate_epics: List[DuplicateGroup] = field(default_factory=list)
    subtasks_to_move: List[Tuple[str, str, str]] = field(default_factory=list)
    issues_to_delete: List[str] = field(default_factory=list)
    skipped_old_dups: List[Dict] = field(default_factory=list)
    epic_link_migrations: List[Tuple[str, str, str]] = field(default_factory=list)


def _issue_number(key: str) -> int:
    """Extract numeric part from issue key.

    Args:
        key: Jira issue key like PARSCHAT-1234.

    Returns:
        Numeric portion of the key.
    """
    return int(key.split("-")[1])


def _is_recent(key: str) -> bool:
    """Check if an issue key is from the recent broken sync.

    Args:
        key: Jira issue key.

    Returns:
        True if the issue number is >= RECENT_ISSUE_THRESHOLD.
    """
    return _issue_number(key) >= RECENT_ISSUE_THRESHOLD


def _pick_original(issues: list) -> Tuple[str, List[str]]:
    """Pick the original issue (lowest key number) and return duplicates.

    Args:
        issues: List of Jira issue objects with same summary.

    Returns:
        Tuple of (original_key, list_of_duplicate_keys).
    """
    sorted_issues = sorted(issues, key=lambda i: _issue_number(i.key))
    original = sorted_issues[0]
    duplicates = sorted_issues[1:]
    return original.key, [d.key for d in duplicates]


def _has_worklogs(jira_repo: TaskManagerRepositoryInterface, issue_key: str) -> bool:
    """Check if an issue has worklogs.

    Args:
        jira_repo: Jira repository interface.
        issue_key: Issue key to check.

    Returns:
        True if the issue has worklogs.
    """
    try:
        issue = jira_repo.get_issue(issue_key)
        if not issue:
            return False
        tt = getattr(issue.fields, "timetracking", None)
        if tt:
            logged = getattr(tt, "timeSpentSeconds", 0) or 0
            if logged > 0:
                return True
        return False
    except Exception:
        return False


async def discover_duplicate_stories(
    jira_repo: TaskManagerRepositoryInterface,
) -> Tuple[List[DuplicateGroup], List[Dict]]:
    """Find all duplicate Stories in the project.

    Separates recent duplicates (safe to delete) from old ones
    (Done/with worklogs) that need manual review.

    Args:
        jira_repo: Jira repository interface.

    Returns:
        Tuple of (actionable_groups, skipped_old_dups).
    """
    jql = (
        f'project = "{PROJECT_KEY}" AND issuetype = Story '
        f"AND status != Closed ORDER BY key ASC"
    )
    all_stories = jira_repo.search_issues(jql, max_results=500)
    LOGGER.info(f"Found {len(all_stories)} open stories in {PROJECT_KEY}")

    by_summary: Dict[str, list] = defaultdict(list)
    for story in all_stories:
        normalised = normalize_persian_text(story.fields.summary)
        by_summary[normalised].append(story)

    actionable_groups = []
    skipped_old = []

    for normalised_summary, issues in by_summary.items():
        if len(issues) < 2:
            continue

        original_key, duplicate_keys = _pick_original(issues)
        original_issue = next(i for i in issues if i.key == original_key)
        subtask_count = len(getattr(original_issue.fields, "subtasks", None) or [])

        recent_dups = [k for k in duplicate_keys if _is_recent(k)]
        old_dups = [k for k in duplicate_keys if not _is_recent(k)]

        for old_key in old_dups:
            old_issue = next((i for i in issues if i.key == old_key), None)
            if not old_issue:
                continue
            status = old_issue.fields.status.name
            has_wl = _has_worklogs(jira_repo, old_key)
            old_subtasks = jira_repo.get_issue_subtasks(old_key)
            if status in DONE_STATUSES or has_wl or len(old_subtasks) > 0:
                skipped_old.append({
                    "key": old_key,
                    "summary": old_issue.fields.summary,
                    "status": status,
                    "has_worklogs": has_wl,
                    "subtask_count": len(old_subtasks),
                    "original": original_key,
                    "reason": "Done/worklogs/subtasks",
                })
            else:
                recent_dups.append(old_key)

        if recent_dups:
            group = DuplicateGroup(
                summary=issues[0].fields.summary,
                original_key=original_key,
                duplicate_keys=recent_dups,
                original_subtask_count=subtask_count,
                issue_type="Story",
            )
            actionable_groups.append(group)

    return actionable_groups, skipped_old


async def discover_duplicate_epics(
    jira_repo: TaskManagerRepositoryInterface,
) -> List[DuplicateGroup]:
    """Find all duplicate Epics in the project.

    Skips protected old epics that are actively used.

    Args:
        jira_repo: Jira repository interface.

    Returns:
        List of DuplicateGroup for each set of duplicates.
    """
    jql = (
        f'project = "{PROJECT_KEY}" AND issuetype = Epic '
        f"AND status != Closed ORDER BY key ASC"
    )
    all_epics = jira_repo.search_issues(jql, max_results=500)
    LOGGER.info(f"Found {len(all_epics)} open epics in {PROJECT_KEY}")

    by_summary: Dict[str, list] = defaultdict(list)
    for epic in all_epics:
        normalised = normalize_persian_text(epic.fields.summary)
        by_summary[normalised].append(epic)

    groups = []
    for normalised_summary, issues in by_summary.items():
        if len(issues) < 2:
            continue

        original_key, duplicate_keys = _pick_original(issues)
        safe_dups = [k for k in duplicate_keys if k not in PROTECTED_EPIC_KEYS]

        if safe_dups:
            group = DuplicateGroup(
                summary=issues[0].fields.summary,
                original_key=original_key,
                duplicate_keys=safe_dups,
                issue_type="Epic",
            )
            groups.append(group)

    return groups


def _find_epic_link_field(jira_repo: TaskManagerRepositoryInterface) -> Optional[str]:
    """Find the epic link custom field ID.

    Args:
        jira_repo: Jira repository interface.

    Returns:
        Custom field ID for epic link, or None.
    """
    try:
        issue = jira_repo.get_issue(f"{PROJECT_KEY}-282")
        if issue:
            for attr_name in dir(issue.fields):
                if attr_name.startswith("customfield_"):
                    val = getattr(issue.fields, attr_name, None)
                    if val and str(val) == f"{PROJECT_KEY}-282":
                        return attr_name
    except Exception:
        pass
    return "customfield_10100"


def build_cleanup_plan(
    jira_repo: TaskManagerRepositoryInterface,
    story_groups: List[DuplicateGroup],
    epic_groups: List[DuplicateGroup],
    skipped_old: List[Dict],
) -> CleanupPlan:
    """Build a complete cleanup plan.

    Args:
        jira_repo: Jira repository interface.
        story_groups: Duplicate story groups.
        epic_groups: Duplicate epic groups.
        skipped_old: Old duplicates that are skipped.

    Returns:
        CleanupPlan with all actions needed.
    """
    plan = CleanupPlan(
        duplicate_stories=story_groups,
        duplicate_epics=epic_groups,
        skipped_old_dups=skipped_old,
    )

    for group in story_groups:
        for dup_key in group.duplicate_keys:
            subtasks = jira_repo.get_issue_subtasks(dup_key)
            for subtask in subtasks:
                plan.subtasks_to_move.append(
                    (subtask.key, dup_key, group.original_key),
                )
            plan.issues_to_delete.append(dup_key)

    for group in epic_groups:
        for dup_key in group.duplicate_keys:
            jql = f'project = "{PROJECT_KEY}" AND "Epic Link" = {dup_key}'
            try:
                linked_issues = jira_repo.search_issues(jql, max_results=100)
                for linked in linked_issues:
                    plan.epic_link_migrations.append(
                        (linked.key, dup_key, group.original_key),
                    )
            except Exception as e:
                LOGGER.warning(f"Could not check epic links for {dup_key}: {e}")
            plan.issues_to_delete.append(dup_key)

    return plan


def print_plan(plan: CleanupPlan) -> None:
    """Print the cleanup plan in a human-readable format.

    Args:
        plan: The cleanup plan to display.
    """
    print("\n" + "=" * 80)
    print("DUPLICATE STORIES TO CLEAN")
    print("=" * 80)
    for group in plan.duplicate_stories:
        print(f"\n  Summary: {group.summary}")
        print(f"  Original: {group.original_key} ({group.original_subtask_count} subtasks)")
        print(f"  Duplicates to delete: {', '.join(group.duplicate_keys)}")

    if plan.skipped_old_dups:
        print("\n" + "=" * 80)
        print("SKIPPED OLD DUPLICATES (Done/worklogs — saved to report)")
        print("=" * 80)
        for item in plan.skipped_old_dups:
            print(
                f"  {item['key']}: {item['summary'][:50]} "
                f"(status={item['status']}, worklogs={item['has_worklogs']}, "
                f"subtasks={item['subtask_count']}, original={item['original']})"
            )

    print("\n" + "=" * 80)
    print("DUPLICATE EPICS TO CLEAN")
    print("=" * 80)
    for group in plan.duplicate_epics:
        print(f"\n  Summary: {group.summary}")
        print(f"  Original: {group.original_key}")
        print(f"  Duplicates to delete ({len(group.duplicate_keys)}): {', '.join(group.duplicate_keys[:5])}")
        if len(group.duplicate_keys) > 5:
            print(f"    ... and {len(group.duplicate_keys) - 5} more")

    if plan.epic_link_migrations:
        print("\n" + "=" * 80)
        print(f"EPIC LINKS TO MIGRATE ({len(plan.epic_link_migrations)})")
        print("=" * 80)
        for issue_key, from_epic, to_epic in plan.epic_link_migrations[:20]:
            print(f"  {issue_key}: epic {from_epic} -> {to_epic}")
        if len(plan.epic_link_migrations) > 20:
            print(f"  ... and {len(plan.epic_link_migrations) - 20} more")

    if plan.subtasks_to_move:
        print("\n" + "=" * 80)
        print(f"SUBTASKS TO MOVE ({len(plan.subtasks_to_move)})")
        print("=" * 80)
        for subtask_key, from_parent, to_parent in plan.subtasks_to_move:
            print(f"  {subtask_key}: {from_parent} -> {to_parent}")

    total_stories_to_delete = sum(
        len(g.duplicate_keys) for g in plan.duplicate_stories
    )
    total_epics_to_delete = sum(
        len(g.duplicate_keys) for g in plan.duplicate_epics
    )
    total_deletes = total_stories_to_delete + total_epics_to_delete

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Subtasks to move:     {len(plan.subtasks_to_move)}")
    print(f"  Epic links to migrate: {len(plan.epic_link_migrations)}")
    print(f"  Stories to delete:    {total_stories_to_delete}")
    print(f"  Epics to delete:      {total_epics_to_delete}")
    print(f"  Old dups skipped:     {len(plan.skipped_old_dups)}")
    print(f"  TOTAL actions:        {len(plan.subtasks_to_move) + len(plan.epic_link_migrations) + total_deletes}")


def _save_report(plan: CleanupPlan, results: Dict) -> Path:
    """Save cleanup report to disk.

    Args:
        plan: The cleanup plan.
        results: Execution results.

    Returns:
        Path to the saved report file.
    """
    report_path = Path("data/cleanup_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        **results,
        "skipped_old_duplicates": plan.skipped_old_dups,
        "duplicate_stories": [
            {
                "summary": g.summary,
                "original": g.original_key,
                "duplicates": g.duplicate_keys,
            }
            for g in plan.duplicate_stories
        ],
        "duplicate_epics": [
            {
                "summary": g.summary,
                "original": g.original_key,
                "duplicates": g.duplicate_keys,
            }
            for g in plan.duplicate_epics
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report_path


async def execute_plan(
    jira_repo: TaskManagerRepositoryInterface,
    plan: CleanupPlan,
) -> None:
    """Execute the cleanup plan.

    Steps: migrate epic links, move subtasks, delete empty duplicates.

    Args:
        jira_repo: Jira repository interface.
        plan: The cleanup plan to execute.
    """
    print("\n" + "=" * 80)
    print("EXECUTING CLEANUP PLAN")
    print("=" * 80)

    results: Dict = {
        "epic_links_migrated": [],
        "epic_links_failed": [],
        "subtasks_moved": {},
        "subtasks_failed": [],
        "issues_deleted": [],
        "issues_skipped": [],
        "issues_failed": [],
    }

    if plan.epic_link_migrations:
        print("\n--- Phase 1: Migrating epic links ---")
        epic_link_field = _find_epic_link_field(jira_repo)
        for issue_key, from_epic, to_epic in plan.epic_link_migrations:
            try:
                issue = jira_repo.get_issue(issue_key)
                if issue:
                    issue.update(fields={epic_link_field: to_epic})
                    results["epic_links_migrated"].append(
                        {"issue": issue_key, "from": from_epic, "to": to_epic},
                    )
                    print(f"  OK: {issue_key} epic: {from_epic} -> {to_epic}")
            except Exception as e:
                results["epic_links_failed"].append(
                    {"issue": issue_key, "from": from_epic, "to": to_epic, "error": str(e)},
                )
                print(f"  FAIL: {issue_key}: {e}")

    if plan.subtasks_to_move:
        print("\n--- Phase 2: Moving subtasks ---")
        for subtask_key, from_parent, to_parent in plan.subtasks_to_move:
            print(f"  Moving {subtask_key}: {from_parent} -> {to_parent}...")
            try:
                new_key = jira_repo.convert_to_subtask(subtask_key, to_parent)
                if new_key:
                    results["subtasks_moved"][subtask_key] = new_key
                    print(f"    OK: {subtask_key} -> {new_key}")
                else:
                    results["subtasks_failed"].append(subtask_key)
                    print(f"    FAILED: Could not move {subtask_key}")
            except Exception as e:
                results["subtasks_failed"].append(subtask_key)
                print(f"    ERROR: {subtask_key}: {e}")

    print("\n--- Phase 3: Deleting empty duplicate issues ---")
    for key in plan.issues_to_delete:
        try:
            remaining_subtasks = jira_repo.get_issue_subtasks(key)
            if remaining_subtasks:
                results["issues_skipped"].append(key)
                print(f"  SKIP {key}: still has {len(remaining_subtasks)} subtasks")
                continue

            success = jira_repo.delete_issue(key)
            if success:
                results["issues_deleted"].append(key)
                print(f"  OK: Deleted {key}")
            else:
                results["issues_failed"].append(key)
                print(f"  FAIL: {key}")
        except Exception as e:
            results["issues_failed"].append(key)
            print(f"  ERROR: {key}: {e}")

    report_path = _save_report(plan, results)

    print("\n" + "=" * 80)
    print("EXECUTION COMPLETE")
    print("=" * 80)
    print(f"  Epic links migrated:  {len(results['epic_links_migrated'])}")
    print(f"  Epic links failed:    {len(results['epic_links_failed'])}")
    print(f"  Subtasks moved:       {len(results['subtasks_moved'])}")
    print(f"  Subtasks failed:      {len(results['subtasks_failed'])}")
    print(f"  Issues deleted:       {len(results['issues_deleted'])}")
    print(f"  Issues skipped:       {len(results['issues_skipped'])}")
    print(f"  Issues failed:        {len(results['issues_failed'])}")
    print(f"  Report saved to:      {report_path}")


async def main() -> None:
    """Run the duplicate cleanup workflow."""
    parser = argparse.ArgumentParser(description="Cleanup duplicate Jira issues")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform cleanup (default is dry-run)",
    )
    args = parser.parse_args()

    container = get_container()
    jira_repo = container[TaskManagerRepositoryInterface]

    print("Discovering duplicate stories...")
    story_groups, skipped_old = await discover_duplicate_stories(jira_repo)

    print("Discovering duplicate epics...")
    epic_groups = await discover_duplicate_epics(jira_repo)

    plan = build_cleanup_plan(jira_repo, story_groups, epic_groups, skipped_old)
    print_plan(plan)

    if not story_groups and not epic_groups:
        print("\nNo actionable duplicates found.")
        return

    if not args.execute:
        report_path = _save_report(plan, {"dry_run": True})
        print(f"\n  Dry-run report saved to {report_path}")
        print(
            "\n--- DRY RUN --- "
            "Run with --execute to actually perform cleanup."
        )
        return

    await execute_plan(jira_repo, plan)


if __name__ == "__main__":
    asyncio.run(main())
