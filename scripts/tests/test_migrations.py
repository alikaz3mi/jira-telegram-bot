"""Test script for database migrations."""
from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.database.migration_runner import MigrationRunner
from jira_telegram_bot.adapters.repositories.postgres.jira_report_repository import (
    JiraReportRepository,
)
from jira_telegram_bot.settings.postgre_db_settings import PostgresSettings


def main():
    """Test migration system."""
    try:
        LOGGER.info("Testing database migration system")

        # Initialize settings
        settings = PostgresSettings()

        # Create repository (this will run migrations)
        repo = JiraReportRepository(settings)

        # Test migration runner directly
        migration_runner = MigrationRunner(repo._engine)

        # Get migration status
        status = migration_runner.get_migration_status()

        LOGGER.info(f"Migration status: {status}")
        LOGGER.info(f"Total migrations available: {status['total_available']}")
        LOGGER.info(f"Total migrations applied: {status['total_applied']}")

        if status["applied"]:
            LOGGER.info("Applied migrations:")
            for migration in status["applied"]:
                LOGGER.info(f"  - {migration['version']}: {migration['description']}")

        if status["pending"]:
            LOGGER.info("Pending migrations:")
            for migration in status["pending"]:
                LOGGER.info(f"  - {migration['version']}: {migration['description']}")

        LOGGER.info("Migration system test completed successfully")

    except Exception as e:
        LOGGER.error(f"Migration system test failed: {e}")
        raise


if __name__ == "__main__":
    main()
