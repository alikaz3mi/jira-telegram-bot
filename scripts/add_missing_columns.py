"""One-time script to add missing columns to jira_tasks_enhanced table."""
from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.interfaces.database_connection_interface import DatabaseConnectionInterface


def add_missing_columns():
    """Add missing due_date and project columns to jira_tasks_enhanced table."""
    try:
        container = get_container()
        db_connection = container[DatabaseConnectionInterface]
        
        # Check if table exists
        result = db_connection.execute_query("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'jira_tasks_enhanced'
            );
        """)
        
        if not result.fetchone()[0]:
            LOGGER.info("Table jira_tasks_enhanced does not exist. Skipping migration.")
            return
        
        # Add due_date column if it doesn't exist
        try:
            db_connection.execute_query("""
                ALTER TABLE jira_tasks_enhanced 
                ADD COLUMN IF NOT EXISTS due_date TIMESTAMP;
            """)
            LOGGER.info("Added due_date column")
        except Exception as e:
            LOGGER.warning(f"Could not add due_date column: {e}")
        
        # Add project column if it doesn't exist
        try:
            db_connection.execute_query("""
                ALTER TABLE jira_tasks_enhanced 
                ADD COLUMN IF NOT EXISTS project VARCHAR(255);
            """)
            LOGGER.info("Added project column")
        except Exception as e:
            LOGGER.warning(f"Could not add project column: {e}")
        
        LOGGER.info("Migration completed successfully")
        
    except Exception as e:
        LOGGER.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    add_missing_columns()
