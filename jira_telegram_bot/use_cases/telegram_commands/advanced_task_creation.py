from __future__ import annotations

import json
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from jira import Issue

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class AdvancedTaskCreation:
    """Handles creation of multiple related tasks with subtasks through AI analysis."""

    def __init__(
        self,
        task_manager_repository: TaskManagerRepositoryInterface,
        user_config: UserConfigInterface,
    ):
        self.task_manager_repository = task_manager_repository
        self.user_config = user_config

    async def create_tasks(
        self,
        description: str,
        project_key: str,
        epic_key: Optional[str] = None,
        parent_story_key: Optional[str] = None,
        task_type: str = "story",  # "story" or "subtask"
    ) -> List[TaskData]:
        """Create multiple stories with their component-specific subtasks.

        Args:
            description: Detailed description of the work needed
            project_key: Jira project key
            epic_key: Optional epic to link stories to
            parent_story_key: Optional parent story for subtasks
            task_type: Either "story" (with subtasks) or "subtask" (add to existing story)

        Returns:
            List of created TaskData objects
        """
        # Load project info from projects_info.json
        project_info = await self._get_project_info(project_key)

        # Parse the tasks
        tasks_data = self._parse_task_description(
            description=description,
            project_info=project_info,
            task_type=task_type,
        )

        created_tasks = []

        if task_type == "story":
            await self.create_stories(created_tasks, epic_key, project_key, tasks_data)
        else:  # task_type == "subtask"
            await self.create_subtasks_for_story(
                created_tasks,
                parent_story_key,
                project_key,
                tasks_data,
            )

        return created_tasks

    @staticmethod
    async def _get_project_info(project_key: str):
        with open(
            f"{DEFAULT_PATH}/jira_telegram_bot/settings/projects_info.json",
            "r",
        ) as f:
            projects_info = json.load(f)
            project_info = projects_info.get(project_key)
        if not project_info:
            raise ValueError(f"No project info found for {project_key}")
        return project_info

    async def create_subtasks_for_story(
        self,
        created_tasks,
        parent_story_key,
        project_key,
        tasks_data,
    ):
        if not parent_story_key:
            raise ValueError("Parent story key is required for creating subtasks")
        for subtask in tasks_data["subtasks"]:
            subtask_data = TaskData(
                project_key=project_key,
                summary=subtask["summary"],
                description=subtask["description"],
                components=[subtask["component"]],
                story_points=subtask["story_points"],
                assignee=subtask.get("assignee"),
                task_type="Sub-task",
                parent_issue_key=parent_story_key,
            )
            subtask_issue = self.task_manager_repository.create_task(subtask_data)
            LOGGER.info(
                f"Subtask created: {subtask_issue.key} under parent story {parent_story_key}",
            )
            created_tasks.append(subtask_issue)

    async def create_stories(
        self,
        created_tasks,
        epic_key,
        project_key,
        tasks_data,
    ) -> List[Issue]:
        for story in tasks_data["stories"]:
            story_data = TaskData(
                project_key=project_key,
                summary=story["summary"],
                description=story["description"],
                components=[ct["component"] for ct in story["component_tasks"]],
                story_points=story["story_points"],
                task_type="Story",
                priority=story["priority"],
                epic_link=epic_key,
            )
            story_issue = self.task_manager_repository.create_task(story_data)
            created_tasks.append(story_issue)

            # Create subtasks for each component
            for comp_tasks in story["component_tasks"]:
                for subtask in comp_tasks["subtasks"]:
                    subtask_data = TaskData(
                        project_key=project_key,
                        summary=subtask["summary"],
                        description=subtask["description"],
                        components=[comp_tasks["component"]],
                        story_points=subtask["story_points"],
                        assignee=subtask.get("assignee"),
                        task_type="Sub-task",
                        parent_issue_key=story_issue.key,
                    )
                    subtask_issue = self.task_manager_repository.create_task(
                        subtask_data,
                    )
                    LOGGER.info(
                        f"Subtask created: {subtask_issue.key} under parent story {story_issue.key}",
                    )
                    created_tasks.append(subtask_issue)
        return created_tasks

    async def create_structured_user_story(
        self,
        description: str,
        project_key: str,
        epic_key: Optional[str] = None,
        parent_story_key: Optional[str] = None,
    ) -> TaskData:
        """Create a well-structured user story following agile best practices.

        Uses AI to generate a comprehensive user story with acceptance criteria,
        non-functional requirements, and definition of done based on the provided
        description. If epic or parent story keys are provided, their context will be
        incorporated into the user story creation.

        Args:
            description: Detailed description of the work needed
            project_key: Jira project key
            epic_key: Optional epic to link the story to
            parent_story_key: Optional parent story to enhance with this user story

        Returns:
            TaskData object of the created or updated story
        """
        # Load project info from projects_info.json
        project_info = await self._get_project_info(project_key)

        # Gather context from existing stories/epics if available
        epic_context = {}
        parent_story_context = {}

        if epic_key:
            epic_issue = self.task_manager_repository.get_issue(epic_key)
            if epic_issue:
                epic_context = {
                    "key": epic_key,
                    "summary": epic_issue.fields.summary,
                    "description": epic_issue.fields.description or "",
                }

        if parent_story_key:
            parent_issue = self.task_manager_repository.get_issue(parent_story_key)
            if parent_issue:
                parent_story_context = {
                    "key": parent_story_key,
                    "summary": parent_issue.fields.summary,
                    "description": parent_issue.fields.description or "",
                }

        # Generate structured user story
        user_story_content = await self._generate_structured_user_story(
            description=description,
            project_info=project_info,
            epic_context=epic_context,
            parent_story_context=parent_story_context,
        )

        # Create or update the task
        if parent_story_key:
            # Update existing story with enhanced content
            parent_issue = self.task_manager_repository.get_issue(parent_story_key)

            # Generate updated description that preserves original content
            original_description = parent_issue.fields.description or ""
            updated_description = self._merge_descriptions(
                original_description,
                user_story_content["description"],
            )

            issue_fields = {
                # "summary": user_story_content["summary"],
                "description": updated_description,
            }
            story_data = TaskData(
                project_key=project_key,
                summary=user_story_content["summary"],
                description=updated_description,
                components=[user_story_content["component"]],
                story_points=user_story_content.get("story_points", 5),
                task_type="Story",
                priority=user_story_content.get("priority", "Medium"),
            )

            # Update the existing story
            self.task_manager_repository.update_issue_from_fields(
                parent_story_key,
                issue_fields,
            )
            LOGGER.info(
                f"Updated existing story: {parent_story_key} with new content",
            )
            return story_data
        else:
            # Create new story
            components = []
            if "component" in user_story_content:
                components = [user_story_content["component"]]

            story_data = TaskData(
                project_key=project_key,
                summary=user_story_content["summary"],
                description=user_story_content["description"],
                components=components,
                story_points=user_story_content.get("story_points", 5),
                task_type="Story",
                priority=user_story_content.get("priority", "Medium"),
                epic_link=epic_key,
            )

            # Create the new story
            new_issue = self.task_manager_repository.create_task(story_data)
            LOGGER.info(
                f"Created new story: {new_issue.key} with structured content",
            )
            return story_data

    async def _generate_structured_user_story(
        self,
        description: str,
        project_info: Dict[str, Any],
        epic_context: Dict[str, Any] = None,
        parent_story_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Generate structured user story content using AI.

        Args:
            description: The detailed task description
            project_info: Project configuration information
            epic_context: Optional context from linked epic
            parent_story_context: Optional context from parent story

        Returns:
            Dictionary containing user story content
        """
        epic_context = epic_context or {}
        parent_story_context = parent_story_context or {}

        # Extract business goals from project info
        business_goal = project_info.get("project_info", {}).get(
            "objective",
            "Improve user experience",
        )

        # Extract product area from project info
        product_area = project_info.get("project_info", {}).get(
            "description",
            "Software Product",
        )

        # Main personas from project info if available
        primary_persona = "User"
        if "personas" in project_info:
            primary_persona = next(iter(project_info["personas"]), "User")

        # Define the schema for the structured output
        schema = [
            ResponseSchema(
                name="user_story",
                description="""Dictionary containing:
                summary (string): A concise title for the story,
                description (string): Full user story with narrative, acceptance criteria, and definition of done,
                component (string): Primary team/department responsible,
                story_points (number): Estimated story points (1-13),
                priority (string): High, Medium, or Low""",
                type="json",
            ),
        ]

        parser = StructuredOutputParser.from_response_schemas(schema)
        format_instructions = parser.get_format_instructions()

        # Create the prompt template for the user story
        template = """You are an experienced Agile Product Owner.

Context:

Product/Feature Area: {product_area}

Business Goal / OKR: {business_goal}

Primary Persona: {primary_persona}

Dependencies / Constraints: {dependencies}

Description of work: {description}

{epic_context}

{parent_story_context}

Instructions:

Write one INVEST-compliant user story in the format:
'As a <persona role>, I want <capability> so that <benefit/value>.'

Add a concise narrative (≤ 3 sentences) that explains why this story matters to the business goal.

Provide Acceptance Criteria using Gherkin-style "Given / When / Then" bullets (≥ 3 distinct criteria, covering happy-path and one edge case).

List Non-functional Requirements that could cause the story to fail if ignored (e.g., performance, security, accessibility).

Suggest Sizing hints (story-points or T-shirt size) with a short rationale.

Suggest Risks & Open Questions the team should discuss during refinement.

End with a Definition of Done checklist that references code, tests, documentation, and release validation.

Tone & Style:
- Clear, testable, and free of jargon
- Bullet points where possible
- Avoid passive voice
- Generate the result in google doc format
- Use markdown for formatting
- Generate the story in fluent Farsi.

{format_instructions}
"""

        # Format the epic context if available
        epic_context_text = ""
        if epic_context:
            epic_context_text = f"""Epic Information:
Epic Key: {epic_context.get('key', '')}
Epic Summary: {epic_context.get('summary', '')}
Epic Description: {epic_context.get('description', '')}"""

        # Format the parent story context if available
        parent_context_text = ""
        if parent_story_context:
            parent_context_text = f"""Parent Story Information:
Story Key: {parent_story_context.get('key', '')}
Story Summary: {parent_story_context.get('summary', '')}
Story Description: {parent_story_context.get('description', '')}"""

        prompt = PromptTemplate(
            template=template,
            input_variables=[
                "product_area",
                "business_goal",
                "primary_persona",
                "dependencies",
                "description",
                "epic_context",
                "parent_story_context",
            ],
            partial_variables={"format_instructions": format_instructions},
        )

        # Extract dependencies from description or use default
        # This would ideally use NLP to identify dependencies in the text
        dependencies = "Integration with existing systems required"

        # Get the response from LLM
        llm_response = self.llm.invoke(
            prompt.format(
                product_area=product_area,
                business_goal=business_goal,
                primary_persona=primary_persona,
                dependencies=dependencies,
                description=description,
                epic_context=epic_context_text,
                parent_story_context=parent_context_text,
            ),
        )

        # Extract the content as a string
        content = llm_response.content

        try:
            # Parse the structured output
            parsed_data = parser.parse(content)
            return parsed_data["user_story"]
        except Exception as e:
            # Fallback in case of parsing error
            return {
                "summary": "User story based on description",
                "description": f"""As a user, I want the described functionality so that I can achieve my goals.

{description}

**Acceptance Criteria:**
- Given the system is set up, when the functionality is used, then it works as expected.
- Given an error occurs, when the user interacts with the system, then appropriate feedback is provided.
- Given the user completes their task, when they review their work, then they can see the results.

**Definition of Done:**
- Code is written and tested
- Documentation is updated
- Changes are reviewed and approved""",
                "component": list(project_info["departments"].keys())[0],
                "story_points": 5,
                "priority": "Medium",
            }

    def _merge_descriptions(self, original: str, new_content: str) -> str:
        """Merge original description with new user story content.

        Args:
            original: Original description text
            new_content: New user story content to add

        Returns:
            Combined description preserving both contents
        """
        # If original is empty, just return new content
        if not original or original.strip() == "":
            return new_content

        # Check if original already has user story formatting
        if "As a " in original and "I want " in original and "so that " in original:
            # Already has user story format, update acceptance criteria and other sections

            # Extract sections from new content
            new_sections = {}
            possible_sections = [
                "Acceptance Criteria",
                "Non-functional Requirements",
                "Sizing",
                "Risks & Open Questions",
                "Definition of Done",
            ]

            for section in possible_sections:
                if section in new_content:
                    start_idx = new_content.find(section)
                    next_section_idx = float("inf")
                    for next_section in possible_sections:
                        if (
                            next_section != section
                            and next_section in new_content[start_idx + len(section) :]
                        ):
                            section_idx = (
                                new_content[start_idx + len(section) :].find(
                                    next_section,
                                )
                                + start_idx
                                + len(section)
                            )
                            next_section_idx = min(next_section_idx, section_idx)

                    if next_section_idx < float("inf"):
                        new_sections[section] = new_content[
                            start_idx:next_section_idx
                        ].strip()
                    else:
                        new_sections[section] = new_content[start_idx:].strip()

            # Update or append each section
            result = original
            for section, content in new_sections.items():
                if section in result:
                    # Update existing section
                    start_idx = result.find(section)
                    next_section_idx = float("inf")
                    for next_section in possible_sections:
                        if (
                            next_section != section
                            and next_section in result[start_idx + len(section) :]
                        ):
                            section_idx = (
                                result[start_idx + len(section) :].find(next_section)
                                + start_idx
                                + len(section)
                            )
                            next_section_idx = min(next_section_idx, section_idx)

                    if next_section_idx < float("inf"):
                        result = (
                            result[:start_idx] + content + result[next_section_idx:]
                        )
                    else:
                        result = result[:start_idx] + content
                else:
                    # Append new section
                    result += f"\n\n{content}"

            return result
        else:
            # Doesn't have user story format, preserve original as context
            return f"""**Original Description:**
{original}

**Enhanced User Story:**
{new_content}"""

    def _parse_task_description(
        self,
        description: str,
        project_info: Dict[str, Any],
        task_type: str,
    ) -> Dict[str, Any]:
        """Analyze task description and return structured task data.

        Args:
            description: The detailed task description
            project_info: Project configuration information
            task_type: Either "story" or "subtask"

        Returns:
            Dictionary containing parsed tasks information
        """
        # Format department details
        dept_details = []
        for dept, info in project_info["departments"].items():
            dept_details.append(
                f"{dept}:\n- {info['description']}\n- Tools: {', '.join(info['tools'])}\n- Weekly Hours: {info['time_allocation_weekly_hours']}",
            )

        # Format assignee details
        assignee_details = []
        for assignee in project_info["assignees"]:
            assignee_details.append(
                f"{assignee['username']} ({assignee['role']}) - {assignee['department']}",
            )

        # Define schema based on task type
        if task_type == "story":
            schema = [
                ResponseSchema(
                    name="stories",
                    description="""Array of story objects. Each story has:
                    summary (string),
                    description (string),
                    story_points (number between 1-13),
                    priority (string: High, Medium, Low),
                    component_tasks (array of component task objects)""",
                    type="json",
                ),
            ]
        else:  # subtask
            schema = [
                ResponseSchema(
                    name="subtasks",
                    description="""Array of subtask objects. Each subtask has:
                    summary (string),
                    description (string),
                    story_points (number between 0.5-8),
                    component (string),
                    assignee (string, optional)""",
                    type="json",
                ),
            ]

        parser = StructuredOutputParser.from_response_schemas(schema)
        format_instructions = parser.get_format_instructions()

        # Create the prompt template
        if task_type == "story":
            template = """You are an expert technical project manager with deep experience in breaking down complex projects into actionable tasks.

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
1) Break this down into coherent user stories that deliver complete features or capabilities
2) For each story:
   - Write a clear summary and description
    - Generate description in markdown format
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

