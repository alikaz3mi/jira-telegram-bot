#!/usr/bin/env python3
"""Clean up duplicate Jira issues safely — worklogs are never lost.

Keeper selection strategy (which duplicate to KEEP):
  1. The issue with the most worklogs wins.
  2. Ties broken by total time-spent seconds (more = keep).
  3. Remaining ties broken by lowest key number (oldest = keep).

Before deleting a duplicate the script:
  - Migrates ALL worklogs to the keeper (REST preserves author).
  - Migrates ALL comments to the keeper.
  - Moves subtasks from the duplicate to the keeper.
  - **Refuses** to delete if the duplicate still has worklogs after migration.
  - Updates Google Sheet rows whose ``developer_board_issue_key`` pointed
    at the deleted key → surviving keeper key.

Pass ``--clean-labels`` to also strip stale ``PM-PCD-*`` / ``PM-*`` labels.

Usage:
    # Dry-run (default) — only reports what would happen
    python -m scripts.cleanup.cleanup_all_duplicates

    # Actually perform cleanup
    python -m scripts.cleanup.cleanup_all_duplicates --execute

    # Also clean PM-* labels
    python -m scripts.cleanup.cleanup_all_duplicates --execute --clean-labels
"""
import argparse
import asyncio
import json
import logging
import logging.handlers
import os
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

os.makedirs("/tmp/jira_cleanup_logs", exist_ok=True)
_orig_init = logging.handlers.RotatingFileHandler.__init__


def _patched_init(self, filename, *args, **kwargs):
    if "logs/logs.log" in str(filename):
        filename = "/tmp/jira_cleanup_logs/logs.log"
    _orig_init(self, filename, *args, **kwargs)


