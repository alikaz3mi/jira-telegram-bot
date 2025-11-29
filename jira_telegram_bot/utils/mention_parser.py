"""Utility functions for parsing and converting Jira mentions to Telegram mentions."""

import re
from typing import List, Tuple

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.user_config import UserConfig


def extract_jira_mentions(text: str) -> List[str]:
    """Extract all Jira username mentions from text.
    
    Jira mentions can be in two formats:
    - [~username] (markup format)
    - ~username (plain format)
    
    Args:
        text: The text to parse for mentions
        
    Returns:
        List of Jira usernames that were mentioned
    """
    if not text:
        return []
    
    # Match both [~username] and ~username patterns
    markup_pattern = r'\[~([a-zA-Z0-9_\-.]+)\]'
    # Plain pattern: ~username preceded by start, space, or newline, followed by non-word char or end
    plain_pattern = r'(?:^|[\s\n])~([a-zA-Z0-9_\-.]+)(?=[\W\s]|$)'
    
    markup_matches = re.findall(markup_pattern, text)
    plain_matches = re.findall(plain_pattern, text)
    
    all_mentions = list(set(markup_matches + plain_matches))
    
    LOGGER.debug(f"Extracted Jira mentions: {all_mentions} from text: {text[:100]}")
    return all_mentions


def convert_jira_mentions_to_telegram(text: str, user_config: UserConfig) -> Tuple[str, List[str]]:
    """Convert Jira mentions in text to Telegram mentions.
    
    Replaces Jira-style mentions ([~username] or ~username) with Telegram-style
    mentions (@telegram_username).
    
    Args:
        text: The text containing Jira mentions
        user_config: UserConfig instance to lookup user mappings
        
    Returns:
        Tuple of (converted_text, list of telegram usernames that were mentioned)
    """
    if not text:
        return text, []
    
    jira_mentions = extract_jira_mentions(text)
    converted_text = text
    telegram_mentions = []
    
    for jira_username in jira_mentions:
        try:
            # Use the lookup function that handles multiple fallback methods
            from jira_telegram_bot.frameworks.fast_api.create_ticket import lookup_user_config_by_jira_username
            user_cfg = lookup_user_config_by_jira_username(jira_username)
            
            if user_cfg and hasattr(user_cfg, 'telegram_username') and user_cfg.telegram_username:
                telegram_username = user_cfg.telegram_username
                telegram_mentions.append(telegram_username)
                
                # Replace both markup and plain formats
                converted_text = re.sub(
                    rf'\[~{re.escape(jira_username)}\]',
                    f'@{telegram_username}',
                    converted_text
                )
                converted_text = re.sub(
                    rf'(?:^|[\s\n])~{re.escape(jira_username)}(?=[\W\s]|$)',
                    f' @{telegram_username}',
                    converted_text
                )
                
                LOGGER.debug(f"Converted Jira mention ~{jira_username} to @{telegram_username}")
            else:
                LOGGER.warning(f"No Telegram username found for Jira user: {jira_username}")
        except Exception as e:
            LOGGER.error(f"Error converting mention for {jira_username}: {e}")
    
    return converted_text, telegram_mentions


def get_mentioned_user_configs(text: str, user_config: UserConfig) -> List:
    """Get user config objects for all mentioned users.
    
    Args:
        text: The text containing Jira mentions
        user_config: UserConfig instance to lookup user mappings
        
    Returns:
        List of user config objects for mentioned users
    """
    jira_mentions = extract_jira_mentions(text)
    user_configs = []
    
    for jira_username in jira_mentions:
        try:
            # Use the lookup function that handles multiple fallback methods
            from jira_telegram_bot.frameworks.fast_api.create_ticket import lookup_user_config_by_jira_username
            user_cfg = lookup_user_config_by_jira_username(jira_username)
            if user_cfg:
                user_configs.append(user_cfg)
        except Exception as e:
            LOGGER.error(f"Error getting user config for {jira_username}: {e}")
    
    return user_configs
