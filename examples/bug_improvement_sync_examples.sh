#!/bin/bash

# Bug/Improvement Sync Examples
# This file shows various ways to use the sync script

echo "=== Bug/Improvement Sync Examples ==="
echo ""

# Example 1: Full sync of all configured boards
echo "Example 1: Full sync of all boards"
echo "Command: python scripts/sync_bugs_improvements.py sync --full"
echo ""

# Example 2: Sync specific boards (last 30 days)
echo "Example 2: Sync specific boards (PROJ1 and PROJ2, last 30 days)"
echo "Command: python scripts/sync_bugs_improvements.py sync --boards PROJ1 PROJ2"
echo ""

# Example 3: Sync all boards (last 30 days)
echo "Example 3: Quick sync all boards (last 30 days)"
echo "Command: python scripts/sync_bugs_improvements.py sync"
echo ""

# Example 4: Scheduled sync - every 5 minutes
echo "Example 4: Run scheduled sync every 5 minutes (last 7 days)"
echo "Command: python scripts/sync_bugs_improvements.py scheduled"
echo ""

# Example 5: Scheduled sync - custom interval
echo "Example 5: Run scheduled sync every 10 minutes (last 14 days)"
echo "Command: python scripts/sync_bugs_improvements.py scheduled --interval 10 --days-back 14"
echo ""

# Example 6: Scheduled sync - frequent updates
echo "Example 6: Run scheduled sync every 2 minutes (last 3 days) - for active projects"
echo "Command: python scripts/sync_bugs_improvements.py scheduled --interval 2 --days-back 3"
echo ""

# Example 7: Test connections
echo "Example 7: Test Jira and Google Sheets connections"
echo "Command: python scripts/sync_bugs_improvements.py test"
echo ""

echo "=== Running Example: Test connections ==="
# Uncomment the line below to actually run the test
# python scripts/sync_bugs_improvements.py test

echo ""
echo "To run any of these examples, uncomment the command and execute this script"
echo "Or copy the command and run it directly in your terminal"
