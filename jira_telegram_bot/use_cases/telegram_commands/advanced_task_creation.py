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
from jira_telegram_bot.entities.task import UserStory
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import AiServiceProtocol
from jira_telegram_bot.use_cases.interfaces.ai_service_interface import PromptCatalogProtocol
from jira_telegram_bot.use_cases.interfaces.interfaces import StoryGenerator
from jira_telegram_bot.use_cases.interfaces.story_decomposition_interface import StoryDecompositionInterface
from jira_telegram_bot.use_cases.interfaces.subtask_creation_interface import SubtaskCreationInterface
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
        ai_service: AiServiceProtocol,
        prompt_catalog: PromptCatalogProtocol,
        story_generator: StoryGenerator,
        story_decomposition_service: StoryDecompositionInterface = None,
        subtask_creation_service: SubtaskCreationInterface = None,
    ):
        self.task_manager_repository = task_manager_repository
        self.user_config = user_config
        self.ai_service = ai_service
        self.prompt_catalog = prompt_catalog
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
        
        story_inputs = self._prepare_story_inputs(
            description, project_info, epic_context, parent_story_context
        )
        
        try:
            user_story = await self._generate_user_story_with_service(
                description, project_info, story_inputs
            )
            return self._convert_user_story_to_dict(user_story)
        except Exception as e:
            LOGGER.error(f"Error generating user story: {str(e)}")
            return self._create_fallback_user_story(description, project_info)
            
    def _prepare_story_inputs(
        self,
        description: str,
        project_info: Dict[str, Any],
        epic_context: Dict[str, Any],
        parent_story_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prepare inputs for story generation.
        
        Args:
            description: The detailed task description
            project_info: Project configuration information
            epic_context: Optional context from linked epic
            parent_story_context: Optional context from parent story
            
        Returns:
            Dictionary of prepared inputs
        """
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
            
        return {
            "product_area": product_area,
            "business_goal": business_goal,
            "primary_persona": primary_persona,
            "dependencies": "Integration with existing systems required",
            "epic_context": self._format_epic_context(epic_context),
            "parent_story_context": self._format_parent_context(parent_story_context),
        }
        
    def _format_epic_context(self, epic_context: Dict[str, Any]) -> str:
        """Format epic context for story generation.
        
        Args:
            epic_context: Epic context information
            
        Returns:
            Formatted epic context text
        """
        if not epic_context:
            return ""
            
        return f"""Epic Information:
Epic Key: {epic_context.get('key', '')}
Epic Summary: {epic_context.get('summary', '')}
Epic Description: {epic_context.get('description', '')}"""
        
    def _format_parent_context(self, parent_story_context: Dict[str, Any]) -> str:
        """Format parent story context for story generation.
        
        Args:
            parent_story_context: Parent story context information
            
        Returns:
            Formatted parent context text
        """
        if not parent_story_context:
            return ""
            
        return f"""Parent Story Information:
Story Key: {parent_story_context.get('key', '')}
Story Summary: {parent_story_context.get('summary', '')}
Story Description: {parent_story_context.get('description', '')}"""
        
    async def _generate_user_story_with_service(
        self,
        description: str,
        project_info: Dict[str, Any],
        story_inputs: Dict[str, Any],
    ) -> UserStory:
        """Generate user story using the story generator service.
        
        Args:
            description: The detailed task description
            project_info: Project configuration information
            story_inputs: Prepared inputs for story generation
            
        Returns:
            Generated UserStory object
        """
        project_key = list(project_info.get("departments", {}).keys())[0] if project_info.get("departments") else ""
        return await self.story_generator.generate(
            raw_text=description,
            project=project_key,
            **story_inputs
        )
        
    def _convert_user_story_to_dict(self, user_story: UserStory) -> Dict[str, Any]:
        """Convert UserStory object to dictionary format.
        
        Args:
            user_story: UserStory object
            
        Returns:
            Dictionary representation of user story
        """
        return {
            "summary": user_story.summary,
            "description": user_story.description,
            "component": user_story.components[0] if user_story.components else "",
            "story_points": user_story.story_points,
            "priority": user_story.priority,
        }
        
    def _create_fallback_user_story(
        self,
        description: str,
        project_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a fallback user story when generation fails.
        
        Args:
            description: The detailed task description
            project_info: Project configuration information
            
        Returns:
            Dictionary containing basic user story
        """
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
        if not original or original.strip() == "":
            return new_content

        if "As a " in original and "I want " in original and "so that " in original:
            new_sections = self._extract_content_sections(new_content)
            return self._update_existing_user_story(original, new_sections)
        else:
            return self._format_as_enhanced_story(original, new_content)
            
    def _extract_content_sections(self, content: str) -> Dict[str, str]:
        """Extract sections from user story content.
        
        Args:
            content: User story content with sections
            
        Returns:
            Dictionary of section name to section content
        """
        new_sections = {}
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
                next_section_idx = self._find_next_section_index(
                    content, section, start_idx, possible_sections
                )

                if next_section_idx < float("inf"):
                    new_sections[section] = content[start_idx:next_section_idx].strip()
                else:
                    new_sections[section] = content[start_idx:].strip()
                    
        return new_sections
    
    def _find_next_section_index(
        self, content: str, current_section: str, start_idx: int, possible_sections: List[str]
    ) -> float:
        """Find the index of the next section in content.
        
        Args:
            content: The content to search in
            current_section: The current section name
            start_idx: Starting index for the search
            possible_sections: List of possible section names
            
        Returns:
            Index of the next section or infinity if none found
        """
        next_section_idx = float("inf")
        for next_section in possible_sections:
            if (
                next_section != current_section
                and next_section in content[start_idx + len(current_section):]
            ):
                section_idx = (
                    content[start_idx + len(current_section):].find(next_section)
                    + start_idx
                    + len(current_section)
                )
                next_section_idx = min(next_section_idx, section_idx)
                
        return next_section_idx
        
    def _update_existing_user_story(self, original: str, new_sections: Dict[str, str]) -> str:
        """Update existing user story with new sections.
        
        Args:
            original: Original user story text
            new_sections: New sections to update or append
            
        Returns:
            Updated user story text
        """
        result = original
        possible_sections = [
            "Acceptance Criteria",
            "Non-functional Requirements",
            "Sizing",
            "Risks & Open Questions",
            "Definition of Done",
        ]
        
        for section, content in new_sections.items():
            if section in result:
                start_idx = result.find(section)
                next_section_idx = self._find_next_section_index(
                    result, section, start_idx, possible_sections
                )

                if next_section_idx < float("inf"):
                    result = result[:start_idx] + content + result[next_section_idx:]
                else:
                    result = result[:start_idx] + content
            else:
                result += f"\n\n{content}"
                
        return result
    
    def _format_as_enhanced_story(self, original: str, new_content: str) -> str:
        """Format original content and new user story.
        
        Args:
            original: Original description text
            new_content: New user story content
            
        Returns:
            Combined description with clear separation
        """
        return f"""**Original Description:**
{original}

**Enhanced User Story:**
{new_content}"""

    async def _parse_task_description(
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
        try:
            formatted_details = self._format_project_details(project_info)
            result = await self._generate_task_structure(
                description, 
                project_info, 
                task_type, 
                formatted_details
            )
            
            # Assign tasks based on skill levels for stories
            if task_type == "story" and "stories" in result:
                result = self._assign_tasks(result, project_info)
                
            return result
        except Exception as e:
            LOGGER.error(f"Error parsing task description: {str(e)}")
            return self._generate_fallback_result(task_type, description, project_info)
    
    def _format_project_details(self, project_info: Dict[str, Any]) -> Dict[str, str]:
        """Format project details for AI prompt.
        
        Args:
            project_info: Project configuration information
            
        Returns:
            Dictionary of formatted project details
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
            
        return {
            "project_context": project_info["project_info"]["description"],
            "departments": ", ".join(project_info["departments"].keys()),
            "department_details": "\n\n".join(dept_details),
            "assignee_details": "\n".join(assignee_details),
        }
        
    async def _generate_task_structure(
        self, 
        description: str,
        project_info: Dict[str, Any],
        task_type: str,
        formatted_details: Dict[str, str],
    ) -> Dict[str, Any]:
        """Generate the task structure using appropriate service.
        
        Args:
            description: The detailed task description
            project_info: Project configuration information
            task_type: Either "story" or "subtask"
            formatted_details: Dictionary containing formatted project details
            
        Returns:
            Dictionary containing structured tasks
        """
        if task_type == "story":
            return await self._generate_story_structure(description, formatted_details)
        else:
            return await self._generate_subtask_structure(description, formatted_details)
            
    async def _generate_story_structure(
        self, 
        description: str, 
        formatted_details: Dict[str, str]
    ) -> Dict[str, Any]:
        """Generate story structure using decomposition service.
        
        Args:
            description: The detailed task description
            formatted_details: Dictionary containing formatted project details
            
        Returns:
            Dictionary containing structured story data
        """
        if self.story_decomposition_service:
            return await self.story_decomposition_service.decompose_story(
                project_context=formatted_details["project_context"],
                description=description,
                departments=formatted_details["departments"],
                department_details=formatted_details["department_details"],
                assignee_details=formatted_details["assignee_details"],
            )
        else:
            prompt_spec = await self.prompt_catalog.get_prompt("decompose_user_story")
            return await self.ai_service.run(
                prompt=prompt_spec,
                inputs={
                    "project_context": formatted_details["project_context"],
                    "description": description,
                    "departments": formatted_details["departments"],
                    "department_details": formatted_details["department_details"],
                    "assignee_details": formatted_details["assignee_details"],
                },
                cleanse_llm_text=True,
            )
            
    async def _generate_subtask_structure(
        self, 
        description: str, 
        formatted_details: Dict[str, str]
    ) -> Dict[str, Any]:
        """Generate subtask structure using subtask creation service.
        
        Args:
            description: The detailed task description
            formatted_details: Dictionary containing formatted project details
            
        Returns:
            Dictionary containing structured subtask data
        """
        if self.subtask_creation_service:
            return await self.subtask_creation_service.create_subtasks(
                project_context=formatted_details["project_context"],
                description=description,
                departments=formatted_details["departments"],
                department_details=formatted_details["department_details"],
                assignee_details=formatted_details["assignee_details"],
            )
        else:
            prompt_spec = await self.prompt_catalog.get_prompt("create_subtasks")
            return await self.ai_service.run(
                prompt=prompt_spec,
                inputs={
                    "project_context": formatted_details["project_context"],
                    "description": description,
                    "departments": formatted_details["departments"],
                    "department_details": formatted_details["department_details"],
                    "assignee_details": formatted_details["assignee_details"],
                },
                cleanse_llm_text=True,
            )
            
    def _generate_fallback_result(
        self,
        task_type: str,
        description: str,
        project_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a fallback result when task parsing fails.
        
        Args:
            task_type: Either "story" or "subtask"
            description: The detailed task description
            project_info: Project configuration information
            
        Returns:
            Dictionary containing basic task data structure
        """
        default_component = list(project_info["departments"].keys())[0]
        
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
                                "component": default_component,
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
        else:  # task_type == "subtask"
            return {
                "subtasks": [
                    {
                        "summary": "Investigate requirements",
                        "description": description,
                        "story_points": 3,
                        "component": default_component,
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
        team_structure = self._build_team_structure(project_info)
        
        # Assign tasks based on skill levels
        for story in parsed_data["stories"]:
            for comp_tasks in story["component_tasks"]:
                dept = comp_tasks["component"]
                if dept not in team_structure["dept_members"]:
                    continue

                self._assign_department_tasks(
                    comp_tasks, 
                    dept, 
                    team_structure["dept_members"], 
                    team_structure["dept_leads"]
                )

        return parsed_data
        
    def _build_team_structure(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """Build team structure from project info.
        
        Args:
            project_info: Project configuration information
            
        Returns:
            Dictionary containing team structure
        """
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
            
        return {
            "dept_leads": dept_leads,
            "dept_members": dept_members,
        }
        
    def _assign_department_tasks(
        self, 
        comp_tasks: Dict[str, Any], 
        dept: str, 
        dept_members: Dict[str, List[Dict[str, str]]],
        dept_leads: Dict[str, str],
    ) -> None:
        """Assign tasks for a department based on skill levels.
        
        Args:
            comp_tasks: Component tasks to assign
            dept: Department name
            dept_members: Dictionary of department members
            dept_leads: Dictionary of department leads
        """
        members = dept_members[dept]
        leader = dept_leads.get(dept)

        # Group members by seniority
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

    def _distribute_tasks_based_on_complexity(
        self,
        comp_tasks: Dict[str, Any],
        juniors: List[Dict[str, str]],
        leader: str,
        mid_levels: List[Dict[str, str]],
        seniors: List[Dict[str, str]],
    ) -> None:
        """Distribute tasks based on their complexity and available team members.
        
        Args:
            comp_tasks: Component tasks to distribute
            juniors: List of junior developers
            leader: Department lead username
            mid_levels: List of mid-level developers
            seniors: List of senior developers
        """
        for task in comp_tasks["subtasks"]:
            if task.get("assignee") is None:  # Only assign if not already assigned
                self._assign_task_based_on_complexity(
                    task, seniors, mid_levels, juniors, leader
                )
                
    def _assign_task_based_on_complexity(
        self,
        task: Dict[str, Any],
        seniors: List[Dict[str, str]],
        mid_levels: List[Dict[str, str]],
        juniors: List[Dict[str, str]],
        leader: str,
    ) -> None:
        """Assign a specific task based on its complexity.
        
        Args:
            task: Task to assign
            seniors: List of senior developers
            mid_levels: List of mid-level developers
            juniors: List of junior developers
            leader: Department lead username
        """
        story_points = task["story_points"]
        
        if story_points >= 5:  # Complex tasks
            self._assign_to_available_developer(task, seniors)
        elif story_points >= 2:  # Medium tasks
            if not self._assign_to_available_developer(task, mid_levels):
                self._assign_to_available_developer(task, seniors)
        else:  # Simple tasks
            if not self._assign_to_available_developer(task, juniors):
                if not self._assign_to_available_developer(task, mid_levels):
                    self._assign_to_available_developer(task, seniors)
                    
        # If still no assignee, assign to department lead
        if not task.get("assignee") and leader:
            task["assignee"] = leader
            
    def _assign_to_available_developer(
        self,
        task: Dict[str, Any],
        developers: List[Dict[str, str]],
    ) -> bool:
        """Assign task to first available developer in the list.
        
        Args:
            task: Task to assign
            developers: List of available developers
            
        Returns:
            True if assignment was successful, False otherwise
        """
        if developers:
            task["assignee"] = developers[0]["username"]
            return True
        return False


# Testing functionality should be moved to proper test files in the tests directory
