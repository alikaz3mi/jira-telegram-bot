#!/usr/bin/env python3
"""Run migration 011 to add actual_start_date and actual_end_date columns to jira_tasks_enhanced."""
from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_runner import (
    MigrationRunner,
)
from jira_telegram_bot.adapters.repositories.postgres.database.postgresql_connection import (
    PostgreSQLConnection,
)
from jira_telegram_bot.settings.postgre_db_settings import PostgresSettings


def main() -> None:
    """Run migration 011."""
    LOGGER.info("Starting migration 011: Add actual_start_date and actual_end_date")

    settings = PostgresSettings()
    db_connection = PostgreSQLConnection(settings)
    engine = db_connection.get_engine()

    runner = MigrationRunner(engine)

    try:
        runner.run_pending_migrations()
        LOGGER.info("Migration 011 completed successfully")
    except Exception as e:
        LOGGER.error(f"Migration 011 failed: {e}")
        raise


if __name__ == "__main__":
    main()
