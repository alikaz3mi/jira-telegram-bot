# Quick Start Guide - Google Docs Documentation Feature

## TL;DR

```bash
# 1. Install Google API client
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

# 2. Configure (see below)
# - Get Google service account JSON
# - Update config/projects_config.json
# - Add emails to user_config.json

# 3. Test
python scripts/run_synth_pm.py test

# 4. Run once
python scripts/run_synth_pm.py sync

# 5. Run continuously (optional)
python scripts/run_synth_pm.py service
```

## Minimal Setup

### 1. Google Service Account

1. Go to: https://console.cloud.google.com/
2. Create project → Enable "Google Docs API" & "Google Drive API"
3. Create Service Account → Download JSON key
4. Save as `parschat-684f8662ca98.json` in project root
5. Share your Google Doc & Sheet with service account email

### 2. Config Files

**`.env`** - Add these lines:
```bash
GOOGLE_SERVICE_ACCOUNT_FILE=parschat-684f8662ca98.json
PM_PROJECT_KEY=PARSCHAT
DEVELOPER_BOARD_PROJECT_KEY=DEV
```

**`config/projects_config.json`** - Create this:
```json
{
  "projects": {
    "PARSCHAT": {
      "project_name": "ParsChat",
      "google_sheets": {
        "spreadsheet_id": "YOUR_SHEET_ID",
        "tasks": {
          "sheet_name": "Developer Board",
          "gid": "0",
          "data_range": "A:AW"
        },
        "releases": {
          "sheet_name": "Release Notes",
          "data_range": "A:Z"
        }
      },
      "google_docs": {
        "document_id": "YOUR_DOC_ID",
        "document_url": "https://docs.google.com/document/d/YOUR_DOC_ID/edit",
        "epic_tab_mappings": {}
      },
      "jira": {
        "pm_board": {
          "board_key": "PARSCHAT",
          "board_id": 123
        },
        "development_board": {
          "board_key": "DEV",
          "board_id": 456
        }
      }
    }
  }
}
```

**Get IDs from URLs:**
- Sheet: `https://docs.google.com/spreadsheets/d/{THIS_IS_SHEET_ID}/edit`
- Doc: `https://docs.google.com/document/d/{THIS_IS_DOC_ID}/edit`

**`data/storage/user_config.json`** - Add email to each user:
```json
{
  "user_id": {
    "name": "John Doe",
    "email": "john@company.com",  ← ADD THIS
    "people_column": "Frontend"
  }
}
```

### 3. Run

```bash
# Test everything
python scripts/run_synth_pm.py test

# Sync once
python scripts/run_synth_pm.py sync

# Sync with filters
python scripts/run_synth_pm.py sync --sprints "Sprint 1" --releases "v1.0.0"
```

## What It Does

1. ✅ Syncs features from Google Sheets → Jira
2. ✅ Creates releases in PM board
3. ✅ Generates Google Docs documentation (organized by Epic)
4. ✅ Creates 2-hour documentation subtasks per department
5. ✅ Color codes by status (🔴 Red, 🟡 Yellow, 🟢 Green)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: googleapiclient` | `pip install google-api-python-client` |
| `403 Permission denied` | Share Google Doc/Sheet with service account email |
| `Project not found` | Check `projects_config.json` project key |
| No assignee | Add `email` field to `user_config.json` |

## Full Documentation

See `docs/google-docs-feature-guide.md` for detailed information.

## Run Tests

```bash
# All tests
python -m pytest tests/unit_tests/ -v

# 78 tests should pass ✓
```
