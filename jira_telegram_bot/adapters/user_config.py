# adapter/user_config.py
from __future__ import annotations

import json
from typing import Optional

from pydantic import ValidationError

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot.entities.user_config import UserConfig as UserConfigEntity

USER_CONFIG_PATH = f"{DEFAULT_PATH}/jira_telegram_bot/settings/user_config.json"


class UserConfig:
    def __init__(self, user_config_path: str = USER_CONFIG_PATH) -> None:
        self.user_config = self.load_user_config(user_config_path)

    def load_user_config(self, user_config_path: str):
        with open(USER_CONFIG_PATH, "r") as file:
            raw_data = json.load(file)

        user_configurations = {}
        for username, config_data in raw_data.items():
            try:
                user_configurations[username] = UserConfigEntity(**config_data)
            except ValidationError as e:
                print(f"Error loading config for {username}: {e}")
        return user_configurations

    def get_user_config(self, username: str) -> Optional[UserConfigEntity]:
        return self.user_config.get(username)
