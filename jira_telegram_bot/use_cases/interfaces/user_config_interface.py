from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot.entities.user_config import UserConfig as UserConfigEntity


class UserConfigInterface(ABC):
    """Interface for user configuration management"""

    @abstractmethod
    def load_user_config(self, user_config_path: str) -> Dict[str, UserConfigEntity]:
        """
        Load user configurations from a JSON file

        Args:
            user_config_path: Path to the user config JSON file

        Returns:
            Dictionary mapping usernames to their configurations
        """
        pass

    @abstractmethod
    def get_user_config(self, username: str) -> Optional[UserConfigEntity]:
        """
        Retrieve configuration for a specific user

        Args:
            username: The username to look up

        Returns:
            UserConfigEntity if found, None otherwise
        """
        pass

    @abstractmethod
    def get_user_config_by_jira_username(
        self,
        username: str,
    ) -> Optional[UserConfigEntity]:
        """
        Retrieve configuration for a specific Jira username

        Args:
            username: The Jira username to look up

        Returns:
            UserConfigEntity if found, None otherwise
        """
        pass

    @abstractmethod
    def save_user_config(
        self,
        telegram_username: str,
        user_cfg: UserConfigEntity,
    ) -> None:
        """
        Save a user configuration

        Args:
            telegram_username: The username of the user
            user_cfg: The configuration to save
        """
        pass

    @abstractmethod
    def get_all_user_configs(self) -> Dict[str, UserConfigEntity]:
        """
        Get all user configurations.

        Returns:
            Dictionary mapping usernames to their configurations
        """
        pass

    @abstractmethod
    def get_group_chat_ids(self) -> List[int]:
        """
        Get all configured Telegram group chat IDs.

        Returns:
            List of group chat IDs where bot should send notifications
        """
        pass

    @abstractmethod
    def get_user_component(self, username: str, project_key: str) -> Optional[str]:
        """
        Get user component for a specific project.

        Args:
            username: JIRA username
            project_key: Project key (e.g., "PARSCHAT")

        Returns:
            Component name or None if not found
        """
        pass

    @abstractmethod
    def list_all_users(self) -> List[str]:
        """
        List all users in the configuration.

        Returns:
            List of usernames
        """
        pass

    @abstractmethod
    def list_jira_usernames(self) -> List[str]:
        """
        List all Jira usernames in the configuration.

        Returns:
            List of Jira usernames
        """
        pass

    @abstractmethod
    def list_telegram_usernames(self) -> List[str]:
        """
        List all Telegram usernames in the configuration.

        Returns:
            List of Telegram usernames
        """
        pass

    @abstractmethod
    def list_telegram_user_ids(self) -> List[int]:
        """
        List all Telegram user IDs in the configuration.

        Returns:
            List of Telegram user IDs
        """
        pass
