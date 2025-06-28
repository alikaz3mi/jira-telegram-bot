"""Settings module exports."""
from jira_telegram_bot.settings.postgre_db_settings import PostgresSettings

POSTGRES_SETTINGS = PostgresSettings()

__all__ = ["POSTGRES_SETTINGS", "PostgresSettings"]