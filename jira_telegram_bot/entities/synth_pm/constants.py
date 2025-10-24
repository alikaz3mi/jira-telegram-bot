from __future__ import annotations

from enum import Enum


class SynthPMStatus(Enum):
    """SynthPM status constants."""

    READY_FOR_TECHNICAL_IMPLEMENTATION = "۵"  # آماده پیاده سازی فنی
    IN_IMPLEMENTATION = "۶"  # در حال پیاده سازی
    IN_DESIGN_PHASE = "۴"  # در مرحله طراحی (UI/UX tasks)
    IN_TECHNICAL_TESTING = "۷"  # در مرحله تست فنی
    READY_FOR_DELIVERY = "۸"  # آماده تحویل

    # Legacy statuses
    TODO = "۱"
    IN_PROGRESS_LEGACY = "۲"
    DONE_LEGACY = "۳"


class JiraStatus(Enum):
    """Jira status constants."""

    TO_DO = "To Do"
    SELECTED_FOR_DEVELOPMENT = "Selected for Development"
    IN_PROGRESS = "In Progress"
    REVIEW = "Review"
    DONE = "Done"

    # Legacy statuses
    IN_REVIEW = "In Review"
    TESTING = "Testing"
    READY_FOR_RELEASE = "Ready for Release"


class JiraPriority(Enum):
    """Jira priority constants."""

    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TelegramIcons(Enum):
    """Telegram message icons."""

    # Priority icons
    PRIORITY_HIGHEST = "🔴"
    PRIORITY_HIGH = "🟠"
    PRIORITY_MEDIUM = "🟡"
    PRIORITY_LOW = "🟢"

    # Status icons
    STATUS_READY_FOR_TECH = "📋"  # آماده پیاده سازی فنی
    STATUS_IN_IMPLEMENTATION = "⚡"  # در حال پیاده سازی
    STATUS_IN_DESIGN = "🎨"  # در مرحله طراحی
    STATUS_IN_TESTING = "🔍"  # در مرحله تست فنی
    STATUS_READY_FOR_DELIVERY = "✅"  # آماده تحویل

    # Component icons
    COMPONENT_AI = "🤖"
    COMPONENT_BACKEND = "⚙️"
    COMPONENT_FRONTEND = "🎨"
    COMPONENT_DEVOPS = "🔧"
    COMPONENT_UI_UX = "🎯"


class StatusDescriptions(Enum):
    """Human readable status descriptions."""

    INITIATION_AND_PRIORITIZATION = "۱. ثبت و اولویت بندی"
    ANALYSIS_AND_RFP = "۲. تحلیل مسئله و RFP"
    USER_STORY_PREPARATION = "۳. آماده سازی یوزر استوری"
    IN_DESIGN = "۴. در مرحله طراحی"
    READY_FOR_TECHNICAL_DEVELOPMENT = "۵. آماده پیاده سازی فنی"
    IN_PROGRESS = "۶. در حال پیاده سازی"
    TECHNICAL_TESTING = "۷. تست فنی"
    READY_FOR_DELIVERY = "۸. آماده تحویل"
    TECHNICAL_DOCUMENTATION = "۹. مستندسازی فنی"
    COMPLETED = "۱۰. تکمیل شده"


# Status mapping dictionaries
GOOGLE_SHEET_TO_JIRA_STATUS = {
    # Sheet -> Jira mapping (based on actual Jira workflow)
    "۱. ثبت و اولویت بندی": "BACKLOG",
    "۲. تحلیل مسئله و RFP": "SELECTED FOR DEVELOPMENT",
    "۳. آماده سازی یوزر استوری": "TO DO",
    "۴. در مرحله طراحی": "IN REVIEW",
    "۵. آماده پیاده سازی فنی": "REOPENED",
    "۶. در حال پیاده سازی": "IN PROGRESS",
    "۷. تست فنی": "REVIEW",
    "۸. آماده تحویل": "RESOLVED",
    "۹. مستندسازی فنی": "DONE",
    "۱۰. تکمیل شده": "CLOSED",
    # Legacy number-only mappings for backward compatibility
    "۱": "BACKLOG",
    "۲": "SELECTED FOR DEVELOPMENT",
    "۳": "TO DO",
    "۴": "IN REVIEW",
    "۵": "REOPENED",
    "۶": "IN PROGRESS",
    "۷": "REVIEW",
    "۸": "RESOLVED",
    "۹": "DONE",
    "۱۰": "CLOSED",
}

