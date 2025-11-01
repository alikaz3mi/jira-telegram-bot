# Google Docs Documentation Feature - Setup & Usage Guide

This guide explains how to set up and run the new Google Docs documentation generation feature.

## Overview

This feature automatically:
1. Creates Google Docs documentation for features synchronized from Google Sheets
2. Organizes documentation by Epics (tabs/sections)
3. Creates documentation subtasks (2 hours each) for involved departments
4. Creates releases in Jira PM board
5. Syncs everything with color-coded status indicators

## Prerequisites

### 1. Google API Setup

**Install Google API client:**
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

**Get Google Service Account credentials:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Docs API and Google Drive API
4. Create a Service Account:
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Download JSON key file
5. Share your Google Docs document with the service account email

**Save the JSON key file** as specified in your settings (e.g., `parschat-684f8662ca98.json`)

### 2. Configuration Files

#### A. Environment Variables

Add to your `.env` file:
```bash
# Existing Jira & Sheets settings
JIRA_DOMAIN=https://your-jira.com
JIRA_USERNAME=your_username
JIRA_PASSWORD=your_token

# Google Sheets
GOOGLE_SHEET_ID=your_sheet_id
GOOGLE_SHEET_DEVELOPER_BOARD_NAME=Developer Board
GOOGLE_SHEET_RELEASE_NOTES_NAME=Release Notes

# Google Service Account
GOOGLE_SERVICE_ACCOUNT_FILE=parschat-684f8662ca98.json

# Jira Board IDs
PM_PROJECT_KEY=PARSCHAT
DEVELOPER_BOARD_PROJECT_KEY=DEV
```

#### B. Project Configuration

Create/update `config/projects_config.json`:

```json
{
  "projects": {
    "PARSCHAT": {
      "project_name": "ParsChat",
      "google_sheets": {
        "spreadsheet_id": "your_spreadsheet_id_here",
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
        "document_id": "your_google_doc_id_here",
        "document_url": "https://docs.google.com/document/d/your_doc_id/edit",
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
        },
        "support_board": null
      }
    }
  }
}
```

**How to get IDs:**
- **Spreadsheet ID**: From the URL `https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit`
- **Document ID**: From the URL `https://docs.google.com/document/d/{DOCUMENT_ID}/edit`
- **Board ID**: From Jira board URL or use Jira API

#### C. User Config (Email Mapping)

Update `data/storage/user_config.json` to include email fields for assignee mapping:

```json
{
  "user_telegram_id": {
    "name": "John Doe",
    "email": "john.doe@company.com",
    "jira_username": "john.doe",
    "people_column": "Frontend",
    "default_project": "PARSCHAT",
    "default_board_id": 123
  }
}
```

## Running the Feature

### 1. Test Connections

First, verify all connections are working:

```bash
python scripts/run_synth_pm.py test
```

This will check:
- ✅ Google Sheets connection
- ✅ Jira API connection
- ✅ Telegram bot connection
- ✅ Configuration loaded correctly

Expected output:
```
📊 Testing Google Sheets connection...
✅ Found X features in Google Sheets
🎫 Testing Jira connection...
✅ Jira connection OK
🤖 Testing dedicated SynthPM Telegram bot...
✅ SynthPM notification gateway is configured
🎉 All connections tested successfully!
```

### 2. Run One-Time Sync

Synchronize features and generate documentation:

```bash
python scripts/run_synth_pm.py sync
```

This will:
1. Fetch features from Google Sheets
2. Sync them to Jira Developer Board
3. Create releases in PM board
4. Generate Google Docs documentation
5. Create documentation subtasks for each department

**With filters** (optional):
```bash
# Sync only specific sprints
python scripts/run_synth_pm.py sync --sprints "Sprint 1" "Sprint 2"

# Sync only specific releases
python scripts/run_synth_pm.py sync --releases "v1.0.0" "v1.1.0"

# Sync specific versions
python scripts/run_synth_pm.py sync --versions "1.0.0"

# Include features without sprint/release
python scripts/run_synth_pm.py sync --include-empty-sprint --include-empty-release
```

### 3. Run as Background Service

For continuous synchronization:

```bash
python scripts/run_synth_pm.py service
```

This runs as a daemon that:
- Periodically checks for changes
- Automatically syncs new/modified features
- Updates documentation
- Creates subtasks as needed

**Stop the service:** Press `Ctrl+C`

## What Happens During Sync

### Feature Processing Flow

1. **Fetch from Google Sheets**
   - Reads all features from "Developer Board" sheet
   - Reads release notes from "Release Notes" sheet

2. **Create/Update in Jira**
   - Creates or updates features in Developer Board
   - Links features to epics and sprints
   - Sets estimates, assignees, components

