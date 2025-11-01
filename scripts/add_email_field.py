#!/usr/bin/env python3
"""Script to add email field to all users in user_config.json."""

import json
from pathlib import Path

# Path to user_config.json
USER_CONFIG_PATH = Path(__file__).parent.parent / "data" / "storage" / "user_config.json"


def add_email_field():
    """Add email field to all users in user_config.json."""
    # Read the current config
    with open(USER_CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Add email field to each user if it doesn't exist
    modified_count = 0
    for username, user_data in config.items():
        if 'email' not in user_data:
            # Add email field after google_sheet_name
            # We'll insert it in the right position
            user_data['email'] = None
            modified_count += 1
            print(f"Added email field to user: {username}")
    
    # Write back to file with proper formatting
    with open(USER_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    print(f"\nTotal users modified: {modified_count}")
    print(f"Config file updated at: {USER_CONFIG_PATH}")


if __name__ == "__main__":
    add_email_field()