JIRA_TO_GOOGLE_SHEET_STATUS = {
    # Jira -> Sheet mapping (based on actual Jira workflow)
    "BACKLOG": "۱. ثبت و اولویت بندی",
    "SELECTED FOR DEVELOPMENT": "۲. تحلیل مسئله و RFP",
    "TO DO": "۳. آماده سازی یوزر استوری",
    "IN REVIEW": "۴. در مرحله طراحی",
    "REOPENED": "۵. آماده پیاده سازی فنی",
    "OPEN": "۵. آماده پیاده سازی فنی",
    "IN PROGRESS": "۶. در حال پیاده سازی",
    "PAUSE": "۶.۵ توقف پیاده سازی فنی",
    "REVIEW": "۷. تست فنی",
    "RESOLVED": "۸. آماده تحویل",
    "DONE": "۹. مستندسازی فنی",
    "CLOSED": "۱۰. تکمیل شده",
}

PRIORITY_MAPPING = {
    "Highest": JiraPriority.HIGHEST.value,
    "High": JiraPriority.HIGH.value,
    "Medium": JiraPriority.MEDIUM.value,
    "Low": JiraPriority.LOW.value,
    # Persian mappings
    "بالاترین": JiraPriority.HIGHEST.value,
    "بالا": JiraPriority.HIGH.value,
    "متوسط": JiraPriority.MEDIUM.value,
    "پایین": JiraPriority.LOW.value,
    "بحرانی": JiraPriority.HIGHEST.value,
    "خیلی پایین": JiraPriority.LOW.value,
}

PRIORITY_ICONS = {
    JiraPriority.HIGHEST.value: TelegramIcons.PRIORITY_HIGHEST.value,
    JiraPriority.HIGH.value: TelegramIcons.PRIORITY_HIGH.value,
    JiraPriority.MEDIUM.value: TelegramIcons.PRIORITY_MEDIUM.value,
    JiraPriority.LOW.value: TelegramIcons.PRIORITY_LOW.value,
    # Persian mappings
    "بالاترین": TelegramIcons.PRIORITY_HIGHEST.value,
    "بالا": TelegramIcons.PRIORITY_HIGH.value,
    "متوسط": TelegramIcons.PRIORITY_MEDIUM.value,
    "پایین": TelegramIcons.PRIORITY_LOW.value,
}

STATUS_ICONS = {
    "۱": "📝",  # ثبت و اولویت بندی
    "۲": "🔍",  # تحلیل مسئله و RFP
    "۳": "📋",  # برری بوردو اسپوری
    "۴": "🎨",  # در مرحله طراحی
    "۵": "⚙️",  # پیاده سازی فنی
    "۶": "⚡",  # در حال پیاده سازی
    "۷": "🔍",  # تست فنی
    "۸": "✅",  # آماده تحویل
    "۹": "📚",  # مستندسازی فنی
    "۱۰": "🎯",  # تکمیل شده
    # Legacy
    SynthPMStatus.TODO.value: "📝",
    SynthPMStatus.IN_PROGRESS_LEGACY.value: "⚡",
    SynthPMStatus.DONE_LEGACY.value: "✅",
}

STATUS_DESCRIPTIONS = {
    "۱": StatusDescriptions.INITIATION_AND_PRIORITIZATION.value,
    "۲": StatusDescriptions.ANALYSIS_AND_RFP.value,
    "۳": StatusDescriptions.USER_STORY_PREPARATION.value,
    "۴": StatusDescriptions.IN_DESIGN.value,
    "۵": StatusDescriptions.READY_FOR_TECHNICAL_DEVELOPMENT.value,
    "۶": StatusDescriptions.IN_PROGRESS.value,
    "۷": StatusDescriptions.TECHNICAL_TESTING.value,
    "۸": StatusDescriptions.READY_FOR_DELIVERY.value,
    "۹": StatusDescriptions.TECHNICAL_DOCUMENTATION.value,
    "۱۰": StatusDescriptions.COMPLETED.value,
    # Legacy
    SynthPMStatus.TODO.value: "To Do",
    SynthPMStatus.IN_PROGRESS_LEGACY.value: "In Progress",
    SynthPMStatus.DONE_LEGACY.value: "Done",
}

# Statuses that should trigger Telegram notifications
TELEGRAM_TRIGGER_STATUSES = [
    "۶",  # در حال پیاده سازی (IN PROGRESS)
    "۷",  # تست فنی (REVIEW)
    "۸",  # آماده تحویل (RESOLVED)
    "۹",  # مستندسازی فنی (DONE)
]
