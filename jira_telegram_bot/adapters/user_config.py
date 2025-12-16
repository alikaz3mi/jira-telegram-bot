from __future__ import annotations

import json
import os
from typing import Optional
from typing import Dict

from pydantic import ValidationError

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.user_config import UserConfig as UserConfigEntity
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)

USER_CONFIG_PATH = f"{DEFAULT_PATH}/data/storage/user_config.json"


class UserConfig(UserConfigInterface):
    def __init__(self, user_config_path: str = USER_CONFIG_PATH) -> None:
        self.user_config_path = user_config_path
        self.user_config = self.load_user_config(user_config_path)

    def load_user_config(self, user_config_path: str) -> Dict[str, UserConfigEntity]:
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(user_config_path), exist_ok=True)

            # Try to read the existing config
            if os.path.exists(user_config_path):
                with open(user_config_path, "r") as file:
                    raw_data = json.load(file)
            else:
                # Create a default empty config
                LOGGER.warning(
                    f"User config file not found at {user_config_path}. Creating an empty one.",
                )
                raw_data = {}
                with open(user_config_path, "w") as file:
                    json.dump(raw_data, file)

            user_configurations = {}
            for username, config_data in raw_data.items():
                try:
                    user_configurations[username] = UserConfigEntity(**config_data)
                except ValidationError as e:
                    LOGGER.error(f"Error loading config for {username}: {e}")
            return user_configurations

        except Exception as e:
            LOGGER.error(f"Error loading user config: {e}")
            return {}

    def get_user_config(self, username: str) -> Optional[UserConfigEntity]:
        return self.user_config.get(username)

    def list_all_users(self):
        return self.user_config.keys()

    def list_all_users_google_sheet_names(self):
        return [username.google_sheet_name for username in self.user_config.values() if username.google_sheet_name]

    def get_user_config_by_jira_username(
        self,
        jira_username: str,
    ) -> Optional[UserConfigEntity]:
        for user_config in self.user_config.values():
            if user_config.jira_username.lower() == jira_username.lower():
                return user_config
        LOGGER.warning(f"User config not found for JIRA username: {jira_username}")
        return None

    def get_user_role_for_board(
        self,
        username: str,
        board_name: str,
    ) -> Optional[str]:
        """Get the role of a user for a specific board.
        
        Args:
            username: Telegram username
            board_name: Name of the board (e.g., 'PARSCHAT', 'PCT')
            
        Returns:
            Role string (e.g., 'admin', 'member', 'viewer') or None if not found
        """
        user_cfg = self.get_user_config(username)
        if user_cfg and user_cfg.board_roles:
            return user_cfg.board_roles.get(board_name)
        return None

    def is_board_admin(
        self,
        username: str,
        board_name: str,
    ) -> bool:
        """Check if a user is an admin for a specific board.
        
        Args:
            username: Telegram username
            board_name: Name of the board
            
        Returns:
            True if user is admin, False otherwise
        """
        role = self.get_user_role_for_board(username, board_name)
        return role == "admin" if role else False

    def save_user_config(
        self,
        telegram_username: str,
        user_cfg: UserConfigEntity,
    ) -> None:
        self.user_config[telegram_username] = user_cfg
        configs = {
            username: user_cfg.dict() for username, user_cfg in self.user_config.items()
        }
        with open(self.user_config_path, "w") as file:
            json.dump(configs, file)

    def get_all_user_configs(self):
        """Get all user configurations."""
        return self.user_config

    def get_group_chat_ids(self):
        """
        Get all configured Telegram group chat IDs.

        Currently returns an empty list as group chats are not configured in user config.
        This can be extended to support group chat configuration.
        """
        # TODO: Implement group chat configuration
        # For now, return empty list or read from environment/config
        import os

        group_chat_ids_str = os.environ.get("TELEGRAM_GROUP_CHAT_IDS", "")
        if group_chat_ids_str:
            try:
                return [
                    int(chat_id.strip())
                    for chat_id in group_chat_ids_str.split(",")
                    if chat_id.strip()
                ]
            except ValueError as e:
                LOGGER.error(f"Error parsing group chat IDs: {e}")
                return []
        return []

    def get_user_component(self, username: str, project_key: str) -> Optional[str]:
        """
        Get the user component for a specific user and project key.

        Args:
            username: The username to look up
            project_key: The project key to filter components

        Returns:
            The component name if found, None otherwise
        """
        user_config = self.get_user_config_by_jira_username(username)
        if user_config and user_config.user_components:
            return user_config.user_components.get(project_key)
        return None

    def get_user_weekly_capacity(
        self,
        username: str,
        project_key: str,
        component: str,
    ) -> Optional[int]:
        """Get user's weekly capacity for a specific project and component.

        Args:
            username: Jira username
            project_key: Project key (e.g., "PARSCHAT")
            component: Component name (e.g., "AI", "Backend", "Frontend", "UI/UX", "DevOps")

        Returns:
            Weekly capacity in hours, or None if not set
        """
        user_config = self.get_user_config_by_jira_username(username)
        if user_config and user_config.weekly_capacity:
            project_capacity = user_config.weekly_capacity.get(project_key, {})
            return project_capacity.get(component)
        return None

    def list_telegram_usernames(self):
        """
        List all Telegram usernames from the user configurations.

        Returns:
            List of Telegram usernames
        """
        return list(self.user_config.keys())

    def list_jira_usernames(self):
        """
        List all Jira usernames from the user configurations.

        Returns:
            List of Jira usernames
        """
        return [
            user_cfg.jira_username
            for user_cfg in self.user_config.values()
            if user_cfg.jira_username
        ]

    def list_telegram_user_ids(self):
        """
        List all Telegram user IDs from the user configurations.

        Returns:
            List of Telegram user IDs
        """
        return [
            user_cfg.telegram_user_chat_id
            for user_cfg in self.user_config.values()
            if user_cfg.telegram_user_chat_id
        ]

    def get_user_config_by_email(self, email: str) -> Optional[UserConfigEntity]:
        """
        Retrieve configuration for a specific user by email.

        Args:
            email: The email address to look up

        Returns:
            UserConfigEntity if found, None otherwise
        """
        if not email:
            return None
        
        email_lower = email.lower().strip()
        for user_config in self.user_config.values():
            if user_config.email and user_config.email.lower().strip() == email_lower:
                return user_config
        
        LOGGER.warning(f"User config not found for email: {email}")
        return None

    def list_user_emails(self):
        """
        List all user email addresses from the user configurations.

        Returns:
            List of email addresses (excluding None values)
        """
        return [
            user_cfg.email
            for user_cfg in self.user_config.values()
            if user_cfg.email
        ]
