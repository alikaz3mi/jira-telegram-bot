"""Script to find and remove duplicate empty sprints from Jira boards."""
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot import LOGGER


def find_duplicate_empty_sprints(
    jira_repository: TaskManagerRepositoryInterface,
    board_key: str,
) -> dict:
    """Find duplicate sprints and identify which are empty.

    Args:
        jira_repository: Jira repository instance
        board_key: Board key to scan

    Returns:
        Dictionary with sprint analysis results
    """
    board_id = jira_repository.get_board_id(board_key)
    if not board_id:
        LOGGER.error(f"Board '{board_key}' not found")
        return {}

    LOGGER.info(f"Scanning board '{board_key}' (ID: {board_id}) for sprints...")
    sprints = jira_repository.get_sprints(board_id, get_from_cache=False)
    LOGGER.info(f"Found {len(sprints)} total sprints")

    sprints_by_name = defaultdict(list)
    for sprint in sprints:
        sprints_by_name[sprint.name].append(sprint)

    duplicates = {
        name: sprint_list
        for name, sprint_list in sprints_by_name.items()
        if len(sprint_list) > 1
    }

    LOGGER.info(f"Found {len(duplicates)} sprint names with duplicates")

    results = {
        "board_key": board_key,
        "board_id": board_id,
        "total_sprints": len(sprints),
        "duplicate_groups": len(duplicates),
        "sprints_to_delete": [],
        "empty_sprints_no_duplicate": [],
    }

    for name, sprint_list in duplicates.items():
        LOGGER.info(f"\nDuplicate sprint name: '{name}' ({len(sprint_list)} copies)")
        for sprint in sprint_list:
            issue_count = _count_sprint_issues(jira_repository, sprint, board_key)
            LOGGER.info(
                f"  Sprint ID: {sprint.id}, State: {sprint.state}, "
                f"Issues: {issue_count}"
            )

        sprint_list_sorted = sorted(
            sprint_list,
            key=lambda s: _count_sprint_issues(jira_repository, s, board_key),
            reverse=True,
        )

        kept = False
        for sprint in sprint_list_sorted:
            issue_count = _count_sprint_issues(jira_repository, sprint, board_key)
            if not kept:
                LOGGER.info(f"  KEEP: Sprint ID {sprint.id} ({issue_count} issues)")
                kept = True
            else:
                if issue_count == 0:
                    results["sprints_to_delete"].append({
                        "id": sprint.id,
                        "name": sprint.name,
                        "state": sprint.state,
                        "issues": issue_count,
                    })
                    LOGGER.info(f"  DELETE: Sprint ID {sprint.id} (empty duplicate)")
                else:
                    LOGGER.info(
                        f"  SKIP: Sprint ID {sprint.id} ({issue_count} issues - has tasks)"
                    )

    for name, sprint_list in sprints_by_name.items():
        if len(sprint_list) == 1:
            sprint = sprint_list[0]
            issue_count = _count_sprint_issues(jira_repository, sprint, board_key)
            if issue_count == 0 and sprint.state == "future":
                results["empty_sprints_no_duplicate"].append({
                    "id": sprint.id,
                    "name": sprint.name,
                    "state": sprint.state,
                    "issues": issue_count,
                })

    return results


def _count_sprint_issues(
    jira_repository: TaskManagerRepositoryInterface,
    sprint: object,
    board_key: str,
) -> int:
    """Count the number of issues in a sprint.

    Args:
        jira_repository: Jira repository instance
        sprint: Sprint object
        board_key: Board/project key

    Returns:
        Number of issues in the sprint
    """
    try:
        jql = f'project = "{board_key}" AND sprint = {sprint.id}'
        issues = jira_repository.search_issues(jql, max_results=1)
        return len(issues)
    except Exception as e:
        LOGGER.warning(f"Error counting issues for sprint {sprint.id}: {e}")
        return -1


def delete_sprints(
    jira_repository: TaskManagerRepositoryInterface,
    sprints_to_delete: list,
) -> int:
    """Delete empty duplicate sprints via Jira REST API.

    Args:
        jira_repository: Jira repository instance
        sprints_to_delete: List of sprint dicts to delete

    Returns:
        Number of sprints deleted
    """
    deleted = 0
    for sprint_info in sprints_to_delete:
        try:
            sprint_id = sprint_info["id"]
            LOGGER.info(
                f"Deleting sprint {sprint_id} ('{sprint_info['name']}', "
                f"state: {sprint_info['state']})"
            )
            url = f"{jira_repository.jira._options['server']}/rest/agile/1.0/sprint/{sprint_id}"
            response = jira_repository.jira._session.delete(url)
            if response.status_code in (200, 204):
                deleted += 1
                LOGGER.info(f"Successfully deleted sprint {sprint_id}")
            else:
                LOGGER.error(
                    f"Failed to delete sprint {sprint_id}: "
                    f"HTTP {response.status_code} - {response.text}"
                )
        except Exception as e:
            LOGGER.error(f"Failed to delete sprint {sprint_id}: {e}")
    return deleted


def main():
    """Run the duplicate sprint cleanup."""
    container = get_container()
    jira_repository = container[TaskManagerRepositoryInterface]

    board_keys = ["PARSCHAT", "FollowUpper"]

    for board_key in board_keys:
        LOGGER.info(f"\n{'='*60}")
        LOGGER.info(f"Analyzing board: {board_key}")
        LOGGER.info(f"{'='*60}")

        results = find_duplicate_empty_sprints(jira_repository, board_key)

        if not results:
            continue

        LOGGER.info(f"\n--- Summary for {board_key} ---")
        LOGGER.info(f"Total sprints: {results['total_sprints']}")
        LOGGER.info(f"Duplicate groups: {results['duplicate_groups']}")
        LOGGER.info(f"Sprints to delete: {len(results['sprints_to_delete'])}")
        LOGGER.info(
            f"Empty non-duplicate future sprints: "
            f"{len(results['empty_sprints_no_duplicate'])}"
        )

        if results["empty_sprints_no_duplicate"]:
            LOGGER.info("\nEmpty future sprints (no duplicates):")
            for sprint_info in results["empty_sprints_no_duplicate"]:
                LOGGER.info(
                    f"  {sprint_info['name']} (ID: {sprint_info['id']}, "
                    f"State: {sprint_info['state']})"
                )

        if results["sprints_to_delete"]:
            LOGGER.info(f"\nDeleting {len(results['sprints_to_delete'])} empty duplicate sprints...")
            deleted = delete_sprints(jira_repository, results["sprints_to_delete"])
            LOGGER.info(f"Deleted {deleted} sprints")
        else:
            LOGGER.info("No duplicate empty sprints to delete")


if __name__ == "__main__":
    main()
