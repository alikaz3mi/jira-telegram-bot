#!/bin/bash

# shellcheck disable=SC1091
source activate base

conda activate base

# Run the new scheduled report service
python scripts/run_scheduled_reports.py
python jira_telegram_bot/adapters/fetch_store_gitlab_commits.py

