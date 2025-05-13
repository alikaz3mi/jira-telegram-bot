from __future__ import annotations

from typing import Dict
from typing import List

from jira import Issue
from jira.exceptions import JIRAError

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import JiraServerRepository


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

PROJECT_KEY = "PARSCHAT"  # ← board / project you want to touch
MAX_RESULTS = 1_000  # jira‘s REST default is 50 – bump it up
BATCH_LOG_EVERY = 20  # how often to log progress

# numeric priority‑ID → new human‑readable name
PRIORITY_REMAP: Dict[str, str] = {
    "ONE": "High",
    "TWO": "Medium",
    "THREE": "Low",
    "FOUR": "Lowest",
    "FIVE": "Lowest",
    "SIX": "Lowest",
    "SEVEN": "Lowest",
}


# --------------------------------------------------------------------------- #
# Helper
# --------------------------------------------------------------------------- #


def _build_target_priority_id_map(repo: JiraServerRepository) -> Dict[str, str]:
    """
    Return a dict  {priority_name (case‑insensitive) -> priority_id}  that
    reflects the priorities actually configured on the JIRA instance.
    """
    id_by_name = {}
    for prio in repo.get_priorities():
        id_by_name[prio.name.lower()] = prio.id  # prio.id is a string
    return id_by_name


# --------------------------------------------------------------------------- #
# Main worker
# --------------------------------------------------------------------------- #


def update_priorities_for_board(repo: JiraServerRepository, project_key: str) -> None:
    """Fetch all issues on *project_key* and remap their priority in‑place."""
    LOGGER.info("Loading priorities configured on the server …")
    target_name_to_id = _build_target_priority_id_map(repo)

    # Validate mapping: every *new* name in PRIORITY_REMAP must exist
    missing = [
        name
        for name in PRIORITY_REMAP.values()
        if name.lower() not in target_name_to_id
    ]
    if missing:
        raise RuntimeError(
            f"The following priorities are not defined in Jira: {missing}",
        )

    LOGGER.info("Fetching issues for %s …", project_key)
    jql = f'project = "{project_key}"'
    issues: List[Issue] = repo.search_for_issues(jql, max_results=MAX_RESULTS)

    if not issues:
        LOGGER.warning("No issues found for %s – nothing to do.", project_key)
        return

    LOGGER.info("Processing %d issues …", len(issues))
    updated, skipped, errors = 0, 0, 0

    for idx, issue in enumerate(issues, 1):
        old_prio_obj = issue.fields.priority
        if old_prio_obj is None:
            skipped += 1
            continue

        # Decide the *new* priority name we want
        new_prio_name = PRIORITY_REMAP.get(old_prio_obj.name)
        if not new_prio_name:
            skipped += 1  # current priority not in the numeric 1‑4 range
            continue

        # Skip if nothing would change
        if new_prio_name.lower() == old_prio_obj.name.lower():
            skipped += 1
            continue

        try:
            issue.update(
                fields={
                    "priority": {"name": new_prio_name},
                },
            )
            updated += 1
        except JIRAError as exc:
            LOGGER.error("Failed updating %s: %s", issue.key, exc.text)
            errors += 1

        if idx % BATCH_LOG_EVERY == 0:
            LOGGER.info("…%d / %d done", idx, len(issues))
            LOGGER.info(
                f"Finished: {updated} updated, {skipped} skipped, {errors} errors (total {len(issues)})",
            )


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    repo = JiraServerRepository()  # credentials & domain come from JIRA_SETTINGS
    update_priorities_for_board(repo, PROJECT_KEY)