{format_instructions}"""
        else:  # subtask
            template = """You are an expert technical project manager who specializes in breaking down tasks into actionable subtasks.

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
1) Break this down into specific subtasks that can each be completed in 1-2 days
2) For each subtask:
   - Create a clear summary and description with acceptance criteria
   - Generate description in markdown format
   - Assign to appropriate component/department
   - Estimate story points (0.5-8)
   - Consider which team member is best suited (optional)
3) Ensure subtasks are:
   - Concrete and actionable
   - Have clear success criteria
   - Properly sized for 1-2 days of work

{format_instructions}"""

        prompt = PromptTemplate(
            template=template,
            input_variables=[
                "project_context",
                "description",
                "departments",
                "department_details",
                "assignee_details",
            ],
            partial_variables={"format_instructions": format_instructions},
        )

        # Get the response from LLM
        llm_response = self.llm.invoke(
            prompt.format(
                project_context=project_info["project_info"]["description"],
                description=description,
                departments=", ".join(project_info["departments"].keys()),
                department_details="\n\n".join(dept_details),
                assignee_details="\n".join(assignee_details),
            ),
        )

        # Extract the content as a string
        content = llm_response.content

        try:
            # Parse the structured output
            parsed_data = parser.parse(content)

            # Assign tasks based on skill levels for stories
            if task_type == "story" and "stories" in parsed_data:
                parsed_data = self._assign_tasks(parsed_data, project_info)

            return parsed_data
        except Exception as e:
            LOGGER.error(f"Error parsing task description: {e}")
            # Fallback in case of parsing error
            if task_type == "story":
                return {
                    "stories": [
                        {
                            "summary": "Unable to parse description",
                            "description": description,
                            "story_points": 3,
                            "priority": "Medium",
                            "component_tasks": [
                                {
                                    "component": list(
                                        project_info["departments"].keys(),
                                    )[0],
                                    "subtasks": [
                                        {
                                            "summary": "Investigate requirements",
                                            "description": description,
                                            "story_points": 3,
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                }
            else:
                return {
                    "subtasks": [
                        {
                            "summary": "Investigate requirements",
                            "description": description,
                            "story_points": 3,
                            "component": list(project_info["departments"].keys())[0],
                        },
                    ],
                }

    def _assign_tasks(
        self,
        parsed_data: Dict[str, Any],
        project_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assign tasks to team members based on skill levels and department.

        Args:
            parsed_data: The parsed task data
            project_info: Project configuration information

        Returns:
            Updated task data with assignments
        """
        # Get department leads and members
        dept_leads = {comp["name"]: comp["lead"] for comp in project_info["components"]}
        dept_members = {}
        for assignee in project_info["assignees"]:
            dept = assignee["department"]
            if dept not in dept_members:
                dept_members[dept] = []
            dept_members[dept].append(
                {
                    "username": assignee["username"],
                    "role": assignee["role"],
                },
            )

        # Assign tasks based on skill levels
        for story in parsed_data["stories"]:
            for comp_tasks in story["component_tasks"]:
                dept = comp_tasks["component"]
                if dept not in dept_members:
                    continue

                members = dept_members[dept]
                leader = dept_leads.get(dept)

                # Sort members by seniority for task allocation
                seniors = [m for m in members if m["role"] == "Senior Developer"]
                mid_levels = [m for m in members if m["role"] == "Mid-level Developer"]
                juniors = [m for m in members if m["role"] == "Junior Developer"]

                # Distribute tasks based on complexity (story points)
                self._distribute_tasks_based_on_complexity(
                    comp_tasks,
                    juniors,
                    leader,
                    mid_levels,
                    seniors,
                )

        return parsed_data

    @staticmethod
    def _distribute_tasks_based_on_complexity(
        comp_tasks,
        juniors,
        leader,
        mid_levels,
        seniors,
    ) -> Dict[str, Any]:
        for task in comp_tasks["subtasks"]:
            if task.get("assignee") is None:  # Only assign if not already assigned
                if task["story_points"] >= 5:  # Complex tasks
                    if seniors:
                        task["assignee"] = seniors[0]["username"]
                elif task["story_points"] >= 2:  # Medium tasks
                    if mid_levels:
                        task["assignee"] = mid_levels[0]["username"]
                    elif seniors:
                        task["assignee"] = seniors[0]["username"]
                else:  # Simple tasks
                    if juniors:
                        task["assignee"] = juniors[0]["username"]
                    elif mid_levels:
                        task["assignee"] = mid_levels[0]["username"]
                    elif seniors:
                        task["assignee"] = seniors[0]["username"]

                # If still no assignee, assign to department lead
                if not task.get("assignee") and leader:
                    task["assignee"] = leader
        return comp_tasks


