"""Backfill reviewed_at column for existing issues."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import (
    DatabaseConnectionInterface,
)
from sqlalchemy import text


def backfill_reviewed_at() -> None:
    """Update reviewed_at column for existing issues based on status history.
    
    This queries the jira_status_history table to find the most recent
    transition to 'Review' status for each issue and updates the
    jira_tasks_enhanced table accordingly.
    """
    LOGGER.info("Starting reviewed_at backfill process")

    container = get_container()
    database_connection = container[DatabaseConnectionInterface]
    engine = database_connection.get_engine()

    with engine.connect() as connection:
        LOGGER.info("Updating reviewed_at from status history")
        
        result = connection.execute(
            text(
                """
                UPDATE jira_tasks_enhanced t
                SET reviewed_at = subquery.max_changed_at
                FROM (
                    SELECT 
                        issue_key,
                        MAX(changed_at) as max_changed_at
                    FROM jira_status_history
                    WHERE to_status = 'Review'
                    GROUP BY issue_key
                ) subquery
                WHERE t.key = subquery.issue_key
                  AND t.reviewed_at IS NULL
                """
            )
        )
        connection.commit()
        
        rows_updated = result.rowcount
        LOGGER.info(f"Updated {rows_updated} issues with reviewed_at timestamp")

        LOGGER.info("Querying total issues with reviewed_at")
        result = connection.execute(
            text(
                "SELECT COUNT(*) FROM jira_tasks_enhanced WHERE reviewed_at IS NOT NULL"
            )
        )
        total_with_reviewed = result.scalar()
        LOGGER.info(f"Total issues with reviewed_at: {total_with_reviewed}")

        LOGGER.info("Querying total Review status transitions")
        result = connection.execute(
            text(
                "SELECT COUNT(DISTINCT issue_key) FROM jira_status_history "
                "WHERE to_status = 'Review'"
            )
        )
        total_review_transitions = result.scalar()
        LOGGER.info(f"Total distinct issues with Review transitions: {total_review_transitions}")

    LOGGER.info("Backfill completed successfully")


if __name__ == "__main__":
    try:
        backfill_reviewed_at()
    except Exception as e:
        LOGGER.error(f"Backfill failed: {e}")
        sys.exit(1)
