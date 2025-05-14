"""Authentication module for Telegram users."""

from telegram import Update

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.interfaces.user_authentication_interface import (
    UserAuthenticationInterface,
)


class TelegramAuthenticationService:
    """Service for authenticating Telegram users."""
    
    def __init__(self, user_authentication_repository: UserAuthenticationInterface):
        """Initialize the authentication service.
        
        Args:
            user_authentication_repository: Repository for user authentication
        """
        self.user_authentication_repository = user_authentication_repository
    
    async def check_user_allowed(self, update: Update) -> bool:
        """Check if a user is allowed to use the bot.
        
        Args:
            update: Telegram update object containing user information
            
        Returns:
            True if user is allowed, False otherwise
        """
        user_id = update.message.from_user.username
        chat_type = update.message.chat.type
        
        is_allowed = await self.user_authentication_repository.is_user_allowed(user_id)
        
        if not is_allowed:
            await update.message.reply_text(
                f"{user_id}: You are not authorized to create tasks."
            )
            LOGGER.info(f"Unauthorized user: {user_id} in chat type: {chat_type}")
            return False
            
        return True
