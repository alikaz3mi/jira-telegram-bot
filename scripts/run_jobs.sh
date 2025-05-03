#!/bin/bash

# shellcheck disable=SC1091
source activate base

cd /home/ali/project/jirabot || exit
conda activate base

python jira_telegram_bot/use_cases/report.py
python jira_telegram_bot/adapters/fetch_store_gitlab_commits.py
