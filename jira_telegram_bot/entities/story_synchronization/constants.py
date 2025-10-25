"""Constants for story synchronization feature."""

# Story synchronization specific mapping - only maps to technical statuses (۵-۸)
JIRA_TO_STORY_SYNC_STATUS = {
    # Backlog, To Do, Selected for Development -> ۵ (آماده پیاده سازی فنی)
    "BACKLOG": "۵. آماده پیاده سازی فنی",
    "SELECTED FOR DEVELOPMENT": "۵. آماده پیاده سازی فنی",
    "TO DO": "۵. آماده پیاده سازی فنی",
    "REOPENED": "۵. آماده پیاده سازی فنی",
    "OPEN": "۵. آماده پیاده سازی فنی",
    # In Progress -> ۶ (در حال پیاده سازی)
    "IN PROGRESS": "۶. در حال پیاده سازی",
    # Pause -> ۶.۵ (توقف پیاده سازی فنی)
    "PAUSE": "۶.۵ توقف پیاده سازی فنی",
    # In Review -> ۷ (تست فنی)
    "IN REVIEW": "۷. تست فنی",
    "REVIEW": "۷. تست فنی",
    # Done, Resolved, Closed -> ۸ (آماده تحویل)
    "RESOLVED": "۸. آماده تحویل",
    "DONE": "۸. آماده تحویل",
    "CLOSED": "۸. آماده تحویل",
}

# Statuses that should be preserved (not updated) in story sync
# These are PM/Business statuses that shouldn't be changed by developer board sync
STORY_SYNC_PRESERVE_STATUSES = [
    "۱",
    "۱. ثبت و اولویت بندی",
    "۲",
    "۲. تحلیل مسئله و RFP",
    "۳",
    "۳. آماده سازی یوزر استوری",
    "۴",
    "۴. در مرحله طراحی",
    "۹",
    "۹. مستندسازی فنی",
    "۱۰",
    "۱۰. تکمیل شده",
]
