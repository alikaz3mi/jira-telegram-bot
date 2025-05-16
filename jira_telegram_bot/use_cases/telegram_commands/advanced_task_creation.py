from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from jira import Issue

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.entities.task import UserStory
from jira_telegram_bot.use_cases.interfaces.interfaces import StoryGenerator
from jira_telegram_bot.use_cases.interfaces.story_decomposition_interface import (
    StoryDecompositionInterface,
)
from jira_telegram_bot.use_cases.interfaces.subtask_creation_interface import (
    SubtaskCreationInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)
from jira_telegram_bot.use_cases.interfaces.project_info_repository_interface import (
    ProjectInfoRepositoryInterface,
)


class AdvancedTaskCreation:
    """Handles creation of multiple related tasks with subtasks through AI analysis."""

    def __init__(
        self,
        task_manager_repository: TaskManagerRepositoryInterface,
        user_config: UserConfigInterface,
        project_info_repository: ProjectInfoRepositoryInterface,
        story_generator: StoryGenerator,
        story_decomposition_service: StoryDecompositionInterface,
        subtask_creation_service: SubtaskCreationInterface,
    ):
        """Initialize advanced task creation service.

        Args:
            task_manager_repository: Repository for task management operations
            user_config: Service for user configuration
            project_info_repository: Repository for project information
            story_generator: Service for generating user stories
            story_decomposition_service: Service for decomposing stories into tasks
            subtask_creation_service: Service for creating subtasks
        """
        self.task_manager_repository = task_manager_repository
        self.user_config = user_config
        self.project_info_repository = project_info_repository
        self.story_generator = story_generator
        self.story_decomposition_service = story_decomposition_service
        self.subtask_creation_service = subtask_creation_service

    async def create_tasks(
        self,
        description: str,
        project_key: str,
        epic_key: Optional[str] = None,
        parent_story_key: Optional[str] = None,
        task_type: str = "story",  # "story" or "subtask"
    ) -> List[Issue]:
        """Create multiple stories with their component-specific subtasks.

        Args:
            description: Detailed description of the work needed
            project_key: Jira project key
            epic_key: Optional epic to link stories to
            parent_story_key: Optional parent story for subtasks
            task_type: Either "story" (with subtasks) or "subtask" (add to existing story)

        Returns:
            List of created Issue objects
        """
        # Load project info from repository
        project_info = await self.project_info_repository.get_project_info(project_key)

        # Parse the tasks
        if task_type == "story":
            tasks_data = await self.story_decomposition_service.decompose_story(
                project_context=project_info["project_info"]["description"],
                description=description,
                departments=", ".join(project_info["departments"].keys()),
                department_details=self._format_department_details(project_info),
                assignee_details=self._format_assignee_details(project_info),
            )
        else:  # task_type == "subtask"
            tasks_data = await self.subtask_creation_service.create_subtasks(
                project_context=project_info["project_info"]["description"],
                description=description,
                departments=", ".join(project_info["departments"].keys()),
                department_details=self._format_department_details(project_info),
                assignee_details=self._format_assignee_details(project_info),
            )

        # Assign tasks based on skills
        if task_type == "story" and "stories" in tasks_data:
            tasks_data = self._assign_tasks(tasks_data, project_info)

        created_tasks = []

        if task_type == "story":
            created_tasks = await self._create_stories(created_tasks, epic_key, project_key, tasks_data)
        else:  # task_type == "subtask"
            created_tasks = await self._create_subtasks_for_story(
                created_tasks,
                parent_story_key,
                project_key,
                tasks_data,
            )

        return created_tasks

    def _format_department_details(self, project_info: Dict[str, Any]) -> str:
        """Format department details for AI prompts.

        Args:
            project_info: Project configuration information

        Returns:
            String with formatted department details
        """
        dept_details = []
        for dept, info in project_info["departments"].items():
            dept_details.append(
                f"{dept}:\n- {info['description']}\n- Tools: {', '.join(info['tools'])}\n- Weekly Hours: {info['time_allocation_weekly_hours']}",
            )
        return "\n\n".join(dept_details)

    def _format_assignee_details(self, project_info: Dict[str, Any]) -> str:
        """Format assignee details for AI prompts.

        Args:
            project_info: Project configuration information

        Returns:
            String with formatted assignee details
        """
        assignee_details = []
        for assignee in project_info["assignees"]:
            assignee_details.append(
                f"{assignee['username']} ({assignee['role']}) - {assignee['department']}",
            )
        return "\n".join(assignee_details)

    async def _create_subtasks_for_story(
        self,
        created_tasks: List[Issue],
        parent_story_key: str,
        project_key: str,
        tasks_data: Dict[str, Any],
    ) -> List[Issue]:
        """Create subtasks for an existing parent story.

        Args:
            created_tasks: List to append created tasks to
            parent_story_key: Key of the parent story
            project_key: Project key
            tasks_data: Task data structure from AI
        """
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
        
        return created_tasks

    async def _create_stories(
        self,
        created_tasks: List[Issue],
        epic_key: Optional[str],
        project_key: str,
        tasks_data: Dict[str, Any],
    ) -> List[Issue]:
        """Create stories with subtasks.

        Args:
            created_tasks: List to append created tasks to
            epic_key: Optional epic key to link stories to
            project_key: Project key
            tasks_data: Task data structure from AI
        """
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
        # Load project info from repository
        project_info = await self.project_info_repository.get_project_info(project_key)

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

        # Generate user story using story generator
        try:
            # Extract business goals and product area
            business_goal = project_info.get("project_info", {}).get(
                "objective", "Improve user experience"
            )
            product_area = project_info.get("project_info", {}).get(
                "description", "Software Product"
            )

            # Main personas from project info
            primary_persona = "User"
            if "personas" in project_info:
                primary_persona = next(iter(project_info["personas"]), "User")

            # Format epic and parent context
            epic_context_str = ""
            if epic_context:
                epic_context_str = f"""Epic Information:
                                    Epic Key: {epic_context.get("key", "")}
                                    Epic Summary: {epic_context.get("summary", "")}
                                    Epic Description: {epic_context.get("description", "")}
                                    """

            parent_context_str = ""
            if parent_story_context:
                parent_context_str = f"""Parent Story Information:
                                        Story Key: {parent_story_context.get("key", "")}
                                        Story Summary: {parent_story_context.get("summary", "")}
                                        Story Description: {parent_story_context.get("description", "")}"""

            project_key_for_story = project_key
            if "departments" in project_info:
                project_key_for_story = list(project_info["departments"].keys())[0]

            user_story = await self.story_generator.generate(
                raw_text=description,
                project=project_key_for_story,
                product_area=product_area,
                business_goal=business_goal,
                primary_persona=primary_persona,
                dependencies="Integration with existing systems required",
                epic_context=epic_context_str,
                parent_story_context=parent_context_str,
            )

            # Convert to dictionary
            user_story_content = {
                "summary": user_story.summary,
                "description": user_story.description,
                "component": user_story.components[0] if user_story.components else "",
                "story_points": user_story.story_points,
                "priority": user_story.priority,
            }
        except Exception as e:
            LOGGER.error(f"Error generating user story: {str(e)}")
            # Fallback story
            user_story_content = {
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

    def _merge_descriptions(self, original: str, new_content: str) -> str:
        """Merge original description with new user story content.

        Args:
            original: Original description text
            new_content: New user story content to add

        Returns:
            Combined description preserving both contents
        """
        if not original or original.strip() == "":
            return new_content

        if "As a " in original and "I want " in original and "so that " in original:
            # It already has a user story format, try to enhance it
            return self._update_existing_user_story_content(original, new_content)
        else:
            # Doesn't have user story format, preserve original as context
            return f"""**Original Description:**
{original}

**Enhanced User Story:**
{new_content}"""

    def _update_existing_user_story_content(
        self, original: str, new_content: str
    ) -> str:
        """Update an existing user story with new content, preserving structure.

        Args:
            original: Original user story text
            new_content: New user story content to integrate

        Returns:
            Enhanced user story with merged sections
        """
        # Extract sections from the new content
        new_sections = self._extract_sections(new_content)

        # Update or append sections to original content
        result = original
        for section_name, section_content in new_sections.items():
            if section_name in result:
                # Update existing section
                start_idx = result.find(section_name)
                next_section_idx = self._find_next_section(
                    result, section_name, start_idx
                )

                if next_section_idx < float("inf"):
                    result = (
                        result[:start_idx] + section_content + result[next_section_idx:]
                    )
                else:
                    result = result[:start_idx] + section_content
            else:
                # Append new section
                result += f"\n\n{section_content}"

        return result

    def _extract_sections(self, content: str) -> Dict[str, str]:
        """Extract sections from user story content.

        Args:
            content: The user story content

        Returns:
            Dictionary of section name to section content
        """
        sections = {}
        possible_sections = [
            "Acceptance Criteria",
            "Non-functional Requirements",
            "Sizing",
            "Risks & Open Questions",
            "Definition of Done",
        ]

        for section in possible_sections:
            if section in content:
                start_idx = content.find(section)
                next_section_idx = self._find_next_section(content, section, start_idx)

                if next_section_idx < float("inf"):
                    sections[section] = content[start_idx:next_section_idx].strip()
                else:
                    sections[section] = content[start_idx:].strip()

        return sections

    def _find_next_section(
        self, content: str, current_section: str, start_idx: int
    ) -> float:
        """Find the index of the next section in the content.

        Args:
            content: The content to search
            current_section: Current section name
            start_idx: Starting index for search

        Returns:
            Index of the next section or infinity if none found
        """
        possible_sections = [
            "Acceptance Criteria",
            "Non-functional Requirements",
            "Sizing",
            "Risks & Open Questions",
            "Definition of Done",
        ]

        next_section_idx = float("inf")
        for section in possible_sections:
            if (
                section != current_section
                and section in content[start_idx + len(current_section) :]
            ):
                section_idx = (
                    content[start_idx + len(current_section) :].find(section)
                    + start_idx
                    + len(current_section)
                )
                next_section_idx = min(next_section_idx, section_idx)

        return next_section_idx

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
        # Build team structure
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

                # Group members by seniority
                seniors = [m for m in members if m["role"] == "Senior Developer"]
                mid_levels = [m for m in members if m["role"] == "Mid-level Developer"]
                juniors = [m for m in members if m["role"] == "Junior Developer"]

                # Distribute tasks based on complexity (story points)
                for task in comp_tasks["subtasks"]:
                    if (
                        task.get("assignee") is None
                    ):  # Only assign if not already assigned
                        story_points = task["story_points"]

                        if story_points >= 5:  # Complex tasks
                            if seniors:
                                task["assignee"] = seniors[0]["username"]
                        elif story_points >= 2:  # Medium tasks
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

        return parsed_data
