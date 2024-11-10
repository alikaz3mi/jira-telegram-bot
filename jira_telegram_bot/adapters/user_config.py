from __future__ import annotations

import json

from jira_telegram_bot import DEFAULT_PATH

USER_CONFIG_PATH = f"{DEFAULT_PATH}/jira_telegram_bot/settings/user_config.json"


class UserConfig:
    def __init__(self, user_config_path: str = USER_CONFIG_PATH) -> None:
        self.user_config = self.load_user_config(user_config_path)

    def load_user_config(self, user_config_path: str):
        with open(USER_CONFIG_PATH, "r") as file:
            return json.load(file)

    def get_user_config(self, username: str):
        return self.user_config.get(username, None)
