from enum import Enum

class JiraStatus(str, Enum):
    """Jira status enum."""
    TO_DO = "To Do"
    IN_PROGRESS = "In Progress"
    DONE = "Done"
    BLOCKED = "Blocked"
    IN_REVIEW = "In Review"
    IN_TESTING = "In Testing"
    SELECTED_FOR_DEVELOPMENT = "Selected for Development"
    
