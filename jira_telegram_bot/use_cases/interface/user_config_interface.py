from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Dict
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
