"""Setup script for team evaluation feature."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.use_cases.team_evaluation.sprint_closed_team_evaluation_use_case import (
    SprintClosedTeamEvaluationUseCase,
)


def setup_team_evaluation():
    """Set up the team evaluation feature."""

    LOGGER.info("🚀 Setting up Team Evaluation feature...")

    # Check required directories
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "storage"
    config_dir = project_root / "config"

    # Create directories if they don't exist
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info(f"✅ Created directories: {data_dir}, {config_dir}")

    # Check for example files
    calendar_example = data_dir / "2024.json.example"
    config_example = config_dir / "team_evaluation.env.example"

    if calendar_example.exists():
        LOGGER.info(f"📅 Calendar example available: {calendar_example}")
        LOGGER.info("   Copy to 2024.json and customize for your holidays")

    if config_example.exists():
        LOGGER.info(f"⚙️  Config example available: {config_example}")
        LOGGER.info("   Copy settings to your .env file")

    # Check environment variables
    required_env_vars = [
        "TEAM_EVALUATION_SHEET_ID",
    ]

    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        LOGGER.info(
            f"⚠️  Missing required environment variables: {', '.join(missing_vars)}",
        )
        LOGGER.info("   Please set these in your .env file")
    else:
        LOGGER.info("✅ All required environment variables are set")

    # Try to import the main components
    try:
        container = get_container()
        container[SprintClosedTeamEvaluationUseCase]
        LOGGER.info("✅ Team evaluation components loaded successfully")

    except Exception as e:
        LOGGER.info(f"❌ Error loading team evaluation components: {e}")
        return False

    LOGGER.info("\n🎉 Team Evaluation setup complete!")
    LOGGER.info("\nNext steps:")
    LOGGER.info("1. Configure your Google Sheets ID in TEAM_EVALUATION_SHEET_ID")
    LOGGER.info("2. Set up calendar data in data/storage/YYYY.json")
    LOGGER.info("3. Configure Jira webhooks to send sLOGGER.info events")
    LOGGER.info("4. Test with: python scripts/test_team_evaluation.py")

    return True


if __name__ == "__main__":
    success = setup_team_evaluation()
    sys.exit(0 if success else 1)
