from telegram import Update

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings import TELEGRAM_SETTINGS
from jira_telegram_bot.use_cases.interfaces.authentication_interface import AuthenticationInterface


class TelegramAuthentication(AuthenticationInterface):
    """Telegram-specific authentication implementation."""

    async def is_user_allowed(self, user_context: Update) -> bool:
        """Check if a Telegram user is allowed to perform actions.
        
        Args:
            user_context: Telegram Update object containing user information
        
        Returns:
            True if user is authorized, False otherwise
        """
        user_id = user_context.message.from_user.username
        chat_type = user_context.message.chat.type
        if user_id not in TELEGRAM_SETTINGS.ALLOWED_USERS:
            await user_context.message.reply_text(
                f"{user_id}: You are not authorized to create tasks."
            )
            LOGGER.info(f"Unauthorized user: {user_id} in chat type: {chat_type}")
            return False
        return True


# Legacy function - kept for backward compatibility
# but should be deprecated in favor of the TelegramAuthentication class
async def check_user_allowed(update: Update) -> bool:
    """Check if a user is allowed based on Telegram settings.
    
    Args:
        update: Telegram Update object
        
    Returns:
        True if user is authorized, False otherwise
    """
    auth_service = TelegramAuthentication()
    return await auth_service.is_user_allowed(update)
