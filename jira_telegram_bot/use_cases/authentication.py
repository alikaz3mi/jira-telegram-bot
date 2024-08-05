from telegram import Update

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.config import ALLOWED_USERS


async def check_user_allowed(update: Update) -> bool:
    user_id = update.message.from_user.username
    chat_type = update.message.chat.type
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text(
            f"{user_id}: You are not authorized to create tasks."
        )
        LOGGER.info(f"Unauthorized user: {user_id} in chat type: {chat_type}")
        return False
    return True
