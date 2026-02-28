#!/usr/bin/env python3
"""Sync Jira issue links back to Google Sheet for both Tasks and Features tabs.

For each row in the Google Sheet, searches Jira by summary to find the matching
issue and updates the issue key/link column. Handles both:
  - Tasks sheet (developer board): updates developer_board_issue_key
  - Features sheet (PM board): updates issue_link

Usage:
    python -m scripts.cleanup.sync_sheet_issue_links
    python -m scripts.cleanup.sync_sheet_issue_links --dry-run
    python -m scripts.cleanup.sync_sheet_issue_links --execute
    python -m scripts.cleanup.sync_sheet_issue_links --execute --tasks-only
    python -m scripts.cleanup.sync_sheet_issue_links --execute --features-only
    python -m scripts.cleanup.sync_sheet_issue_links --force-all
"""
import argparse
import asyncio
import json
import logging
import logging.handlers
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

os.makedirs("/tmp/jira_cleanup_logs", exist_ok=True)
_orig_init = logging.handlers.RotatingFileHandler.__init__


def _patched_init(self, filename, *args, **kwargs):
    if "logs/logs.log" in str(filename):
        filename = "/tmp/jira_cleanup_logs/logs.log"
    _orig_init(self, filename, *args, **kwargs)


logging.handlers.RotatingFileHandler.__init__ = _patched_init

from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.adapters.repositories.synth_pm_repository import (
    SynthPMRepository,
)
from jira_telegram_bot.utils.text_normalization import (
    build_jql_summary_search,
    summaries_match,
)


MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


def _search_jira_by_summary(
    synth_repo: SynthPMRepository,
    summary: str,
    project_key: str,
) -> Optional[str]:
    """Search Jira for an issue by summary in a given project (with retries).

    Args:
        synth_repo: SynthPM repository instance
        summary: Issue summary to search for
        project_key: Jira project key

    Returns:
        Issue key if found, None otherwise
    """
    summary_cleaned = summary.strip()
    if not summary_cleaned:
        return None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            jql = build_jql_summary_search(project_key, summary_cleaned)
            issues = synth_repo.jira_repository.search_for_issues(jql, max_results=10)

            if not issues:
                return None

            for issue in issues:
                if summaries_match(issue.fields.summary, summary_cleaned):
                    return issue.key

            return issues[0].key

        except Exception as exc:
            if "504" in str(exc) or "502" in str(exc) or "503" in str(exc):
                if attempt < MAX_RETRIES:
                    print(f"    RETRY {attempt}/{MAX_RETRIES} for '{summary_cleaned[:40]}' (server error)")
                    time.sleep(RETRY_DELAY_SECONDS * attempt)
                    continue
            print(f"    ERROR searching for '{summary_cleaned[:50]}': {exc}")
            return None
    return None


async def _sync_tasks_sheet(
    synth_repo: SynthPMRepository,
    execute: bool,
    force_all: bool,
) -> Tuple[int, int, int]:
    """Sync issue links for the Tasks sheet (developer board).

    Args:
        synth_repo: SynthPM repository instance
        execute: Whether to apply updates
        force_all: Re-verify even rows that already have keys

    Returns:
        Tuple of (updates_found, success_count, fail_count)
    """
    project_key = synth_repo.developer_board_project_key
    print(f"\n{'=' * 70}")
    print(f"TASKS SHEET — searching in Jira project: {project_key}")
    print(f"{'=' * 70}")

    features = await synth_repo.get_developer_board_features()
    print(f"Loaded {len(features)} features from Tasks sheet")

    updates: List[Tuple[int, str, str, str, str]] = []
    skipped = 0
    not_found = 0

    for feature in features:
        title = feature.task_title
        if not title or not title.strip():
            continue

        current_key = feature.developer_board_issue_key
        if current_key and current_key.strip() and not force_all:
            skipped += 1
            continue

        found_key = _search_jira_by_summary(synth_repo, title, project_key)
        time.sleep(0.5)
        if not found_key:
            not_found += 1
            print(f"  NOT FOUND: Row {feature.sheet_row_number} — {title[:70]}")
            continue

        if found_key == current_key:
            skipped += 1
            continue

        updates.append((
            feature.sheet_row_number,
            current_key or "(empty)",
            found_key,
            "developer_board_issue_key",
            title[:60],
        ))

    _print_update_summary("Tasks", updates, skipped, not_found)

    if not updates or not execute:
        return len(updates), 0, 0

    return await _apply_updates(synth_repo, updates, is_pm_board=False)