if __name__ == "__main__":
    import asyncio
    from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import (
        JiraRepository,
    )
    from jira_telegram_bot.adapters.user_config import UserConfig
    from jira_telegram_bot.settings import JIRA_SETTINGS

    jira_repo = JiraRepository(
        settings=JIRA_SETTINGS,
    )
    task_creator = AdvancedTaskCreation(
        task_manager_repository=jira_repo,
        user_config=UserConfig(),
    )
    story_description = """The task is to connect to the widget through a JavaScript snippet.
    This story point belongs to the front-end department.
    It is estimated to take 16 hours to prepare this task, which includes changes to the service connection
    page with the ability to add a new section for connecting to the widget service.
    On this page, I need to modify the built JavaScript snippet for the user who enters the chat page,
    the plugin page. On the panel page, I should be able to copy the necessary code for his web clock
    and place it in his web clock."""

    # Example of using the new create_structured_user_story method
    result = asyncio.run(
        task_creator.create_structured_user_story(
            description=story_description,
            project_key="PARSCHAT",
            epic_key="PARSCHAT-15",
        ),
    )
    print(result.description)

    # # Original example
    # asyncio.run(
    #     task_creator.create_tasks(
    #         description=description,
    #         project_key="PARSCHAT",
    #         epic_key="PARSCHAT-15",
    #         task_type="subtask",
    #         parent_story_key="PARSCHAT-2296",  # Example parent key
    #     ),
    # )
