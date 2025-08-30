#!/usr/bin/env python3
"""Team Evaluation CLI runner script."""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from jira_telegram_bot.frameworks.cli.team_evaluation_cli import main

if __name__ == "__main__":
    main()
