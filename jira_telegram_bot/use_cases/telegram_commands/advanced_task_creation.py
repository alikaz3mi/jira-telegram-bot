from __future__ import annotations

import aiohttp
import json
import tempfile
from io import BytesIO
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from langchain.output_parsers import ResponseSchema
from langchain.output_parsers import StructuredOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import GEMINI_SETTINGS as gemini_connection_settings
from jira_telegram_bot.use_cases.interface.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interface.user_config_interface import (
    UserConfigInterface,
)


class AdvancedTaskCreation:
    """Handles creation of multiple related tasks with subtasks through AI analysis."""

    def __init__(
        self,
        jira_repo: TaskManagerRepositoryInterface,
        user_config: UserConfigInterface,
    ):
        self.jira_repo = jira_repo
        self.user_config = user_config
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.2,
            google_api_key=gemini_connection_settings.token,
            convert_system_message_to_human=True,
        )

    async def create_tasks(
        self,
        description: str,
        project_key: str,
        epic_key: Optional[str] = None,
        parent_story_key: Optional[str] = None,
        task_type: str = "story",  # "story" or "subtask"
        attachments: Dict[str, List] = None,
    ) -> List[TaskData]:
        """Create multiple stories with their component-specific subtasks.

        Args:
            description: Detailed description of the work needed
            project_key: Jira project key
            epic_key: Optional epic to link stories to
            parent_story_key: Optional parent story for subtasks
            task_type: Either "story" (with subtasks) or "subtask" (add to existing story)
            attachments: Optional dictionary of file attachments to add to tasks

        Returns:
            List of created TaskData objects
        """
        # Load project info from projects_info.json
        with open(
            f"{DEFAULT_PATH}/jira_telegram_bot/settings/projects_info.json",
            "r",
        ) as f:
            projects_info = json.load(f)
            project_info = projects_info.get(project_key)

        if not project_info:
            raise ValueError(f"No project info found for {project_key}")

        try:
            # Parse the tasks
            tasks_data = self._parse_task_description(
                description=description,
                project_info=project_info,
                task_type=task_type,
            )
    
            created_tasks = []
    
            # Validate and sanitize the parsed data
            self._validate_tasks_data(tasks_data, project_info, task_type)
        except Exception as e:
            LOGGER.error(f"Error preparing task data: {str(e)}")
            # Provide fallback simple task data
            if task_type == "story":
                tasks_data = {
                    "stories": [{
                        "summary": "Story from requirements",
                        "description": description,
                        "story_points": 3,
                        "priority": "Medium",
                        "component_tasks": [{
                            "component": list(project_info["departments"].keys())[0],
                            "subtasks": [{
                                "summary": "Implement requirements",
                                "description": "Implement the requirements as described.",
                                "story_points": 3
                            }]
                        }]
                    }]
                }
            else:  # subtask
                tasks_data = {
                    "subtasks": [{
                        "summary": "Subtask from requirements",
                        "description": description,
                        "story_points": 3,
                        "component": list(project_info["departments"].keys())[0],
                    }]
                }

        if task_type == "story":
            for story in tasks_data["stories"]:
                # Create the main story
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
                
                # Add attachments to the story if provided
                if attachments:
                    for attachment_type, files in attachments.items():
                        story_data.attachments[attachment_type].extend(files)
                
                story_issue = self.jira_repo.create_task(story_data)
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
                        subtask_issue = self.jira_repo.create_task(subtask_data)
                        LOGGER.info(
                            f"Subtask created: {subtask_issue.key} under parent story {story_issue.key}",
                        )
                        created_tasks.append(subtask_issue)

        else:  # task_type == "subtask"
            if not parent_story_key:
                raise ValueError("Parent story key is required for creating subtasks")

            for subtask in tasks_data["subtasks"]:
                subtask_data = TaskData(
                    project_key=project_key,
                    summary=subtask["summary"],
                    description=subtask["description"],
                    components=[subtask["component"]],
                    story_points=subtask["story_points"] / 8,
                    assignee=subtask.get("assignee"),
                    task_type="Sub-task",
                    parent_issue_key=parent_story_key,
                )
                
                # Only add attachments to the first subtask if provided
                # This avoids duplicating attachments across all subtasks
                if attachments and subtask == tasks_data["subtasks"][0]:
                    for attachment_type, files in attachments.items():
                        subtask_data.attachments[attachment_type].extend(files)
                
                subtask_issue = self.jira_repo.create_task(subtask_data)
                LOGGER.info(
                    f"Subtask created: {subtask_issue.key} under parent story {parent_story_key}",
                )
                created_tasks.append(subtask_issue)

        return created_tasks

    async def create_structured_user_story(
        self,
        description: str,
        project_key: str,
        epic_key: Optional[str] = None,
        parent_story_key: Optional[str] = None,
        attachments: Dict[str, List] = None,
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
        with open(
            f"{DEFAULT_PATH}/jira_telegram_bot/settings/projects_info.json",
            "r",
        ) as f:
            projects_info = json.load(f)
            project_info = projects_info.get(project_key)

        if not project_info:
            raise ValueError(f"No project info found for {project_key}")

        # Gather context from existing stories/epics if available
        epic_context = {}
        parent_story_context = {}

        if epic_key:
            epic_issue = self.jira_repo.get_issue(epic_key)
            if epic_issue:
                epic_context = {
                    "key": epic_key,
                    "summary": epic_issue.fields.summary,
                    "description": epic_issue.fields.description or "",
                }

        if parent_story_key:
            parent_issue = self.jira_repo.get_issue(parent_story_key)
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
            parent_issue = self.jira_repo.get_issue(parent_story_key)

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
            self.jira_repo.update_issue_from_fields(
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
            
            try:
                # Make sure we're using department names as components, not epic names
                if "component" in user_story_content and user_story_content["component"] in project_info["departments"]:
                    components = [user_story_content["component"]]
                elif project_info["departments"]:
                    # Default to first department if component is invalid or missing
                    first_dept = next(iter(project_info["departments"]))
                    components = [first_dept]
                    LOGGER.warning(f"Invalid component '{user_story_content.get('component')}' replaced with '{first_dept}'")
                else:
                    # If no departments are found in project info (shouldn't happen but for safety)
                    components = ["Default"]
                    LOGGER.error("No departments found in project info, using 'Default' component")
            except Exception as e:
                LOGGER.error(f"Error processing component: {str(e)}")
                # Safe fallback
                components = ["Default"]

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
            
            # Add attachments to the story if provided
            if attachments:
                for attachment_type, files in attachments.items():
                    story_data.attachments[attachment_type].extend(files)

            # Create the new story
            new_issue = self.jira_repo.create_task(story_data)
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
                component (string): Primary team/department responsible (must be one of the available departments, not an epic name),
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

IMPORTANT: For the "component" field, use ONLY one of the available departments listed at the beginning of the prompt (e.g., "Front-end", "Backend", etc.). Do NOT use epic names as components.

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
- Generate the story description in fluent Farsi.
- Choose components and assignee only based on the given input and do not add any other information.

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
3) IMPORTANT: Analyze the description carefully to identify any specific assignees mentioned. For example, if the description says "John should handle the API integration" or "This task is for Sarah", then assign those tasks to John or Sarah accordingly.
4) Follow these principles:
   - User stories should be independent and deliver value
   - Tasks should have clear acceptance criteria
   - Story points for Story follow modified fibonacci (1,2,3,5,8,13)
   - Subtask story points range from 0.25 to 2
   - Consider dependencies between components
   - ONLY if assignees are not explicitly mentioned in the description, assign tasks based on skill level (junior, mid-level, senior)
   - For each subtask, include an "assignee" field with the username if you can determine it from the description

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
   - PRIORITY: Carefully analyze the description to identify any explicitly mentioned assignees. For example, if it says "Ali should implement the login feature" or "This component should be handled by Mina", assign those tasks to those specific people.
   - You MUST set the "assignee" field for each subtask based on names mentioned in the description
   - Estimate story points (0.5-8)
