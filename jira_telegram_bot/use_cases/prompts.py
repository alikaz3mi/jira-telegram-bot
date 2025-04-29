from __future__ import annotations

from typing import Dict

COMPONENT_TASK_TEMPLATES = {
    "frontend": """
    Component: Frontend Development
    Consider:
    - User interface components needed
    - State management requirements
    - API integration points
    - Responsive design requirements
    - Browser compatibility
    - Performance optimizations
    - Form validations
    - Error handling patterns
    """,
    "backend": """
    Component: Backend Development
    Consider:
    - API endpoints required
    - Database schema changes
    - Data validation rules
    - Authentication/Authorization
    - Rate limiting
    - Caching strategies
    - Error handling and logging
    - Performance considerations
    """,
    "AI": """
    Component: AI/NLP Development
    Consider:
    - Model selection/training requirements
    - Data preprocessing needs
    - Integration with existing AI pipeline
    - Performance metrics
    - Error handling and fallbacks
    - Model evaluation criteria
    - Scalability considerations
    """,
    "DevOPS": """
    Component: DevOps/Infrastructure
    Consider:
    - Deployment requirements
    - Infrastructure changes needed
    - Monitoring and alerting
    - Backup and recovery
    - Security considerations
    - Performance optimization
    - Resource scaling
    """,
    "UI/UX": """
    Component: UI/UX Design
    Consider:
    - User flow diagrams
    - Wireframe requirements
    - Design system updates
    - Usability testing needs
    - Accessibility requirements
    - Design documentation
    - User research tasks
    """,
}

COMPLEXITY_GUIDELINES = {
    "story_points": {
        "1-2": "Very simple changes with minimal risk",
        "3-5": "Standard complexity, well-understood work",
        "8": "Complex changes affecting multiple components",
        "13": "Very complex work with significant uncertainty",
    },
    "subtask_points": {
        "0.5": "Trivial changes (< 2 hours)",
        "1": "Simple, straightforward tasks (2-4 hours)",
        "2": "Standard complexity (4-8 hours)",
        "3": "More complex tasks (1-1.5 days)",
        "5": "Complex tasks requiring deep focus (2-3 days)",
        "8": "Very complex tasks (3-4 days)",
    },
}


def get_component_prompt(component: str) -> str:
    """Get the template for a specific component."""
    return COMPONENT_TASK_TEMPLATES.get(
        component,
        "Consider:\n- Technical requirements\n- Dependencies\n- Testing needs",
    )


def get_complexity_guidelines() -> Dict[str, Dict[str, str]]:
    """Get the story point guidelines."""
    return COMPLEXITY_GUIDELINES


task_statistics = """
You are a JIRA query assistant. Your task is to translate complex natural language user requests into JIRA Query Language (JQL) format.
The user will provide a query in plain English, and you will convert it into a precise JQL statement that can be used in JIRA to retrieve or calculate the desired information.

Capabilities:

Filter by multiple criteria: Assignee, project, issue type, status, priority, components, etc.
Date range filtering: Filter based on creation date, due date, or update date.
Sprint and Agile board queries: Filter issues by the current sprint or specific Agile boards.
Aggregation and calculation: Sum, average, or estimate fields like time tracking, story points, etc.
Examples:

User Query: "Show all tasks assigned to John Doe that are due next week."
JIRA Query: assignee = "John Doe" AND due >= startOfWeek(1) AND due <= endOfWeek(1)

User Query: "Find all open bugs in the 'Mobile App' project."
JIRA Query: project = "Mobile App" AND issuetype = Bug AND status = Open

User Query: "List all high-priority issues updated in the last 24 hours."
JIRA Query: priority = High AND updated >= -1d

User Query: "Sum and estimate the time remaining for each component to be completed in the current sprint."
JIRA Query: Sprint in openSprints() AND remainingEstimate is not EMPTY ORDER BY component ASC


User Query: "Calculate the total story points of all 'In Progress' issues for the current sprint."
JIRA Query: status = "In Progress" AND Sprint in openSprints() AND "Story Points" is not EMPTY

Now, translate the following user query into a JIRA query:

User Query: {user_query}

JIRA Query:


"""
