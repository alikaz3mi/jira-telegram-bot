"""Domain services for SynthPM operations."""
from __future__ import annotations

from datetime import datetime
from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot.entities.synth_pm.constants import GOOGLE_SHEET_TO_JIRA_STATUS
from jira_telegram_bot.entities.synth_pm.constants import JIRA_TO_GOOGLE_SHEET_STATUS
from jira_telegram_bot.entities.synth_pm.constants import PRIORITY_MAPPING
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity


class SynthPMDateService:
    """Service for handling date operations in SynthPM."""

    @staticmethod
    def parse_date_string(date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object.

        Args:
            date_str: Date string to parse

        Returns:
            Parsed datetime or None if parsing fails
        """
        if not date_str or date_str.strip() == "":
            return None

        date_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
            "%d-%m-%Y",
        ]

        for date_format in date_formats:
            try:
                return datetime.strptime(date_str.strip(), date_format)
            except ValueError:
                continue

        return None

    @staticmethod
    def extract_dates_from_feature(
        feature: SynthPMFeatureEntity,
    ) -> Dict[str, Optional[str]]:
        """Extract dates from feature in string format.

        Args:
            feature: SynthPM feature entity

        Returns:
            Dictionary with formatted date strings
        """
        due_date = None
        if feature.deadline:
            if isinstance(feature.deadline, str):
                due_date = feature.deadline
            else:
                due_date = feature.deadline.strftime("%Y-%m-%d")

        target_start = None
        if feature.implementation_start_date:
            if isinstance(feature.implementation_start_date, str):
                target_start = feature.implementation_start_date
            else:
                target_start = feature.implementation_start_date.strftime("%Y-%m-%d")

        target_end = None
        if feature.deadline:
            if isinstance(feature.deadline, str):
                target_end = feature.deadline
            else:
                target_end = feature.deadline.strftime("%Y-%m-%d")

        return {
            "due_date": due_date,
            "target_start": target_start,
            "target_end": target_end,
        }


class SynthPMStatusService:
    """Service for handling status mapping in SynthPM."""

    @staticmethod
    def map_sheet_status_to_jira(sheet_status: str) -> str:
        """Map Google Sheet status to Jira status.

        Args:
            sheet_status: Status from Google Sheet

        Returns:
            Corresponding Jira status
        """
        return GOOGLE_SHEET_TO_JIRA_STATUS.get(sheet_status, "TO DO")

    @staticmethod
    def map_jira_status_to_sheet(jira_status: str) -> str:
        """Map Jira status to Google Sheet status.

        Args:
            jira_status: Status from Jira

        Returns:
            Corresponding Google Sheet status
        """
        return JIRA_TO_GOOGLE_SHEET_STATUS.get(jira_status, "۱")

    @staticmethod
    def map_priority(priority: str) -> str:
        """Map priority string to Jira priority.

        Args:
            priority: Priority string

        Returns:
            Mapped Jira priority
        """
        return PRIORITY_MAPPING.get(priority, "Medium")

    @staticmethod
    def determine_jira_status(feature: SynthPMFeatureEntity) -> str:
        """Determine appropriate Jira status based on feature status.

        Args:
            feature: SynthPM feature entity

        Returns:
            Appropriate Jira status
        """
        if not feature.status:
            return "TO DO"

        return SynthPMStatusService.map_sheet_status_to_jira(feature.status)


class SynthPMComponentService:
    """Service for handling component mapping in SynthPM."""

    @staticmethod
    def map_components(feature: SynthPMFeatureEntity) -> List[str]:
        """Map feature department flags to Jira components.

        Args:
            feature: SynthPM feature entity

        Returns:
            List of component names
        """
        components = []

        if feature.ai and feature.ai.strip() and feature.ai != "0":
            components.append("AI")
        if feature.backend and feature.backend.strip() and feature.backend != "0":
            components.append("Backend")
        if feature.frontend and feature.frontend.strip() and feature.frontend != "0":
            components.append("Frontend")
        if feature.devops and feature.devops.strip() and feature.devops != "0":
            components.append("DevOps")
        if feature.ui_ux and feature.ui_ux.strip() and feature.ui_ux != "0":
            components.append("UI/UX")

        return components


class SynthPMColumnMappingService:
    """Service for handling column mapping from Google Sheets."""

    @staticmethod
    def create_column_mapping(headers: List[str]) -> Dict[str, int]:
        """Create mapping from column names to indices.

        Args:
            headers: List of column headers from the sheet

        Returns:
            Dictionary mapping field names to column indices
        """
        mapping = {}

        column_name_mappings = {
            "row_number": ["ردیف", "Row", "ردیف"],
            "task_title": ["وظیفه", "Task", "وظیفه"],
            "epic": ["Epic", "Epic"],
            "necessity": ["ضرورت", "Necessity", "ضرورت"],
            "priority": ["اولویت", "Priority", "اولویت"],
            "status": ["وضعیت", "Status", "وضعیت"],
            "release": ["ریلیز", "Release", "ریلیز"],
            "eta_hours": ["ETA(h)", "ETA", "ETA(h)"],
            "total_hours": ["Total (h)", "Total", "Total (h)"],
            "departments": ["Departments", "Departments"],
            "involved_people": ["افراد درگیر", "Involved People", "افراد درگیر"],
            "ai": ["AI", "AI"],
            "backend": ["Backend", "Backend"],
            "frontend": ["Front-end", "Frontend", "Front-end"],
            "devops": ["DevOPS", "DevOps", "DevOPS"],
            "ui_ux": ["UI / UX", "UI/UX", "UI / UX"],
            "creation_date": ["تاریخ ایجاد", "Creation Date", "تاریخ ایجاد"],
            "implementation_start_date": [
                "تاریخ شروع پیاده سازی",
                "Implementation Start",
                "تاریخ شروع پیاده سازی",
            ],
            "deadline": ["ددلاین", "Deadline", "ددلاین"],
            "sprint": ["اسپرینت", "Sprint", "اسپرینت"],
            "dependencies": ["وابستگی ها", "Dependencies", "وابستگی ها"],
            "initial_delivery_time": [
                "زمان تحویل اولیه",
                "Initial Delivery",
                "زمان تحویل اولیه",
            ],
            "description": ["توضیحات", "Description", "توضیحات"],
            "acceptance_criteria": [
                "معیارهای پذیرش",
                "Acceptance Criteria",
                "معیارهای پذیرش",
            ],
            "test_cases": ["تست ها", "Test Cases", "تست ها"],
            "po_notes": ["علل تغییر یا توقف", "PO Notes", "علل تغییر یا توقف"],
            "jira_issue_key": ["jira_issue_key", "Jira Issue Key", "jira_issue_key"],
            "developer_board_issue_key": ["developer_board_issue_key"],
            "version": ["version", "ریلیز اصلی"],
        }

        for idx, header in enumerate(headers):
            header_clean = header.strip()

            for field_name, possible_names in column_name_mappings.items():
                if header_clean in possible_names:
                    mapping[field_name] = idx
                    break

        return mapping

    @staticmethod
    def number_to_column_letter(column_number: int) -> str:
        """Convert column number to Excel-style column letter.

        Args:
            column_number: Column number (1-based)

        Returns:
            Excel-style column letter (A, B, C, ...)
        """
        column_letter = ""
        while column_number > 0:
            column_number -= 1
            column_letter = chr(column_number % 26 + ord("A")) + column_letter
            column_number //= 26
        return column_letter
