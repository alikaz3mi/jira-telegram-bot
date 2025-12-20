"""Run migration 009 to add delay_reason column to jira_tasks_enhanced."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from dotenv import load_dotenv
from jira_telegram_bot.adapters.repositories.postgres.database.migrations.migration_009_add_delay_reason_to_jira_tasks_enhanced import (
    Migration009AddDelayReasonToJiraTasksEnhanced,
)


def main() -> None:
    """Run migration 009."""
    # Load .env file
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
    
    # Get database settings from environment
    db_user = os.getenv("db_user", "telegram_bot").strip('"')
    db_password = os.getenv("db_password", "").strip('"')
    db_host = os.getenv("db_host", "localhost").strip('"')
    db_port = os.getenv("db_port", "57235").strip('"')
    db_name = os.getenv("db_name", "jira_telegram_bot").strip('"')
    
    # URL-encode password to handle special characters
    db_password_encoded = quote_plus(db_password)
    
    # Create engine
    connection_string = f"postgresql://{db_user}:{db_password_encoded}@{db_host}:{db_port}/{db_name}"
    engine = create_engine(connection_string)
    
    # Run migration
    migration = Migration009AddDelayReasonToJiraTasksEnhanced()
    print(f"Running migration {migration.version}: {migration.description}")
    migration.up(engine)
    print("✓ Migration completed successfully!")


if __name__ == "__main__":
    main()
