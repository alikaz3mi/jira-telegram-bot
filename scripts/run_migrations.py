"""Database migration script."""
from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_runner import MigrationRunner
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface


def main() -> None:
    """Run database migrations."""
    try:
        LOGGER.info("Starting database migrations")
        
        # Get database connection from container
        container = get_container()
        database_connection = container[DatabaseConnectionInterface]
        
        # Get database engine   
        engine = database_connection.get_engine()
        
        # Run migrations
        migration_runner = MigrationRunner(engine)
        status = migration_runner.get_migration_status()
        
        LOGGER.info(f"Migration status: {status['total_applied']} applied, {len(status['pending'])} pending")
        
        if status['pending']:
            migration_runner.run_pending_migrations()
            LOGGER.info("All migrations completed successfully")
        else:
            LOGGER.info("No pending migrations to run")
            
    except Exception as e:
        LOGGER.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    main()