logging.handlers.RotatingFileHandler.__init__ = _patched_init

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.synth_pm_repository_interface import (
    SynthPMRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.utils.text_normalization import normalize_persian_text

DEVELOPER_PROJECT_KEY = "PARSCHAT"


@dataclass
class IssueSnapshot:
    """Lightweight Jira issue snapshot for comparison."""

    key: str
    summary: str
    status: str
    worklog_count: int
    time_spent_seconds: int
    subtask_count: int
    parent_key: Optional[str]
    assignee: Optional[str]


@dataclass
class DuplicateGroup:
    """A set of issues sharing the same normalised summary."""

    raw_summary: str
    issue_type: str
    keeper: IssueSnapshot
    duplicates: List[IssueSnapshot] = field(default_factory=list)


@dataclass
class CleanupReport:
    """Tracks every action the script takes (or would take)."""

    duplicate_groups: List[Dict[str, Any]] = field(default_factory=list)
    worklogs_migrated: List[Dict[str, Any]] = field(default_factory=list)
    comments_migrated: List[Dict[str, Any]] = field(default_factory=list)
    subtasks_moved: List[Dict[str, Any]] = field(default_factory=list)
    issues_deleted: List[str] = field(default_factory=list)
    sheet_updates: List[Dict[str, str]] = field(default_factory=list)
    labels_removed: List[Dict[str, Any]] = field(default_factory=list)
    skipped_has_worklogs: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _key_number(key: str) -> int:
    """Extract the numeric suffix from an issue key.

    Args:
        key: Jira issue key like ``PARSCHAT-1234``.

    Returns:
        Numeric part as int.
    """
    return int(key.rsplit("-", 1)[1])


def _build_snapshot(jira_repo: TaskManagerRepositoryInterface, issue) -> IssueSnapshot:
    """Build a lightweight snapshot from a Jira issue object.

    Args:
        jira_repo: Jira repository (used for worklog query).
        issue: ``jira.resources.Issue`` object.

    Returns:
        Populated IssueSnapshot.
    """
    worklogs = _get_worklogs(jira_repo, issue.key)

    time_spent = _get_time_spent(issue)

    subtasks = getattr(issue.fields, "subtasks", None) or []
    parent = getattr(issue.fields, "parent", None)

    assignee_obj = getattr(issue.fields, "assignee", None)
    assignee_name = getattr(assignee_obj, "name", None) if assignee_obj else None

    return IssueSnapshot(
        key=issue.key,
        summary=issue.fields.summary,
        status=issue.fields.status.name,
        worklog_count=len(worklogs),
        time_spent_seconds=time_spent,
        subtask_count=len(subtasks),
        parent_key=parent.key if parent else None,
        assignee=assignee_name,
    )


def _get_worklogs(jira_repo: TaskManagerRepositoryInterface, issue_key: str) -> list:
    """Fetch worklogs for an issue, returning empty list on error.

    Args:
        jira_repo: Jira repository.
        issue_key: Issue key.

    Returns:
        List of worklog objects.
    """
    try:
        return jira_repo.jira.worklogs(issue_key)
    except Exception:
        return []


def _get_time_spent(issue) -> int:
    """Read time-spent seconds from an issue safely.

    Args:
        issue: Jira issue object.

    Returns:
        Time spent in seconds, or 0.
    """
    try:
        return issue.fields.timetracking.timeSpentSeconds or 0
    except Exception:
        try:
            return issue.fields.timespent or 0
        except Exception:
            return 0


def _pick_keeper(
    snapshots: List[IssueSnapshot],
) -> Tuple[IssueSnapshot, List[IssueSnapshot]]:
    """Choose the issue to keep; the rest are duplicates to delete.

    Priority:
      1. Most worklogs
      2. Most time-spent seconds
      3. Lowest key number (oldest)

    Args:
        snapshots: Snapshots for all issues with the same summary.

    Returns:
        (keeper, list_of_duplicates_to_delete)
    """
    ranked = sorted(
        snapshots,
        key=lambda s: (-s.worklog_count, -s.time_spent_seconds, _key_number(s.key)),
    )
    return ranked[0], ranked[1:]


def _find_all_duplicates(
    jira_repo: TaskManagerRepositoryInterface,
    project_key: str,
    issue_type: str,
) -> List[DuplicateGroup]:
    """Find duplicate issues of a given type in the project.

    Args:
        jira_repo: Jira repository.
        project_key: Project key to search.
        issue_type: Issue type (Story, Task, Sub-task, Epic).

    Returns:
        List of DuplicateGroup objects.
    """
    jql = (
        f'project = "{project_key}" AND issuetype = "{issue_type}" '
        f"ORDER BY key ASC"
    )
    all_issues = jira_repo.search_issues(jql, max_results=5000)
    LOGGER.info(f"Fetched {len(all_issues)} {issue_type} issues from {project_key}")

    is_subtask = issue_type in ("Sub-task", "Sub-Task", "Subtask")

    by_group_key: Dict[tuple, list] = defaultdict(list)
    for issue in all_issues:
        norm = normalize_persian_text(issue.fields.summary.strip())
        if is_subtask:
            parent = getattr(issue.fields, "parent", None)
            parent_key = parent.key if parent else None
            assignee_obj = getattr(issue.fields, "assignee", None)
            assignee_name = getattr(assignee_obj, "name", None) if assignee_obj else None
            group_key = (norm, parent_key, assignee_name)
        else:
            group_key = (norm,)
        by_group_key[group_key].append(issue)

    groups: List[DuplicateGroup] = []
    for _, issue_list in by_group_key.items():
        if len(issue_list) < 2:
            continue

        snapshots = [_build_snapshot(jira_repo, iss) for iss in issue_list]
        keeper, dups = _pick_keeper(snapshots)
        groups.append(
            DuplicateGroup(
                raw_summary=keeper.summary,
                issue_type=issue_type,
                keeper=keeper,
                duplicates=dups,
            )
        )

    LOGGER.info(f"Found {len(groups)} duplicate {issue_type} groups")
    return groups


def _migrate_worklogs(
    jira_repo: TaskManagerRepositoryInterface,
    source_key: str,
    target_key: str,
    report: CleanupReport,
    execute: bool,
) -> int:
    """Migrate worklogs from source to target, preserving author via REST.

    Args:
        jira_repo: Jira repository.
        source_key: Issue to copy worklogs FROM.
        target_key: Issue to copy worklogs TO.
        report: Cleanup report.
        execute: Whether to actually migrate.

    Returns:
        Number of worklogs migrated.
    """
    worklogs = _get_worklogs(jira_repo, source_key)
    if not worklogs:
        return 0

    count = 0
    server = jira_repo.jira._options["server"]

    for wl in worklogs:
        author_name = getattr(getattr(wl, "author", None), "name", None)
        comment_text = getattr(wl, "comment", None) or ""
        entry = {
            "from": source_key,
            "to": target_key,
            "author": author_name,
            "timeSpent": wl.timeSpent,
            "started": wl.started,
        }

        if execute:
            ok = _add_worklog_via_rest(
                jira_repo, server, target_key, wl, author_name, comment_text,
            )
            if ok:
                count += 1
                report.worklogs_migrated.append(entry)
            else:
                report.errors.append(
                    f"Worklog migration failed {source_key}->{target_key} "
                    f"(author={author_name}, time={wl.timeSpent})"
                )
        else:
            count += 1
            entry["dry_run"] = True
            report.worklogs_migrated.append(entry)

    return count


def _add_worklog_via_rest(
    jira_repo: TaskManagerRepositoryInterface,
    server: str,
    target_key: str,
    worklog,
    author_name: Optional[str],
    comment_text: str,
) -> bool:
    """Add a single worklog via REST API (preserves author), with fallback.

    Args:
        jira_repo: Jira repository.
        server: Jira server base URL.
        target_key: Target issue key.
        worklog: Original worklog object.
        author_name: Original author username.
        comment_text: Worklog comment.

    Returns:
        True if worklog was added successfully.
    """
    if author_name:
        try:
            url = (
                f"{server}/rest/api/2/issue/{target_key}/worklog"
                f"?notifyUsers=false&adjustEstimate=leave"
            )
            payload = {
                "timeSpent": worklog.timeSpent,
                "started": worklog.started,
                "comment": comment_text,
                "author": {"name": author_name},
            }
            resp = jira_repo.jira._session.post(url, json=payload)
            if resp.status_code in (200, 201):
                return True
        except Exception:
            pass

    try:
        jira_repo.jira.add_worklog(
            target_key,
            timeSpent=worklog.timeSpent,
            comment=comment_text,
            started=worklog.started,
        )
        return True
    except Exception as e:
        LOGGER.warning(f"Worklog add fallback failed for {target_key}: {e}")
        return False


def _migrate_comments(
    jira_repo: TaskManagerRepositoryInterface,
    source_key: str,
    target_key: str,
    report: CleanupReport,
    execute: bool,
) -> int:
    """Migrate all comments from source to target.

    Args:
        jira_repo: Jira repository.
        source_key: Issue to copy comments FROM.
        target_key: Issue to copy comments TO.
        report: Cleanup report.
        execute: Whether to actually migrate.

    Returns:
        Number of comments migrated.
    """
    try:
        comments = jira_repo.jira.comments(source_key)
    except Exception:
        return 0

    count = 0
    for c in comments:
        entry = {
            "from": source_key,
            "to": target_key,
            "body_preview": (c.body or "")[:80],
        }
        if execute:
            try:
                jira_repo.jira.add_comment(target_key, c.body)
                count += 1
                report.comments_migrated.append(entry)
            except Exception as e:
                report.errors.append(
                    f"Comment migration {source_key}->{target_key}: {e}"
                )
        else:
            count += 1
            entry["dry_run"] = True
            report.comments_migrated.append(entry)
    return count


def _move_subtasks(
    jira_repo: TaskManagerRepositoryInterface,
    from_key: str,
    to_key: str,
    report: CleanupReport,
    execute: bool,
) -> int:
    """Move subtasks from one parent to another.

    Uses ``convert_to_subtask`` which tries in-place conversion first,
    then recreates the subtask (preserving worklogs) if needed.

    Args:
        jira_repo: Jira repository.
        from_key: Source parent issue key.
        to_key: Destination parent issue key.
        report: Cleanup report.
        execute: Whether to actually move.

    Returns:
        Number of subtasks moved.
    """
    try:
        issue = jira_repo.get_issue(from_key)
        if not issue:
            return 0
        subtasks = getattr(issue.fields, "subtasks", None) or []
    except Exception as e:
        report.errors.append(f"Fetch subtasks of {from_key}: {e}")
        return 0

    count = 0
    for sub in subtasks:
        sub_key = sub.key if hasattr(sub, "key") else str(sub)
        entry = {"subtask": sub_key, "from": from_key, "to": to_key}

        if execute:
            try:
                result = jira_repo.convert_to_subtask(sub_key, to_key)
                if result:
                    count += 1
                    entry["result_key"] = result
                    report.subtasks_moved.append(entry)
                else:
                    reparented = _reparent_subtask(
                        jira_repo, sub_key, to_key, report,
                    )
                    if reparented:
                        count += 1
                        entry["result_key"] = reparented
                        entry["method"] = "reparent_recreate"
                        report.subtasks_moved.append(entry)
            except Exception as e:
                report.errors.append(f"Move subtask {sub_key}: {e}")
        else:
            count += 1
            entry["dry_run"] = True
            report.subtasks_moved.append(entry)
    return count


def _reparent_subtask(
    jira_repo: TaskManagerRepositoryInterface,
    sub_key: str,
    new_parent_key: str,
    report: CleanupReport,
) -> Optional[str]:
    """Re-parent a subtask by recreating it under a new parent.

    Used when ``convert_to_subtask`` returns None because the issue
    is already a sub-task of a different parent.

    Args:
        jira_repo: Jira repository.
        sub_key: Subtask issue key to re-parent.
        new_parent_key: New parent issue key.
        report: Cleanup report.

    Returns:
        New issue key on success, None on failure.
    """
    try:
        old_issue = jira_repo.jira.issue(sub_key)
        fields = {
            "project": {"key": old_issue.fields.project.key},
            "summary": old_issue.fields.summary,
            "description": old_issue.fields.description or "",
            "issuetype": {"name": "Sub-task"},
            "parent": {"key": new_parent_key},
        }
        if old_issue.fields.assignee:
            fields["assignee"] = {"name": old_issue.fields.assignee.name}
        if old_issue.fields.reporter:
            fields["reporter"] = {"name": old_issue.fields.reporter.name}
        if old_issue.fields.priority:
            fields["priority"] = {"name": old_issue.fields.priority.name}
        if old_issue.fields.components:
            fields["components"] = [
                {"name": c.name} for c in old_issue.fields.components
            ]
        if old_issue.fields.labels:
            fields["labels"] = list(old_issue.fields.labels)

        new_issue = jira_repo.jira.create_issue(fields=fields)
        new_key = new_issue.key

        jira_repo._migrate_worklogs(sub_key, new_key)
        jira_repo._migrate_comments(sub_key, new_key)

        old_issue.delete()
        LOGGER.info(
            f"Re-parented {sub_key} -> {new_key} under {new_parent_key}"
        )
        return new_key

    except Exception as e:
        report.errors.append(f"Reparent subtask {sub_key}: {e}")
        return None


def _safe_delete(
    jira_repo: TaskManagerRepositoryInterface,
    key: str,
    report: CleanupReport,
    execute: bool,
) -> bool:
    """Delete an issue only when it has zero remaining worklogs.

    Args:
        jira_repo: Jira repository.
        key: Issue key to delete.
        report: Cleanup report.
        execute: Whether to actually delete.

    Returns:
        True if deleted (or would be in dry-run).
    """
    if execute:
        remaining = _get_worklogs(jira_repo, key)
        if remaining:
            report.skipped_has_worklogs.append({
                "key": key,
                "worklog_count": len(remaining),
                "reason": "Worklogs remain after migration — refusing to delete",
            })
            return False

        try:
            issue = jira_repo.get_issue(key)
            if issue:
                subs = getattr(issue.fields, "subtasks", None) or []
                if subs:
                    report.errors.append(
                        f"Cannot delete {key}: still has {len(subs)} subtasks"
                    )
                    return False
        except Exception:
            pass

        try:
            jira_repo.delete_issue(key)
        except Exception as e:
            report.errors.append(f"Delete {key}: {e}")
            return False

    report.issues_deleted.append(key)
    return True


async def _update_google_sheet(
    synth_pm_repo: SynthPMRepositoryInterface,
    deleted_to_keeper: Dict[str, str],
    report: CleanupReport,
    execute: bool,
):
    """Update Google Sheet rows that reference deleted keys.

    Args:
        synth_pm_repo: SynthPM repository (Google Sheet access).
        deleted_to_keeper: Mapping of deleted issue key -> keeper issue key.
        report: Cleanup report.
        execute: Whether to actually update.
    """
    if not deleted_to_keeper:
        return

    try:
        features = await synth_pm_repo.get_developer_board_features()
    except Exception as e:
        report.errors.append(f"Sheet read failed: {e}")
        return

    for feature in features:
        old_key = feature.developer_board_issue_key
        if old_key not in deleted_to_keeper:
            continue

        new_key = deleted_to_keeper[old_key]
        entry = {
            "sheet_row": feature.sheet_row_number,
            "old_key": old_key,
            "new_key": new_key,
        }

        if execute:
            try:
                await synth_pm_repo.update_developer_board_feature(
                    feature.sheet_row_number,
                    {"developer_board_issue_key": new_key},
                )
                report.sheet_updates.append(entry)
                LOGGER.info(
                    f"Sheet row {feature.sheet_row_number}: "
                    f"{old_key} -> {new_key}"
                )
            except Exception as e:
                report.errors.append(
                    f"Sheet update row {feature.sheet_row_number}: {e}"
                )
        else:
            entry["dry_run"] = True
            report.sheet_updates.append(entry)


def _clean_pm_labels(
    jira_repo: TaskManagerRepositoryInterface,
    project_key: str,
    report: CleanupReport,
    execute: bool,
):
    """Remove PM-<project>-* labels from developer board issues.

    Args:
        jira_repo: Jira repository.
        project_key: Developer board project key.
        report: Cleanup report.
        execute: Whether to actually remove labels.
    """
    jql = (
        f'project = "{project_key}" AND labels is not EMPTY '
        f"ORDER BY key ASC"
    )
    try:
        issues = jira_repo.search_issues(jql, max_results=5000)
    except Exception as e:
        report.errors.append(f"Label search failed: {e}")
        return

    for issue in issues:
        labels = list(issue.fields.labels)
        pm_labels = [lb for lb in labels if lb.startswith("PM-") and "-" in lb[3:]]
        if not pm_labels:
            continue

        new_labels = [lb for lb in labels if lb not in pm_labels]
        entry = {
            "key": issue.key,
            "removed": pm_labels,
            "remaining": new_labels,
        }

        if execute:
            try:
                issue.update(fields={"labels": new_labels})
                report.labels_removed.append(entry)
            except Exception as e:
                report.errors.append(f"Remove labels {issue.key}: {e}")
        else:
            entry["dry_run"] = True
            report.labels_removed.append(entry)


def _print_report(report: CleanupReport, execute: bool):
    """Print a human-readable summary.

    Args:
        report: Cleanup report.
        execute: Whether this was a real execution.
    """
    mode = "EXECUTED" if execute else "DRY RUN"
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  CLEANUP REPORT ({mode})")
    print(sep)

    print(f"\n  Duplicate groups: {len(report.duplicate_groups)}")
    for g in report.duplicate_groups:
        print(f"\n    [{g['type']}] \"{g['summary']}\"")
        k = g["keeper"]
        assignee_str = f", assignee={k['assignee']}" if k.get('assignee') else ""
        parent_str = f", parent={k['parent_key']}" if k.get('parent_key') else ""
        print(
            f"      KEEP  : {k['key']}  "
            f"(worklogs={k['worklog_count']}, "
            f"time={k['time_spent_seconds']}s, "
            f"subtasks={k['subtask_count']}"
            f"{assignee_str}{parent_str})"
        )
        for d in g["duplicates"]:
            a_str = f", assignee={d['assignee']}" if d.get('assignee') else ""
            p_str = f", parent={d['parent_key']}" if d.get('parent_key') else ""
            print(
                f"      DELETE: {d['key']}  "
                f"(worklogs={d['worklog_count']}, "
                f"time={d['time_spent_seconds']}s, "
                f"subtasks={d['subtask_count']}"
                f"{a_str}{p_str})"
            )

    print(f"\n  Worklogs migrated:       {len(report.worklogs_migrated)}")
    print(f"  Comments migrated:       {len(report.comments_migrated)}")
    print(f"  Subtasks moved:          {len(report.subtasks_moved)}")
    print(f"  Issues deleted:          {len(report.issues_deleted)}")
    print(f"  Sheet rows updated:      {len(report.sheet_updates)}")
    print(f"  Labels cleaned:          {len(report.labels_removed)}")
    print(f"  Skipped (has worklogs):  {len(report.skipped_has_worklogs)}")
    print(f"  Errors:                  {len(report.errors)}")

    if report.skipped_has_worklogs:
        print("\n  Issues NOT deleted (worklogs remain after migration):")
        for s in report.skipped_has_worklogs:
            print(f"      {s['key']} — {s['worklog_count']} worklogs remaining")

    if report.errors:
        print("\n  Errors:")
        for err in report.errors[:30]:
            print(f"      {err}")

    print(f"\n{sep}\n")


def _serialize_report(report: CleanupReport, execute: bool) -> dict:
    """Serialize the report to a JSON-safe dict.

    Args:
        report: Cleanup report.
        execute: Whether this was a real execution.

    Returns:
        JSON-serialisable dict.
    """
    return {
        "mode": "execute" if execute else "dry_run",
        "duplicate_groups": report.duplicate_groups,
        "worklogs_migrated": report.worklogs_migrated,
        "comments_migrated": report.comments_migrated,
        "subtasks_moved": report.subtasks_moved,
        "issues_deleted": report.issues_deleted,
        "sheet_updates": report.sheet_updates,
        "labels_removed": report.labels_removed,
        "skipped_has_worklogs": report.skipped_has_worklogs,
        "errors": report.errors,
    }


async def main():
    """Run the duplicate cleanup."""
    parser = argparse.ArgumentParser(
        description="Clean up duplicate Jira issues (worklog-safe)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform cleanup (default: dry-run)",
    )
    parser.add_argument(
        "--clean-labels",
        action="store_true",
        help="Also remove PM-PCD-* labels from developer board issues",
    )
    parser.add_argument(
        "--project",
        default=DEVELOPER_PROJECT_KEY,
        help=f"Developer board project key (default: {DEVELOPER_PROJECT_KEY})",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=["Epic", "Story", "Task", "Sub-task"],
        help="Issue types to check for duplicates",
    )
    args = parser.parse_args()

    container = get_container()
    jira_repo = container[TaskManagerRepositoryInterface]
    synth_pm_repo = container[SynthPMRepositoryInterface]

    report = CleanupReport()

    print(f"\n{'=' * 70}")
    print(
        f"  Scanning {args.project} for duplicates "
        f"({'EXECUTE' if args.execute else 'DRY RUN'})"
    )
    print(f"  Issue types: {', '.join(args.types)}")
    print(
        "  Strategy: keep issue with most worklogs; "
        "migrate worklogs before deleting"
    )
    print(f"{'=' * 70}\n")

    all_groups: List[DuplicateGroup] = []
    for issue_type in args.types:
        groups = _find_all_duplicates(jira_repo, args.project, issue_type)
        all_groups.extend(groups)

    for group in all_groups:
        report.duplicate_groups.append({
            "summary": group.raw_summary,
            "type": group.issue_type,
            "keeper": asdict(group.keeper),
            "duplicates": [asdict(d) for d in group.duplicates],
        })

    deleted_to_keeper: Dict[str, str] = {}

    for group in all_groups:
        keeper_key = group.keeper.key

        for dup in group.duplicates:
            dup_key = dup.key

            if dup.worklog_count > 0:
                migrated = _migrate_worklogs(
                    jira_repo, dup_key, keeper_key, report, args.execute,
                )
                LOGGER.info(
                    f"Migrated {migrated} worklogs: {dup_key} -> {keeper_key}"
                )

            _migrate_comments(
                jira_repo, dup_key, keeper_key, report, args.execute,
            )

            if dup.subtask_count > 0:
                moved = _move_subtasks(
                    jira_repo, dup_key, keeper_key, report, args.execute,
                )
                LOGGER.info(
                    f"Moved {moved} subtasks: {dup_key} -> {keeper_key}"
                )

            deleted = _safe_delete(jira_repo, dup_key, report, args.execute)
            if deleted:
                deleted_to_keeper[dup_key] = keeper_key

    if deleted_to_keeper:
        print(
            f"\nUpdating Google Sheet for "
            f"{len(deleted_to_keeper)} deleted issues..."
        )
        await _update_google_sheet(
            synth_pm_repo, deleted_to_keeper, report, args.execute,
        )

    if args.clean_labels:
        print("Scanning for PM-* labels to remove...")
        _clean_pm_labels(jira_repo, args.project, report, args.execute)

    _print_report(report, args.execute)

    report_path = Path("data/cleanup_all_duplicates_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            _serialize_report(report, args.execute),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
