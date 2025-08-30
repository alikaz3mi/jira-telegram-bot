"""Classification service for team evaluation."""

from typing import Set

from jira_telegram_bot.entities.team_evaluation import IssueSnapshot, IssueTypeGroup
from jira_telegram_bot.entities.constants import (
    DEV_ISSUE_TYPES,
    BUG_ISSUE_TYPES,
    SUPPORT_LABELS,
    SUPPORT_EPIC_NAME
)


class ClassificationService:
    """Service for classifying issues into groups."""

    @staticmethod
    def classify_issue(issue: IssueSnapshot) -> IssueTypeGroup:
        """Classify an issue into a type group.
        
        Args:
            issue: Issue to classify
            
        Returns:
            Issue type group
        """
        # Check if it's a support issue first
        if ClassificationService._is_support_issue(issue):
            return IssueTypeGroup.SUPPORT_GROUP
        
        # Check issue type
        if issue.issue_type in BUG_ISSUE_TYPES:
            return IssueTypeGroup.BUG_GROUP
        elif issue.issue_type in DEV_ISSUE_TYPES:
            return IssueTypeGroup.DEV_GROUP
        
        # Default to development for unknown types
        return IssueTypeGroup.DEV_GROUP

    @staticmethod
    def _is_support_issue(issue: IssueSnapshot) -> bool:
        """Check if an issue is a support issue.
        
        Args:
            issue: Issue to check
            
        Returns:
            True if it's a support issue
        """
        # Check labels
        issue_labels = {label.lower() for label in issue.labels}
        support_labels = {label.lower() for label in SUPPORT_LABELS}
        
        if issue_labels.intersection(support_labels):
            return True
        
        # Check epic name
        if issue.epic_name and issue.epic_name.strip().lower() == SUPPORT_EPIC_NAME.lower():
            return True
        
        return False

    @staticmethod
    def is_high_priority(issue: IssueSnapshot) -> bool:
        """Check if an issue has high priority.
        
        Args:
            issue: Issue to check
            
        Returns:
            True if it's high priority
        """
        return issue.priority and issue.priority == "Highest"

    @staticmethod
    def get_issue_departments(issue: IssueSnapshot, strategy: str = "component") -> Set[str]:
        """Get departments for an issue based on strategy.
        
        Args:
            issue: Issue to analyze
            strategy: Department inference strategy
            
        Returns:
            Set of department names
        """
        departments = set()
        
        if strategy == "component":
            departments.update(issue.components)
        elif strategy == "label":
            # Extract department-like labels
            dept_keywords = {
                "backend", "frontend", "devops", "data", "product", "qa", "mobile"
            }
            for label in issue.labels:
                if label.lower() in dept_keywords:
                    departments.add(label.title())
        
        # If no departments found, return default
        if not departments:
            departments.add("Unknown")
        
        return departments
