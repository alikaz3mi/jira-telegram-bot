"""Interface for daily task status use case."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from telegram import Update
from telegram.ext import CallbackContext


class DailyTaskStatusInterface(ABC):
    """Interface for daily task status tracking."""

    @abstractmethod
    async def start_daily_status(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Start the daily status check for a user.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            Next conversation state.
        """
        pass

    @abstractmethod
    async def handle_task_action(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle user's action selection for a task.
        
        Args:
            update: Telegram update object.
            context: Telegram callback context.
            
        Returns:
            Next conversation state.
        """
        pass

    @abstractmethod
    async def trigger_for_all_users(
        self,
        application,
    ) -> None:
        """Trigger daily status check for all configured users.
        
        Args:
            application: Telegram Application instance.
        """
        pass
