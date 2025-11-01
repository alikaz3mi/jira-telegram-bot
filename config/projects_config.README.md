# Projects Configuration Guide

این فایل راهنمای استفاده از سیستم configuration جدید برای مدیریت پروژه‌ها است.

## ساختار Configuration

### فایل اصلی: `config/projects_config.json`

این فایل شامل configuration تمام پروژه‌ها است و هر پروژه شامل موارد زیر می‌باشد:

```json
{
  "projects": {
    "PROJECT_KEY": {
      "project_name": "نام پروژه",
      "google_sheets": { ... },
      "google_docs": { ... },
      "jira": { ... }
    }
  }
}
```

## بخش‌های Configuration

### 1. Google Sheets Configuration

```json
"google_sheets": {
  "spreadsheet_id": "SPREADSHEET_ID",
  "tasks": {
    "spreadsheet_id": "SPREADSHEET_ID",
    "sheet_name": "نام شیت وظایف",
    "gid": 123456,
    "data_range": "A2:AW"
  },
  "releases": {
    "sheet_name": "Release Notes",
    "data_range": "A2:AO"
  }
}
```

**توضیحات:**
- `spreadsheet_id`: ID اصلی Google Spreadsheet
- `tasks.sheet_name`: نام شیت که وظایف/فیچرها در آن قرار دارند
- `tasks.gid`: GID شیت برای ساخت URL
- `tasks.data_range`: محدوده داده‌ها (مثلاً `A2:AW` یعنی از ستون A تا AW، از ردیف 2 به بعد)
- `releases.sheet_name`: نام شیت release notes
- `releases.data_range`: محدوده داده‌های release notes

### 2. Google Docs Configuration

```json
"google_docs": {
  "document_id": "DOCUMENT_ID",
  "document_url": "https://docs.google.com/document/d/...",
  "epic_tab_mappings": {}
}
```

**توضیحات:**
- `document_id`: ID داکیومنت Google Docs برای مستندسازی
- `document_url`: URL کامل داکیومنت
- `epic_tab_mappings`: نگاشت Epic ها به tab های داکیومنت (به صورت خودکار پر می‌شود)

### 3. Jira Configuration

```json
"jira": {
  "pm_board": {
    "board_key": "PCD",
    "board_id": null,
    "enabled": true
  },
  "development_board": {
    "board_key": "PARSCHAT",
    "board_id": null,
    "enabled": true
  },
  "support_board": null
}
```

**توضیحات:**
- `pm_board`: تنظیمات board مدیریت محصول (PM)
- `development_board`: تنظیمات board توسعه
- `support_board`: تنظیمات board پشتیبانی (اختیاری)
- `board_key`: کلید پروژه در Jira (مثلاً `PARSCHAT`)
- `board_id`: ID عددی board (اختیاری، برای بهینه‌سازی)
- `enabled`: فعال/غیرفعال بودن sync با این board

## نحوه استفاده

### 1. در کد Python

```python
from jira_telegram_bot.settings.project_config_settings import ProjectConfigSettings

# Load configuration
settings = ProjectConfigSettings()
projects_config = settings.load_config()

# Get specific project
project = projects_config.get_project("PARSCHAT")

# Access Google Sheets settings
spreadsheet_id = project.google_sheets.spreadsheet_id
tasks_sheet = project.google_sheets.tasks.sheet_name

# Access Jira settings
pm_board_key = project.jira.pm_board.board_key
dev_board_key = project.jira.development_board.board_key

# Access Google Docs settings
doc_id = project.google_docs.document_id
```

### 2. جستجو بر اساس Board Key

```python
# Find project by Jira board key
project = projects_config.get_project_by_board_key("PARSCHAT")
```

### 3. جستجو بر اساس Spreadsheet ID

```python
# Find project by Google Sheets ID
project = projects_config.get_project_by_spreadsheet_id("1TCvcE...")
```

## اضافه کردن پروژه جدید

برای اضافه کردن پروژه جدید:

1. فایل `config/projects_config.json` را باز کنید
2. یک entry جدید در `projects` اضافه کنید:

```json
{
  "projects": {
    "EXISTING_PROJECT": { ... },
    "NEW_PROJECT_KEY": {
      "project_name": "My New Project",
      "google_sheets": {
        "spreadsheet_id": "NEW_SPREADSHEET_ID",
        "tasks": {
          "spreadsheet_id": "NEW_SPREADSHEET_ID",
          "sheet_name": "Tasks",
          "gid": 0,
          "data_range": "A2:AW"
        },
        "releases": {
          "sheet_name": "Releases",
          "data_range": "A2:AO"
        }
      },
      "google_docs": {
        "document_id": "NEW_DOC_ID",
        "document_url": "https://docs.google.com/document/d/NEW_DOC_ID/edit",
        "epic_tab_mappings": {}
      },
      "jira": {
        "pm_board": {
          "board_key": "PM_KEY",
          "board_id": null,
          "enabled": true
        },
        "development_board": {
          "board_key": "DEV_KEY",
          "board_id": null,
          "enabled": true
        },
        "support_board": null
      }
    }
  }
}
```

## Environment Variables

می‌توانید مسیر فایل configuration را از طریق environment variable تغییر دهید:

```bash
# در .env
PROJECTS_CONFIG_CONFIG_FILE_PATH=config/custom_projects_config.json
```

## Migration از Configuration قدیمی

اگر از `story_sync_config.json` قدیمی استفاده می‌کنید:

### قدیمی:
```json
{
  "mappings": [
    {
      "spreadsheet_id": "...",
      "sheet_name": "...",
      "board_key": "...",
      ...
    }
  ]
}
```

### جدید:
```json
{
  "projects": {
    "BOARD_KEY": {
      "project_name": "...",
      "google_sheets": { ... },
      "google_docs": { ... },
      "jira": { ... }
    }
  }
}
```

## Best Practices

### 1. یک پروژه = یک کلید منحصر به فرد
از board key اصلی به عنوان کلید پروژه استفاده کنید.

### 2. نگهداری epic_tab_mappings
این فیلد به صورت خودکار توسط سیستم پر می‌شود، آن را دستی تغییر ندهید.

### 3. استفاده از null برای optional fields
اگر support_board ندارید، آن را `null` قرار دهید.

### 4. Validation
قبل از commit کردن تغییرات، JSON را validate کنید:

```bash
python -c "import json; json.load(open('config/projects_config.json'))"
```

## Troubleshooting

### خطا: "Config file not found"
- مطمئن شوید فایل `config/projects_config.json` وجود دارد
- مسیر environment variable را چک کنید

### خطا: "Project not found"
- کلید پروژه را صحیح وارد کرده‌اید؟
- آیا پروژه در فایل configuration وجود دارد؟

### خطا: "Invalid JSON"
- فایل JSON را در یک validator بررسی کنید
- مطمئن شوید comma های اضافی وجود ندارند

## مثال کامل

```json
{
  "projects": {
    "PARSCHAT": {
      "project_name": "ParsChat",
      "google_sheets": {
        "spreadsheet_id": "1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4",
        "tasks": {
          "spreadsheet_id": "1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4",
          "sheet_name": "ParsChat Features",
          "gid": 1054397609,
          "data_range": "A2:AW"
        },
        "releases": {
          "sheet_name": "Release Notes",
          "data_range": "A2:AO"
        }
      },
      "google_docs": {
        "document_id": "1aSko7ryN2-kePi5d8w0dqlXdOZ4heQ3hmBP116NlCYY",
        "document_url": "https://docs.google.com/document/d/1aSko7ryN2-kePi5d8w0dqlXdOZ4heQ3hmBP116NlCYY/edit",
        "epic_tab_mappings": {}
      },
      "jira": {
        "pm_board": {
          "board_key": "PCD",
          "board_id": null,
          "enabled": true
        },
        "development_board": {
          "board_key": "PARSCHAT",
          "board_id": null,
          "enabled": true
        },
        "support_board": null
      }
    }
  }
}
```

## API Reference

برای مستندات کامل API، به فایل‌های زیر مراجعه کنید:
- `jira_telegram_bot/entities/synth_pm/project_config.py`
- `jira_telegram_bot/settings/project_config_settings.py`
