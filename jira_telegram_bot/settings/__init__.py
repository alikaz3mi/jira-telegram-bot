from __future__ import annotations

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot.settings.gemini_settings import GeminiConnectionSetting
from jira_telegram_bot.settings.gitlab_settings import GitlabSettings
from jira_telegram_bot.settings.jira_board_config import JiraBoardSettings
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.settings.openai_settings import OpenAISettings
from jira_telegram_bot.settings.postgre_db_settings import PostgresSettings
from jira_telegram_bot.settings.telegram_settings import TelegramConnectionSettings
from jira_telegram_bot.settings.telegram_settings import (
    TelegramWebhookConnectionSettings,
)

JIRA_SETTINGS = JiraConnectionSettings(_env=f"{DEFAULT_PATH}/.env")
JIRA_BOARD_SETTINGS = JiraBoardSettings(_env=f"{DEFAULT_PATH}/.env")
TELEGRAM_SETTINGS = TelegramConnectionSettings(_env=f"{DEFAULT_PATH}/.env")
OPENAI_SETTINGS = OpenAISettings(_env=f"{DEFAULT_PATH}/.env")
TELEGRAM_WEBHOOK_SETTINGS = TelegramWebhookConnectionSettings(
    _env=f"{DEFAULT_PATH}/.env",
)
GITLAB_SETTINGS = GitlabSettings(_env=f"{DEFAULT_PATH}/.env")
POSTGRES_SETTINGS = PostgresSettings(_env=f"{DEFAULT_PATH}/.env")
GEMINI_SETTINGS = GeminiConnectionSetting(_env=f"{DEFAULT_PATH}/.env")
