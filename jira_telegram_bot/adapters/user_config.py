from __future__ import annotations

import json
from typing import Optional

from pydantic import ValidationError

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.user_config import UserConfig as UserConfigEntity
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)

USER_CONFIG_PATH = f"{DEFAULT_PATH}/jira_telegram_bot/settings/user_config.json"


class UserConfig(UserConfigInterface):
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
                LOGGER.error(f"Error loading config for {username}: {e}")
        return user_configurations

    def get_user_config(self, username: str) -> Optional[UserConfigEntity]:
        return self.user_config.get(username)

    def list_all_users(self):
        return self.user_config.keys()

    def get_user_config_by_jira_username(
        self,
        jira_username: str,
    ) -> Optional[UserConfigEntity]:
        for user_config in self.user_config.values():
            if user_config.jira_username.lower() == jira_username.lower():
                return user_config
        return None

    def save_user_config(self, telegram_username: str, user_cfg: UserConfig) -> None:
        self.user_config[telegram_username] = user_cfg
        configs = {
            username: user_cfg.dict() for username, user_cfg in self.user_config.items()
        }
        with open(USER_CONFIG_PATH, "w") as file:
            json.dump(configs, file)
