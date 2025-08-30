"""Defect service for team evaluation."""

from typing import List, Tuple

from jira_telegram_bot.entities.team_evaluation import IssueSnapshot, IssueTypeGroup
from jira_telegram_bot.entities.constants import TESTER_LABEL, SUPPORT_LABELS, SUPPORT_EPIC_NAME
from jira_telegram_bot.use_cases.team_evaluation.services.classification_service import ClassificationService


class DefectService:
    """Service for defect-related calculations."""

    @staticmethod
    def compute_defect_scores(
        delivered_stories: List[IssueSnapshot],
        bugs: List[IssueSnapshot]
    ) -> Tuple[float, float]:
        """Compute defect rates for support and tester bugs.
        
        Args:
            delivered_stories: List of delivered development stories
            bugs: List of all bugs in the sprint
            
        Returns:
            Tuple of (support_bugs_per_story, tester_bugs_per_story)
        """
        if not delivered_stories:
            return 0.0, 0.0
        
        # Get story keys and epics for matching
        story_keys = {story.key for story in delivered_stories}
        story_epics = {story.epic_key for story in delivered_stories if story.epic_key}
        
        support_bug_count = 0
        tester_bug_count = 0
        
        for bug in bugs:
            if DefectService._is_bug_related_to_stories(bug, story_keys, story_epics):
                if DefectService._is_support_bug(bug):
                    support_bug_count += 1
                if DefectService._is_tester_bug(bug):
                    tester_bug_count += 1
        
        story_count = len(delivered_stories)
        return (
            support_bug_count / story_count,
            tester_bug_count / story_count
        )

    @staticmethod
    def _is_bug_related_to_stories(
        bug: IssueSnapshot,
        story_keys: set,
        story_epics: set
    ) -> bool:
        """Check if a bug is related to delivered stories.
        
        Args:
            bug: Bug issue to check
            story_keys: Set of delivered story keys
            story_epics: Set of epic keys from delivered stories
            
        Returns:
            True if bug is related to delivered stories
        """
        # Check if bug is linked to any delivered story
        for link in bug.linked_issues:
            if link in story_keys:
                return True
        
        # Check if bug is in same epic as delivered stories
        if bug.epic_key and bug.epic_key in story_epics:
            return True
        
        return False

    @staticmethod
    def _is_support_bug(bug: IssueSnapshot) -> bool:
        """Check if a bug is a support bug.
        
        Args:
            bug: Bug issue to check
            
        Returns:
            True if it's a support bug
        """
        # Check labels
        bug_labels = {label.lower() for label in bug.labels}
        support_labels = {label.lower() for label in SUPPORT_LABELS}
        
        if bug_labels.intersection(support_labels):
            return True
        
        # Check epic name
        if bug.epic_name and bug.epic_name.strip().lower() == SUPPORT_EPIC_NAME.lower():
            return True
        
        return False

    @staticmethod
    def _is_tester_bug(bug: IssueSnapshot) -> bool:
        """Check if a bug is a tester bug.
        
        Args:
            bug: Bug issue to check
            
        Returns:
            True if it's a tester bug
        """
        bug_labels = {label.lower() for label in bug.labels}
        return TESTER_LABEL.lower() in bug_labels
