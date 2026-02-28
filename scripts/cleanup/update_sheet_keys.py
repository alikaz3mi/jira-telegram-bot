#!/usr/bin/env python3
"""Update Google Sheet to replace deleted/renamed Jira issue keys.

Reads cleanup_report.json and reparent_report.json to build a complete
mapping of old_key -> replacement_key, then scans the Google Sheet
for any references to old keys and updates them.

Usage:
    python -m scripts.cleanup.update_sheet_keys
    python -m scripts.cleanup.update_sheet_keys --execute
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

from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.adapters.repositories.synth_pm_repository import (
    SynthPMRepository,
)


def _build_key_mapping() -> Dict[str, str]:
    """Build a complete old_key -> new_key mapping from cleanup reports.

    Returns:
        Dictionary mapping deleted/renamed keys to their replacements.
    """
    mapping: Dict[str, str] = {}

    cleanup_path = Path("data/cleanup_report.json")
    if cleanup_path.exists():
        report = json.loads(cleanup_path.read_text())

        for group in report.get("duplicate_stories", []):
            original = group["original"]
            for dup in group["duplicates"]:
                mapping[dup] = original

        for group in report.get("duplicate_epics", []):
            original = group["original"]
            for dup in group["duplicates"]:
                mapping[dup] = original

    reparent_path = Path("data/reparent_report.json")
    if reparent_path.exists():
        reparent = json.loads(reparent_path.read_text())
        for old_key, new_key in reparent.get("moved", {}).items():
            mapping[old_key] = new_key

    return mapping


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    key_mapping = _build_key_mapping()
    print(f"Built key mapping: {len(key_mapping)} deletd/renamed keys")

    container = get_container()
    synth_repo = container[SynthPMRepository]

    features = await synth_repo.get_developer_board_features()
    print(f"Loaded {len(features)} features from Google Sheet")

    updates_needed: List[Tuple[int, str, str, str]] = []

    for feature in features:
        old_key = feature.developer_board_issue_key
        if old_key and old_key in key_mapping:
            new_key = key_mapping[old_key]
            updates_needed.append((
                feature.sheet_row_number,
                old_key,
                new_key,
                feature.task_title or "(no title)",
            ))

    print(f"\n{'=' * 70}")
    print(f"SHEET UPDATES NEEDED: {len(updates_needed)}")
    print(f"{'=' * 70}")

    for row_num, old_key, new_key, title in updates_needed:
        print(f"  Row {row_num}: {old_key} -> {new_key}  ({title[:60]})")

    if not updates_needed:
        print("\nNo updates needed — sheet is clean.")
        return

    if not args.execute:
        print(f"\nDry-run complete. Use --execute to apply {len(updates_needed)} updates.")
        return

    print(f"\n--- EXECUTING {len(updates_needed)} sheet updates ---")
    success_count = 0
    fail_count = 0

    for row_num, old_key, new_key, title in updates_needed:
        try:
            result = await synth_repo.update_developer_board_feature(
                row_num,
                {"developer_board_issue_key": new_key},
            )
            if result:
                print(f"  OK   Row {row_num}: {old_key} -> {new_key}")
                success_count += 1
            else:
                print(f"  FAIL Row {row_num}: {old_key} -> {new_key}")
                fail_count += 1
        except Exception as exc:
            print(f"  ERROR Row {row_num}: {old_key} -> {new_key}: {exc}")
            fail_count += 1

    print(f"\nDone: {success_count} updated, {fail_count} failed")


if __name__ == "__main__":
    asyncio.run(main())
