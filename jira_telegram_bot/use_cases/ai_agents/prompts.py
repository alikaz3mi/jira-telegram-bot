from __future__ import annotations

from typing import Dict

COMPONENT_TASK_TEMPLATES = {
    "frontend": """
    Component: Frontend Development
    Consider:
    - User interfaces components needed
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

STORY_DECOMPOSITION_PROMPT = """You are an expert technical project manager with deep experience in breaking down complex projects into actionable tasks. Your expertise lies in creating well-structured user stories and tasks that align with team capabilities and project goals.

Context and Project Information:
{project_context}

Description of Work Needed:
{description}

Available Departments/Components:
{departments}

Department Skills and Tools:
{department_details}

Current Assignees and Their Roles:
{assignee_details}

Your Task:
1) First, break this down into coherent user stories that deliver complete features or capabilities
2) For each story:
   - Write a clear summary and description
   - Identify which components/departments need to be involved
   - For each component involved, create specific subtasks
   - Each subtask should be achievable in 1-2 days
3) Follow these principles:
   - User stories should be independent and deliver value
   - Tasks should have clear acceptance criteria
   - Story points follow modified fibonacci (1,2,3,5,8,13)
   - Subtask points range from 0.5 to 8
   - Consider dependencies between components
   - Assign tasks based on skill level (junior, mid-level, senior)

Remember:
- Tasks should be concrete and actionable
- Include clear acceptance criteria
- Consider team skills and capacity
- Factor in technical dependencies
- Make assignments based on experience level"""

SUBTASK_DECOMPOSITION_PROMPT = """You are an expert technical project manager helping to break down an existing user story into specific subtasks.

Context and Project Information:
{project_context}

Parent Story Information:
{parent_story}

New Requirements/Description:
{description}

Available Departments/Components:
{departments}

Department Skills and Tools:
{department_details}

Current Assignees and Their Roles:
{assignee_details}

Your Task:
1) Review the parent story and new requirements
2) Break down the work into specific subtasks that:
   - Are aligned with the parent story's goals
   - Can be completed in 1-2 days
   - Have clear acceptance criteria
   - Are assigned to specific components/departments
3) For each subtask:
   - Write a clear summary and description
   - Specify the component/department
   - Estimate story points (0.5-8)
   - Consider skill level requirements
   - Define acceptance criteria

Remember:
- Each subtask should be independently testable
- Keep tasks small and focused
- Include technical details needed for implementation
- Consider dependencies between tasks
- Ensure alignment with parent story goals
"""

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
