"""Helper methods for SynthPM documentation and subtask creation."""
from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    DocumentationTaskInfo,
)
from jira_telegram_bot.entities.synth_pm.pm_board_features import (
    SynthPMFeatureEntity,
)


class DocumentationSubtaskHelper:
    """Helper class for creating documentation subtasks."""
    
    @staticmethod
    def create_documentation_task_info(
        parent_issue_key: str,
        department: str,
        assignee_email: str,
        feature: SynthPMFeatureEntity,
    ) -> DocumentationTaskInfo:
        """Create documentation task info for a department.
        
        Args:
            parent_issue_key: Parent feature issue key
            department: Department name
            assignee_email: Assignee email
            feature: Feature entity
            
        Returns:
            DocumentationTaskInfo entity
        """
        task_title = f"مستندسازی {department} - {feature.task_title}"
        
        return DocumentationTaskInfo(
            department=department,
            assignee_email=assignee_email,
            estimated_hours=2,
            task_title=task_title,
            parent_issue_key=parent_issue_key,
        )
    
    @staticmethod
    def extract_departments_with_times(
        feature: SynthPMFeatureEntity,
    ) -> Dict[str, int]:
        """Extract departments and their time estimates from feature.
        
        Args:
            feature: Feature entity
            
        Returns:
            Dictionary mapping department names to time estimates (hours)
        """
        departments = {}
        
        department_mapping = {
            "Frontend": feature.frontend,
            "Backend": feature.backend,
            "UI/UX": feature.ui_ux,
            "AI": feature.ai,
            "DevOps": feature.devops,
        }
        
        for dept_name, time_value in department_mapping.items():
            if time_value and time_value != "0" and time_value != "":
                try:
                    time_hours = int(float(time_value))
                    if time_hours > 0:
                        departments[dept_name] = time_hours
                except (ValueError, TypeError):
                    LOGGER.warning(
                        f"Invalid time value for {dept_name}: {time_value}",
                    )
        
        return departments
    
    @staticmethod
    def should_create_documentation_subtask(
        department: str,
        time_hours: int,
    ) -> bool:
        """Check if documentation subtask should be created for department.
        
        Args:
            department: Department name
            time_hours: Time estimate in hours
            
        Returns:
            True if documentation subtask should be created
        """
        return time_hours > 0
    
    @staticmethod
    def build_documentation_subtask_description(
        feature: SynthPMFeatureEntity,
        department: str,
    ) -> str:
        """Build description for documentation subtask.
        
        Args:
            feature: Feature entity
            department: Department name
            
        Returns:
            Formatted description string
        """
        description_parts = [
            f"# مستندسازی {department}",
            "",
            f"## فیچر: {feature.task_title}",
            "",
            "## وظایف مستندسازی:",
            "- تکمیل بخش مربوط به این واحد در Google Docs",
            "- اضافه کردن API endpoints (در صورت نیاز)",
            "- تکمیل معیارهای پذیرش مرتبط",
            "- بررسی و تایید مستندات توسط تیم",
            "",
            f"## زمان تخمینی: 2 ساعت",
            "",
            f"## توضیحات فیچر:",
            feature.description or "توضیحات در دسترس نیست",
        ]
        
        return "\n".join(description_parts)


class ReleaseCreationHelper:
    """Helper class for creating releases in Jira."""
    
    @staticmethod
    def extract_release_info(release_note) -> Dict[str, any]:
        """Extract release information for Jira creation.
        
        Args:
            release_note: ReleaseNoteEntity
            
        Returns:
            Dictionary with release information
        """
        release_info = {
            "name": release_note.release_version,
            "description": release_note.description,
            "archived": False,
            "released": False,
        }
        
        if release_note.start_date:
            release_info["startDate"] = release_note.start_date
        
        if release_note.beta_delivery:
            release_info["releaseDate"] = release_note.beta_delivery
        
        return release_info
    
    @staticmethod
    def should_create_release(
        release_note,
        existing_releases: List[str],
    ) -> bool:
        """Check if release should be created.
        
        Args:
            release_note: ReleaseNoteEntity
            existing_releases: List of existing release names
            
        Returns:
            True if release should be created
        """
        return release_note.release_version not in existing_releases


class EmailMappingHelper:
    """Helper class for mapping departments to user emails."""
    
    @staticmethod
    def get_user_email_by_name(user_config_interface, user_name: str) -> Optional[str]:
        """Get user email by name from user config.
        
        Args:
            user_config_interface: UserConfigInterface
            user_name: User name to search for
            
        Returns:
            User email if found, None otherwise
        """
        all_configs = user_config_interface.get_all_user_configs()
        
        for config in all_configs.values():
            if hasattr(config, "name") and config.name == user_name:
                return getattr(config, "email", None)
        
        return None
    
    @staticmethod
    def get_department_assignee_from_feature(
        user_config_interface,
        feature: SynthPMFeatureEntity,
        department: str,
    ) -> Optional[str]:
        """Get assignee email for department from feature people columns.
        
        Args:
            user_config_interface: UserConfigInterface
            feature: Feature entity
            department: Department name
            
        Returns:
            Assignee email if found, None otherwise
        """
        all_configs = user_config_interface.get_all_user_configs()
        
        for user_id, config in all_configs.items():
            if not hasattr(config, "people_column"):
                continue
            
            people_column = config.people_column
            
            department_field_map = {
                "Frontend": feature.frontend,
                "Backend": feature.backend,
                "UI/UX": feature.ui_ux,
                "AI": feature.ai,
                "DevOps": feature.devops,
            }
            
            if department in department_field_map:
                field_value = department_field_map[department]
                
                if field_value and people_column in field_value:
                    return getattr(config, "email", None)
        
        return None
