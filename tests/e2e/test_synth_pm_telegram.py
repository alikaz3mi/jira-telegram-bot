from __future__ import annotations

import asyncio
import sys

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.synth_pm import SynthPMUseCase


async def test_telegram_bot():
    """Test the dedicated Telegram bot for SynthPM."""
    try:
        LOGGER.info("🤖 Testing SynthPM Telegram Bot Configuration...")

        # Get container and settings
        container = get_container()
        settings = container[SynthPMSettings]

        LOGGER.info(f"📱 Channel ID: {settings.telegram_channel_id}")
        LOGGER.info(f"👥 Group ID: {settings.telegram_group_id}")
        LOGGER.info(f"🔑 Bot Token: {settings.telegram_bot_token[:10]}...")

        # Get use case and test bot
        use_case = container[SynthPMUseCase]

        # Test bot initialization
        bot = use_case.notification_gateway
        LOGGER.info("✅ Telegram bot initialized successfully")

        # Test getting bot info
        bot_info = await bot.get_me()
        LOGGER.info(
            f"🤖 Bot Info: @{bot_info.get('username')} ({bot_info.get('first_name')})",
        )

        # Test sending a simple message
        test_message = "🧪 **SynthPM Bot Test**\n\nThis is a test message to verify the bot configuration."

        await bot.send_message(
            chat_id=int(settings.telegram_channel_id),
            text=test_message,
            parse_mode="Markdown",
        )
        LOGGER.info(f"✅ Test message sent to channel {settings.telegram_channel_id}")

        return True

    except Exception as e:
        LOGGER.error(f"❌ Telegram bot test failed: {e}")
        return False


async def main():
    """Main test function."""
    try:
        success = await test_telegram_bot()
        if success:
            LOGGER.info("\n🎉 All Telegram bot tests passed!")
            sys.exit(0)
        else:
            LOGGER.error("\n❌ Telegram bot tests failed!")
            sys.exit(1)
    except Exception as e:
        LOGGER.error(f"❌ Test failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