3) Ensure subtasks are:
   - Concrete and actionable
   - Have clear success criteria
   - Properly sized for 1-2 days of work
4) Rules for assignee extraction:
   - If a person is directly mentioned with a task (e.g., "John will work on the API"), assign that specific task to them
   - If the description has general assignments (e.g., "Frontend tasks go to Sara"), use that for all relevant components
   - ONLY if no assignee can be determined from the description for a specific task, leave it for the automatic assignment based on skills

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
                mids = [m for m in members if m["role"] == "Mid-level Developer"]
                juniors = [m for m in members if m["role"] == "Junior Developer"]

                # Distribute tasks based on complexity (story points)
                for task in comp_tasks["subtasks"]:
                    # Validate required fields first
                    if "summary" not in task or not task["summary"]:
                        task["summary"] = "Task needs description"
                        LOGGER.warning(f"Missing summary in task under component {dept}, adding default summary")
                    
                    # Check if assignee has already been specified by the LLM from the description
                    # Do NOT auto-assign tasks - leave them unassigned if no assignee was extracted
                    if task.get("assignee") is None or task.get("assignee") == "":
                        LOGGER.info(f"No assignee found in description for task: {task.get('summary')}, leaving unassigned")
                        # Do not auto-assign; leave task unassigned
                        if "assignee" in task:
                            del task["assignee"]
                    else:
                        # Keep the explicitly mentioned assignee
                        LOGGER.info(f"Using assignee '{task['assignee']}' extracted from description for task: {task.get('summary')}")

        return parsed_data

    async def fetch_and_store_media(
        self,
        media_file,
        session: aiohttp.ClientSession,
        storage_list: List,
        filename: str,
    ) -> None:
        """Fetch media from Telegram and store it for attachment to Jira.

        Args:
            media_file: The media file object from Telegram
            session: aiohttp client session
            storage_list: List to store the fetched media in
            filename: Name of the file to save

        Returns:
            None
        """
        try:
            file_url = media_file.file_path
            async with session.get(file_url) as response:
                if response.status == 200:
                    buffer = BytesIO(await response.read())
                    storage_list.append((filename, buffer))
                    LOGGER.info(f"Successfully fetched media: {filename}")
                else:
                    LOGGER.error(
                        f"Failed to fetch media: {filename}, status: {response.status}",
                    )
        except Exception as e:
            LOGGER.error(f"Error fetching media: {e}")

    async def process_media_group(
        self,
        messages: List[Any],
        attachments: Dict[str, List],
    ) -> None:
        """Process a group of media messages.

        Args:
            messages: List of media messages
            attachments: Dictionary to store attachments

        Returns:
            None
        """
        if not messages:
            return

        async with aiohttp.ClientSession() as session:
            for idx, message in enumerate(messages):
                if message.photo:
                    media_file = await message.photo[-1].get_file()
                    await self.fetch_and_store_media(
                        media_file,
                        session,
                        attachments["images"],
                        f"group_image_{idx}.jpg",
                    )
                elif message.video:
                    media_file = await message.video.get_file()
                    await self.fetch_and_store_media(
                        media_file,
                        session,
                        attachments["videos"],
                        f"group_video_{idx}.mp4",
                    )
                elif message.audio:
                    media_file = await message.audio.get_file()
                    await self.fetch_and_store_media(
                        media_file,
                        session,
                        attachments["audio"],
                        f"group_audio_{idx}.mp3",
                    )
                elif message.document:
                    media_file = await message.document.get_file()
                    filename = message.document.file_name or f"document_{idx}"
                    await self.fetch_and_store_media(
                        media_file,
                        session,
                        attachments["documents"],
                        filename,
                    )

    async def process_single_media(
        self,
        message: Any,
        attachments: Dict[str, List],
    ) -> None:
        """Process a single media message.

        Args:
            message: The media message
            attachments: Dictionary to store attachments

        Returns:
            None
        """
        async with aiohttp.ClientSession() as session:
            if message.photo:
                media_file = await message.photo[-1].get_file()
                await self.fetch_and_store_media(
                    media_file,
                    session,
                    attachments["images"],
                    "single_image.jpg",
                )
            elif message.video:
                media_file = await message.video.get_file()
                await self.fetch_and_store_media(
                    media_file,
                    session,
                    attachments["videos"],
                    "video.mp4",
                )
            elif message.audio:
                media_file = await message.audio.get_file()
                await self.fetch_and_store_media(
                    media_file,
                    session,
                    attachments["audio"],
                    "audio.mp3",
                )
            elif message.document:
                media_file = await message.document.get_file()
                filename = message.document.file_name or "document"
                await self.fetch_and_store_media(
                    media_file,
                    session,
                    attachments["documents"],
                    filename,
                )

    def _validate_tasks_data(
        self,
        tasks_data: Dict[str, Any],
        project_info: Dict[str, Any],
        task_type: str,
    ) -> None:
        """Validate and sanitize task data before task creation.
        
        This method checks for required fields and ensures components 
        are valid departments from the project info.
        
        Args:
            tasks_data: The task data to validate
            project_info: The project information
            task_type: Either "story" or "subtask"
            
        Returns:
            None
        """
        departments = list(project_info["departments"].keys())
        
        if task_type == "story" and "stories" in tasks_data:
            for i, story in enumerate(tasks_data["stories"]):
                # Validate required story fields
                if "summary" not in story or not story["summary"]:
                    tasks_data["stories"][i]["summary"] = "Untitled Story"
                    LOGGER.warning("Missing story summary, using default")
                    
                if "description" not in story:
                    tasks_data["stories"][i]["description"] = "No description provided"
                    
                if "priority" not in story:
                    tasks_data["stories"][i]["priority"] = "Medium"
                    
                if "story_points" not in story:
                    tasks_data["stories"][i]["story_points"] = 3
                    
                # Validate component tasks
                if "component_tasks" not in story or not story["component_tasks"]:
                    # Create a default component task with the first department
                    tasks_data["stories"][i]["component_tasks"] = [{
                        "component": departments[0] if departments else "Default",
                        "subtasks": [{
                            "summary": "Implement " + story.get("summary", "requirements"),
                            "description": "Implement the requirements described in the story.",
                            "story_points": 3
                        }]
                    }]
                    LOGGER.warning(f"Missing component tasks for story, creating default with {departments[0]}")
                else:
                    # Validate each component task
                    for j, comp_task in enumerate(story["component_tasks"]):
                        # Validate component is a valid department
                        if "component" not in comp_task or comp_task["component"] not in departments:
                            # Replace with first available department
                            tasks_data["stories"][i]["component_tasks"][j]["component"] = departments[0] if departments else "Default"
                            LOGGER.warning(f"Invalid component in task, replaced with {departments[0]}")
                            
                        # Validate subtasks
                        if "subtasks" not in comp_task or not comp_task["subtasks"]:
                            tasks_data["stories"][i]["component_tasks"][j]["subtasks"] = [{
                                "summary": f"Implement {story.get('summary', 'requirements')} for {comp_task.get('component', 'department')}",
                                "description": "Implement the requirements described in the story.",
                                "story_points": 3
                            }]
                            LOGGER.warning(f"Missing subtasks for component {comp_task.get('component')}, creating default")
                        else:
                            # Validate each subtask
                            for k, subtask in enumerate(comp_task["subtasks"]):
                                if "summary" not in subtask or not subtask["summary"]:
                                    tasks_data["stories"][i]["component_tasks"][j]["subtasks"][k]["summary"] = f"Subtask for {comp_task.get('component', 'department')}"
                                    LOGGER.warning("Missing subtask summary, using default")
                                    
                                if "description" not in subtask:
                                    tasks_data["stories"][i]["component_tasks"][j]["subtasks"][k]["description"] = "No description provided"
                                    
                                if "story_points" not in subtask:
                                    tasks_data["stories"][i]["component_tasks"][j]["subtasks"][k]["story_points"] = 1
        
        elif task_type == "subtask" and "subtasks" in tasks_data:
            for i, subtask in enumerate(tasks_data["subtasks"]):
                # Validate required subtask fields
                if "summary" not in subtask or not subtask["summary"]:
                    tasks_data["subtasks"][i]["summary"] = "Untitled Subtask"
                    LOGGER.warning("Missing subtask summary, using default")
                    
                if "description" not in subtask:
                    tasks_data["subtasks"][i]["description"] = "No description provided"
                    
                if "story_points" not in subtask:
                    tasks_data["subtasks"][i]["story_points"] = 1
                    
                # Validate component is a valid department
                if "component" not in subtask or subtask["component"] not in departments:
                    tasks_data["subtasks"][i]["component"] = departments[0] if departments else "Default"
                    LOGGER.warning(f"Invalid component in subtask, replaced with {departments[0]}")
        
        LOGGER.info(f"Task data validation complete for {task_type}")
