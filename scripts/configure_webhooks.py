#!/usr/bin/env python
"""Configure webhooks for Jira and Telegram integration."""

import argparse
import asyncio
import sys
from urllib.parse import urljoin

import requests
from telegram import Bot

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot.settings.telegram_settings import TelegramConnectionSettings


async def setup_telegram_webhook(base_url: str, token: str, remove: bool = False) -> bool:
    """Set up or remove a Telegram webhook.
    
    Args:
        base_url: Base URL for webhook (e.g., https://example.com)
        token: Telegram bot token
        remove: Whether to remove the webhook instead of setting it
        
    Returns:
        True if successful, False otherwise
    """
    bot = Bot(token=token)
    
    if remove:
        LOGGER.info("Removing Telegram webhook...")
        result = await bot.delete_webhook()
        LOGGER.info(f"Webhook removed: {result}")
        return result
    
    # Construct the webhook URL
    webhook_url = urljoin(base_url, f"/webhook/telegram/")
    LOGGER.info(f"Setting Telegram webhook to: {webhook_url}")
    
    try:
        # Set the webhook
        result = await bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "edited_message", "channel_post"]
        )
        
        if result:
            LOGGER.info("Telegram webhook set successfully!")
            webhook_info = await bot.get_webhook_info()
            LOGGER.info(f"Webhook info: {webhook_info}")
        else:
            LOGGER.error("Failed to set Telegram webhook")
        
        return result
    except Exception as e:
        LOGGER.error(f"Error setting Telegram webhook: {str(e)}", exc_info=True)
        return False


def setup_jira_webhook(base_url: str, jira_url: str, jira_user: str, jira_token: str, remove: bool = False) -> bool:
    """Set up or remove a Jira webhook.
    
    Args:
        base_url: Base URL for webhook (e.g., https://example.com)
        jira_url: Jira instance URL
        jira_user: Jira username or email
        jira_token: Jira API token
        remove: Whether to remove the webhook instead of setting it
        
    Returns:
        True if successful, False otherwise
    """
    # Construct the webhook URL for Jira
    webhook_url = urljoin(base_url, f"/webhook/jira/")
    
    # Jira system webhook API endpoint
    jira_webhook_api = urljoin(jira_url, "rest/webhooks/1.0/webhook")
    
    if remove:
        LOGGER.info("Listing and removing Jira webhooks...")
        # Get existing webhooks
        response = requests.get(
            jira_webhook_api,
            auth=(jira_user, jira_token),
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            LOGGER.error(f"Failed to fetch Jira webhooks: {response.text}")
            return False
        
        webhooks = response.json()
        removed_count = 0
        
        for webhook in webhooks:
            if webhook_url in webhook.get("url", ""):
                # Delete this webhook
                delete_response = requests.delete(
                    f"{jira_webhook_api}/{webhook['id']}",
                    auth=(jira_user, jira_token)
                )
                
                if delete_response.status_code == 204:
                    LOGGER.info(f"Removed Jira webhook: {webhook['id']}")
                    removed_count += 1
                else:
                    LOGGER.error(f"Failed to remove webhook {webhook['id']}: {delete_response.text}")
        
        LOGGER.info(f"Removed {removed_count} Jira webhooks")
        return True
    
    # Create the webhook
    LOGGER.info(f"Setting Jira webhook to: {webhook_url}")
    
    webhook_data = {
        "name": "Jira Telegram Bot Integration",
        "url": webhook_url,
        "events": [
            "jira:issue_created",
            "jira:issue_updated", 
            "jira:issue_deleted",
            "comment_created",
            "comment_updated"
        ],
        "filters": {
            "issue-related-events-section": "true"
        },
        "excludeIssueDetails": False
    }
    
    try:
        response = requests.post(
            jira_webhook_api,
            auth=(jira_user, jira_token),
            headers={"Content-Type": "application/json"},
            json=webhook_data
        )
        
        if response.status_code == 201:
            LOGGER.info(f"Jira webhook created successfully: {response.json()['id']}")
            return True
        else:
            LOGGER.error(f"Failed to create Jira webhook: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        LOGGER.error(f"Error creating Jira webhook: {str(e)}", exc_info=True)
        return False


async def main():
    """Main entry point for webhook configuration."""
    parser = argparse.ArgumentParser(description="Configure webhooks for Jira and Telegram integration")
    parser.add_argument(
        "--base-url", required=True, help="Base URL for webhooks (e.g., https://example.com)"
    )
    parser.add_argument(
        "--service", choices=["jira", "telegram", "all"], default="all",
        help="Which webhook service to configure"
    )
    parser.add_argument(
        "--remove", action="store_true", help="Remove webhooks instead of setting them"
    )
    
    args = parser.parse_args()
    
    # Get container with settings
    container = get_container()
    jira_settings = container.resolve(JiraConnectionSettings)
    telegram_settings = container.resolve(TelegramConnectionSettings)
    
    success = True
    
    # Configure webhooks based on service selection
    if args.service in ["telegram", "all"]:
        telegram_result = await setup_telegram_webhook(
            args.base_url,
            telegram_settings.TOKEN,
            args.remove
        )
        success = success and telegram_result
    
    if args.service in ["jira", "all"]:
        jira_result = setup_jira_webhook(
            args.base_url,
            jira_settings.JIRA_SERVER,
            jira_settings.JIRA_USER,
            jira_settings.JIRA_TOKEN,
            args.remove
        )
        success = success and jira_result
    
    if success:
        LOGGER.info("Webhook configuration completed successfully")
        sys.exit(0)
    else:
        LOGGER.error("Webhook configuration failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
