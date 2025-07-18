"""Application startup service for Clean Architecture compliance."""
from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.postgres.database.migration_runner import MigrationRunner
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface
from jira_telegram_bot.utils.exceptions import DatabaseConnectionError


class ApplicationStartupService:
    """Service to handle application startup tasks."""

    def __init__(self, database_connection: DatabaseConnectionInterface) -> None:
        """Initialize startup service.
        
        Args:
            database_connection: Database connection interface.
        """
        self.database_connection = database_connection

    def initialize_database(self) -> None:
        """Initialize database with migrations.
        
        Raises:
            DatabaseConnectionError: If database initialization fails.
        """
        try:
            LOGGER.info("Initializing database")
            
            # Get database engine
            engine = self.database_connection.get_engine()
            
            # Run migrations
            migration_runner = MigrationRunner(engine)
            pending_migrations = migration_runner.get_pending_migrations()
            
            if pending_migrations:
                LOGGER.info(f"Found {len(pending_migrations)} pending migrations")
                migration_runner.run_pending_migrations()
            else:
                LOGGER.info("No pending migrations found")
            
            LOGGER.info("Database initialization completed")
            
        except Exception as e:
            LOGGER.error(f"Database initialization failed: {e}")
            raise DatabaseConnectionError(f"Database initialization failed: {e}")

    def verify_database_connection(self) -> None:
        """Verify database connection is working.
        
        Raises:
            DatabaseConnectionError: If database connection fails.
        """
        try:
            LOGGER.info("Verifying database connection...")
            
            # Test database connection
            with self.database_connection.get_session() as session:
                result = session.execute("SELECT 1").scalar()
                if result != 1:
                    raise DatabaseConnectionError("Database connection test failed")
            
            LOGGER.info("Database connection verified successfully")
            
        except Exception as e:
            LOGGER.error(f"Database connection verification failed: {e}")
            raise DatabaseConnectionError(f"Database connection verification failed: {e}")

    def startup(self) -> None:
        """Perform all startup tasks.
        
        Raises:
            DatabaseConnectionError: If any startup task fails.
        """
        try:
            LOGGER.info("Starting application startup sequence")
            
            # Verify database connection
            self.verify_database_connection()
            
            # Initialize database
            self.initialize_database()
            
            # Add other startup tasks here as needed
            
            LOGGER.info("Application startup completed successfully")
            
        except Exception as e:
            LOGGER.error(f"Application startup failed: {e}")
            raise DatabaseConnectionError(f"Application startup failed: {e}")