async def _sync_features_sheet(
    synth_repo: SynthPMRepository,
    execute: bool,
    force_all: bool,
) -> Tuple[int, int, int]:
    """Sync issue links for the Features sheet (PM board).

    Args:
        synth_repo: SynthPM repository instance
        execute: Whether to apply updates
        force_all: Re-verify even rows that already have keys

    Returns:
        Tuple of (updates_found, success_count, fail_count)
    """
    pm_board_key = synth_repo.pm_board_key
    if not pm_board_key:
        print("\n  PM board not configured — skipping Features sheet")
        return 0, 0, 0

    print(f"\n{'=' * 70}")
    print(f"FEATURES SHEET — searching in Jira project: {pm_board_key}")
    print(f"{'=' * 70}")

    release_notes = await synth_repo.get_release_notes()
    print(f"Loaded {len(release_notes)} release notes from Features sheet")

    updates: List[Tuple[int, str, str, str, str]] = []
    skipped = 0
    not_found = 0

    for note in release_notes:
        search_term = note.release_components
        if not search_term or not search_term.strip():
            continue

        current_key = note.issue_link
        if current_key and current_key.strip() and not force_all:
            skipped += 1
            continue

        found_key = _search_jira_by_summary(synth_repo, search_term, pm_board_key)
        time.sleep(0.5)
        if not found_key:
            not_found += 1
            print(f"  NOT FOUND: Row {note.row_number} — {search_term[:70]}")
            continue

        if found_key == current_key:
            skipped += 1
            continue

        updates.append((
            note.row_number,
            current_key or "(empty)",
            found_key,
            "issue_link",
            search_term[:60],
        ))

    _print_update_summary("Features", updates, skipped, not_found)

    if not updates or not execute:
        return len(updates), 0, 0

    return await _apply_updates(synth_repo, updates, is_pm_board=True)


def _print_update_summary(
    sheet_name: str,
    updates: List[Tuple],
    skipped: int,
    not_found: int,
) -> None:
    """Print summary of discovered updates.

    Args:
        sheet_name: Name of the sheet being reported
        updates: List of update tuples
        skipped: Number of rows skipped
        not_found: Number of rows where Jira issue was not found
    """
    print(f"\n  Summary for {sheet_name}:")
    print(f"    Skipped (already set): {skipped}")
    print(f"    Not found in Jira:     {not_found}")
    print(f"    Updates needed:        {len(updates)}")

    if updates:
        print(f"\n  Updates to apply:")
        for row_num, old_val, new_key, field, title in updates:
            print(f"    Row {row_num}: {old_val} -> {new_key}  ({title})")


async def _apply_updates(
    synth_repo: SynthPMRepository,
    updates: List[Tuple[int, str, str, str, str]],
    is_pm_board: bool,
) -> Tuple[int, int, int]:
    """Apply updates to the Google Sheet.

    Args:
        synth_repo: SynthPM repository instance
        updates: List of (row_num, old_val, new_key, field_name, title) tuples
        is_pm_board: Whether this is PM board (Features) or developer board (Tasks)

    Returns:
        Tuple of (total, success_count, fail_count)
    """
    print(f"\n  --- EXECUTING {len(updates)} sheet updates ---")
    success_count = 0
    fail_count = 0

    for row_num, old_val, new_key, field_name, title in updates:
        try:
            if is_pm_board:
                result = await synth_repo.update_release_note(
                    row_num,
                    {field_name: new_key},
                )
            else:
                result = await synth_repo.update_developer_board_feature(
                    row_num,
                    {field_name: new_key},
                )

            if result:
                print(f"    OK   Row {row_num}: {old_val} -> {new_key}")
                success_count += 1
            else:
                print(f"    FAIL Row {row_num}: {old_val} -> {new_key}")
                fail_count += 1

            time.sleep(0.3)

        except Exception as exc:
            print(f"    ERROR Row {row_num}: {old_val} -> {new_key}: {exc}")
            fail_count += 1

    return len(updates), success_count, fail_count


async def main():
    parser = argparse.ArgumentParser(
        description="Sync Jira issue links to Google Sheet (Tasks & Features)",
    )
    parser.add_argument("--execute", action="store_true", help="Apply updates (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Only report what would change (this is the default)")
    parser.add_argument("--tasks-only", action="store_true", help="Only sync Tasks sheet")
    parser.add_argument("--features-only", action="store_true", help="Only sync Features sheet")
    parser.add_argument("--force-all", action="store_true", help="Re-check rows that already have keys")
    args = parser.parse_args()

    if args.tasks_only and args.features_only:
        print("Cannot use --tasks-only and --features-only together")
        return

    if args.dry_run and args.execute:
        print("Cannot use --dry-run and --execute together")
        return

    execute = args.execute and not args.dry_run
    mode = "EXECUTE" if execute else "DRY RUN"
    print(f"\nMode: {mode}")

    container = get_container()
    synth_repo = container[SynthPMRepository]

    total_updates = 0
    total_success = 0
    total_fail = 0

    if not args.features_only:
        updates, success, fail = await _sync_tasks_sheet(synth_repo, execute, args.force_all)
        total_updates += updates
        total_success += success
        total_fail += fail

    if not args.tasks_only:
        updates, success, fail = await _sync_features_sheet(synth_repo, execute, args.force_all)
        total_updates += updates
        total_success += success
        total_fail += fail

    print(f"\n{'=' * 70}")
    print(f"GRAND TOTAL: {total_updates} updates needed")
    if execute:
        print(f"  Applied: {total_success} OK, {total_fail} FAILED")
    else:
        print(f"  Dry-run complete. Use --execute to apply changes.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
