from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.settings.jira_board_config import JiraBoardSettings
from jira_telegram_bot.settings.telegram_settings import TelegramConnectionSettings


JIRA_SETTINGS = JiraConnectionSettings(_env=f"{DEFAULT_PATH}/.env")
JIRA_BOARD_SETTINGS = JiraBoardSettings(_env=f"{DEFAULT_PATH}/.env")
TELEGRAM_SETTINGS = TelegramConnectionSettings(_env=f"{DEFAULT_PATH}/.env")