3. **Create Releases**
   - Creates release versions in PM board
   - Sets release dates (start, alpha, beta)
   - Links features to releases

4. **Generate Documentation**
   For each feature:
   - Creates Epic tab in Google Docs (if not exists)
   - Creates Feature subtab under Epic
   - Generates structured documentation:
     * Feature title & Jira link
     * Department chips (Frontend, Backend, UI/UX, etc.)
     * User Story section
     * Acceptance Criteria section
     * Wireframe/Design section
     * API List section
     * Subtasks section
   - Color codes by status:
     * 🔴 RED: Not started
     * 🟡 YELLOW: In progress
     * 🟢 GREEN: Done
     * ⚪ DEFAULT: Unknown status

5. **Create Documentation Subtasks**
   For each department involved (with >0 hours):
   - Creates a subtask in Developer Board
   - Title: "مستندسازی {Department} - {Feature Title}"
   - Estimate: 2 hours
   - Assignee: Based on email mapping from user_config
   - Description: Persian template with feature details

## Monitoring & Logs

### Check Logs

```bash
# View logs in real-time
tail -f logs.log

# Search for errors
grep ERROR logs.log

# Search for specific feature
grep "FEAT-123" logs.log
```

### Log Levels

The bot logs at different levels:
- **INFO**: Normal operations, sync progress
- **DEBUG**: Detailed technical information
- **WARNING**: Issues that don't prevent operation
- **ERROR**: Problems that need attention

### Key Log Messages

```
✅ Features synchronization completed successfully!
✅ Release Notes synchronization completed successfully!
Created documentation subtask SUB-123 for Frontend
Created release v1.0.0 in PM board
```

## Troubleshooting

### Common Issues

#### 1. Google API Errors

**Error**: `ModuleNotFoundError: No module named 'googleapiclient'`

**Solution**:
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

#### 2. Permission Denied

**Error**: `403: The caller does not have permission`

**Solution**:
- Share Google Docs with service account email
- Share Google Sheets with service account email
- Check service account has edit permissions

#### 3. Field Not Found

**Error**: `'TaskData' object has no attribute 'title'`

**Solution**: This is already fixed in the code. Make sure you're using the latest version.

#### 4. Configuration Not Found

**Error**: `Project PARSCHAT not found in configuration`

**Solution**: 
- Check `config/projects_config.json` exists
- Verify project key matches exactly (case-sensitive)
- Validate JSON syntax

#### 5. Email Mapping Issues

**Error**: `Assignee not found for email: john@company.com`

**Solution**:
- Update `data/storage/user_config.json` with email field
- Ensure email matches exactly what's in Google Sheets
- Check `people_column` field matches department name

#### 6. Jira Connection Issues

**Error**: `Connection refused` or `401 Unauthorized`

**Solution**:
- Verify JIRA_DOMAIN, JIRA_USERNAME, JIRA_PASSWORD in .env
- Check API token is valid (not expired)
- Ensure user has proper Jira permissions

### Debug Mode

For detailed debugging, set log level in code:

```python
import logging
LOGGER.setLevel(logging.DEBUG)
```

Or check the implementation in `jira_telegram_bot/__init__.py`.

## Architecture Overview

```
Google Sheets (Features)
    ↓
SynthPMRepository (fetch features)
    ↓
SynthPMUseCase (orchestration)
    ↓
    ├─→ TaskManagerRepository (create Jira tasks)
    ├─→ DocumentationGenerationUseCase (generate docs)
    │   └─→ GoogleDocsRepository (write to Google Docs)
    └─→ SynthPMRepository (create subtasks & releases)
```

## Testing

Run unit tests:

```bash
# All tests
python -m pytest tests/unit_tests/ -v

# Specific test suites
python -m pytest tests/unit_tests/entities/synth_pm/ -v
python -m pytest tests/unit_tests/use_cases/helpers/ -v
python -m pytest tests/unit_tests/adapters/repositories/ -v

# With coverage
python -m pytest tests/unit_tests/ --cov=jira_telegram_bot --cov-report=html
```

## Next Steps

1. **Configure your environment** - Set up all config files
2. **Test connections** - Run `python scripts/run_synth_pm.py test`
3. **Do a manual sync** - Run `python scripts/run_synth_pm.py sync`
4. **Review results** - Check Jira, Google Docs, and logs
5. **Set up service** - Run as background service if everything works

## Support

For issues or questions:
1. Check logs in `logs.log`
2. Review test output
3. Verify configuration files
4. Check Google API permissions
5. Validate Jira credentials

## Configuration Reference

See detailed configuration examples:
- `config/projects_config.README.md` - Projects configuration guide
- `docs/TODO-google-docs-integration.md` - Implementation checklist
- Unit tests in `tests/unit_tests/` - Usage examples
