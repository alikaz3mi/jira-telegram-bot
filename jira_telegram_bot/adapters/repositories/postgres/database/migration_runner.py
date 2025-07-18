"""Database migration runner for Clean Architecture compliance."""
from __future__ import annotations

import importlib
import pkgutil
from typing import List

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Engine
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from sqlalchemy import text
from sqlalchemy.exc import NoSuchTableError

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.database.migration_interface import MigrationInterface


class MigrationRunner:
    """Database migration runner."""

    def __init__(self, engine: Engine) -> None:
        """Initialize migration runner.
        
        Args:
            engine: SQLAlchemy engine instance.
        """
        self.engine = engine
        self.metadata = MetaData()
        self._ensure_migration_table()

    def _ensure_migration_table(self) -> None:
        """Ensure the migration tracking table exists."""
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(255) PRIMARY KEY,
                        description TEXT NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                LOGGER.info("Migration tracking table ensured")
        except Exception as e:
            LOGGER.error(f"Failed to create migration tracking table: {e}")
            raise

    def _get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions.
        
        Returns:
            List of applied migration versions.
        """
        try:
            with self.engine.begin() as conn:
                result = conn.execute(text("SELECT version FROM schema_migrations"))
                return [row[0] for row in result]
        except Exception as e:
            LOGGER.error(f"Failed to get applied migrations: {e}")
            return []

    def _mark_migration_applied(self, version: str, description: str) -> None:
        """Mark a migration as applied.
        
        Args:
            version: Migration version.
            description: Migration description.
        """
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO schema_migrations (version, description) 
                    VALUES (:version, :description)
                    ON CONFLICT (version) DO NOTHING
                """), {"version": version, "description": description})
        except Exception as e:
            LOGGER.error(f"Failed to mark migration {version} as applied: {e}")
            raise

    def _mark_migration_rolled_back(self, version: str) -> None:
        """Mark a migration as rolled back.
        
        Args:
            version: Migration version.
        """
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    DELETE FROM schema_migrations WHERE version = :version
                """), {"version": version})
        except Exception as e:
            LOGGER.error(f"Failed to mark migration {version} as rolled back: {e}")
            raise

    def _discover_migrations(self) -> List[MigrationInterface]:
        """Discover all migration classes.
        
        Returns:
            List of migration instances sorted by version.
        """
        migrations = []
        
        # Import the migrations package
        import jira_telegram_bot.adapters.database.migrations as migrations_package
        
        # Iterate through all modules in the migrations package
        for _, module_name, _ in pkgutil.iter_modules(migrations_package.__path__, 
                                                      migrations_package.__name__ + "."):
            if module_name.endswith("__init__"):
                continue
                
            try:
                module = importlib.import_module(module_name)
                
                # Find classes that implement MigrationInterface
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, MigrationInterface) and 
                        attr is not MigrationInterface):
                        migrations.append(attr())
                        
            except Exception as e:
                LOGGER.warning(f"Failed to load migration module {module_name}: {e}")
        
        # Sort migrations by version
        migrations.sort(key=lambda m: m.version)
        return migrations

    def run_pending_migrations(self) -> None:
        """Run all pending migrations."""
        applied_migrations = self._get_applied_migrations()
        available_migrations = self._discover_migrations()
        
        pending_migrations = [
            migration for migration in available_migrations 
            if migration.version not in applied_migrations
        ]
        
        if not pending_migrations:
            LOGGER.info("No pending migrations to run")
            return
        
        LOGGER.info(f"Running {len(pending_migrations)} pending migrations")
        
        for migration in pending_migrations:
            try:
                LOGGER.info(f"Running migration {migration.version}: {migration.description}")
                migration.up(self.engine)
                self._mark_migration_applied(migration.version, migration.description)
                LOGGER.info(f"Migration {migration.version} completed successfully")
                
            except Exception as e:
                LOGGER.error(f"Migration {migration.version} failed: {e}")
                raise

    def rollback_migration(self, version: str) -> None:
        """Rollback a specific migration.
        
        Args:
            version: Migration version to rollback.
        """
        applied_migrations = self._get_applied_migrations()
        
        if version not in applied_migrations:
            LOGGER.warning(f"Migration {version} is not applied, cannot rollback")
            return
        
        available_migrations = self._discover_migrations()
        migration = next((m for m in available_migrations if m.version == version), None)
        
        if not migration:
            LOGGER.error(f"Migration {version} not found")
            raise ValueError(f"Migration {version} not found")
        
        if not migration.can_rollback():
            LOGGER.error(f"Migration {version} cannot be rolled back")
            raise ValueError(f"Migration {version} cannot be rolled back")
        
        try:
            LOGGER.info(f"Rolling back migration {version}: {migration.description}")
            migration.down(self.engine)
            self._mark_migration_rolled_back(version)
            LOGGER.info(f"Migration {version} rolled back successfully")
            
        except Exception as e:
            LOGGER.error(f"Migration {version} rollback failed: {e}")
            raise

    def get_migration_status(self) -> dict:
        """Get the status of all migrations.
        
        Returns:
            Dictionary containing migration status information.
        """
        applied_migrations = self._get_applied_migrations()
        available_migrations = self._discover_migrations()
        
        status = {
            "applied": [],
            "pending": [],
            "total_available": len(available_migrations),
            "total_applied": len(applied_migrations)
        }
        
        for migration in available_migrations:
            if migration.version in applied_migrations:
                status["applied"].append({
                    "version": migration.version,
                    "description": migration.description
                })
            else:
                status["pending"].append({
                    "version": migration.version,
                    "description": migration.description
                })
        
        return status
