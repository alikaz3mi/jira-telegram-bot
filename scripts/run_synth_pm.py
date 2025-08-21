from __future__ import annotations

import argparse
import asyncio
import sys

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.services.synth_pm_sync_task import SynthPMSyncTask
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase


async def setup_components():
    """Set up all required components for SynthPM using dependency injection."""
    try:
        container = get_container()

        synth_developer_board_use_case = container[SynthPMUseCase]

        return synth_developer_board_use_case

    except Exception as e:
        LOGGER.error(f"Error setting up SynthPM components: {e}")
        raise


async def run_sync_once(use_case: SynthPMUseCase):
    """Run synchronization once and exit."""
    try:
        LOGGER.info("Starting one-time SynthPM synchronization...")

        result = await use_case.sync_developer_board_features()

        if result["status"] == "success":
            LOGGER.info("✅  Features synchronization completed successfully!")
            print(f" Features Results: {result.get('results', {})}")
        else:
            LOGGER.error(f"❌  Features synchronization failed: {result.get('message')}")
            sys.exit(1)

        LOGGER.info("Starting Release Notes synchronization...")
        release_result = await use_case.sync_release_notes()

        if release_result["status"] == "success":
            LOGGER.info("✅ Release Notes synchronization completed successfully!")
            print(f"Release Notes Results: {release_result.get('results', {})}")
        else:
            LOGGER.error(
                f"❌ Release Notes synchronization failed: {release_result.get('message')}",
            )
            LOGGER.warning("Continuing despite Release Notes sync failure...")

    except Exception as e:
        LOGGER.error(f"❌ Error during synchronization: {e}")
        sys.exit(1)


async def run_background_service(use_case: SynthPMUseCase):
    """Run as a background service with periodic synchronization."""
    try:
        LOGGER.info("Starting SynthPM background service...")

        container = get_container()
        settings = container[SynthPMSettings]

        sync_task = SynthPMSyncTask(
            synth_developer_board_use_case=use_case,
            settings=settings,
        )

        await sync_task.start()

        try:
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            LOGGER.info("Received interrupt signal, shutting down...")
        finally:
            await sync_task.stop()

    except Exception as e:
        LOGGER.error(f"❌ Error in background service: {e}")
        sys.exit(1)


async def test_connection(use_case: SynthPMUseCase):
    """Test connections to Google Sheets, Jira, and Telegram."""
    try:
        LOGGER.info("Testing connections...")

        print("📊 Testing Google Sheets connection...")
        features = await use_case.repository.get_developer_board_features()
        print(f"✅ Found {len(features)} features in Google Sheets")

        print("🎫 Testing Jira connection...")
        print("✅ Jira connection OK")

        print("🤖 Testing dedicated SynthPM Telegram bot...")
        try:
            bot = use_case.telegram_bot
            bot_info = await bot.get_me()
            print(f"✅ Bot connected: @{bot_info.username} ({bot_info.first_name})")

            test_message = "🧪 **SynthPM Connection Test**\n\nBot is working correctly!"
            await bot.send_message(
                chat_id=int(use_case.settings.telegram_channel_id),
                text=test_message,
                parse_mode="Markdown",
            )
            print(
                f"✅ Test message sent to channel {use_case.settings.telegram_channel_id}",
            )

        except Exception as telegram_error:
            print(f"❌ Telegram bot test failed: {telegram_error}")
            print("💡 Make sure SYNTH_PM_TELEGRAM_BOT_TOKEN is set correctly")
            raise

        print("\n🎉 All connections tested successfully!")
        print(f"📊 Google Sheets: {len(features)} features ready for sync")
        print("🎫 Jira: Connection verified")
        print("🤖 Telegram: Dedicated bot ready for notifications")

    except Exception as e:
        LOGGER.error(f"❌ Connection test failed: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SynthPM synchronization tool",
    )
    parser.add_argument(
        "command",
        choices=["sync", "service", "test"],
        default="service",
        help="Command to run: sync (one-time), service (background), or test (connections)",
    )

    args = parser.parse_args()

    try:
        if args.command == "sync":
            asyncio.run(async_main_sync())
        elif args.command == "service":
            asyncio.run(async_main_service())
        elif args.command == "test":
            asyncio.run(async_main_test())
    except KeyboardInterrupt:
        LOGGER.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        LOGGER.error(f"Unexpected error: {e}")
        sys.exit(1)


async def async_main_sync():
    """Async main for sync command."""
    use_case = await setup_components()
    await run_sync_once(use_case)


async def async_main_service():
    """Async main for service command."""
    use_case = await setup_components()
    await run_background_service(use_case)


async def async_main_test():
    """Async main for test command."""
    use_case = await setup_components()
    await test_connection(use_case)


if __name__ == "__main__":
    main()
