from __future__ import annotations

import json
from typing import Dict
from typing import List
from typing import Optional

from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END
from langgraph.graph import StateGraph
from pydantic import BaseModel
from pydantic import Field

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import GEMINI_SETTINGS as gemini_connection_settings
from jira_telegram_bot.use_cases.interface.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interface.user_config_interface import (
    UserConfigInterface,
)


class SubTask(BaseModel):
    summary: str = Field(
        description="A clear, concise summary of what needs to be done",
    )
    description: str = Field(
        description="Detailed description with acceptance criteria",
    )
    story_points: float = Field(description="Estimated story points (0.5-8)")
    assignee: Optional[str] = Field(description="Username of assignee", default=None)


class ComponentTasks(BaseModel):
    component: str = Field(description="The department/component responsible")
    subtasks: List[SubTask] = Field(description="List of subtasks for this component")


class Story(BaseModel):
    summary: str = Field(description="A clear, concise story summary")
    description: str = Field(
        description="Detailed user story description with acceptance criteria",
    )
    story_points: float = Field(description="Story points (1-13)")
    priority: str = Field(description="Priority level (High, Medium, Low)")
    component_tasks: List[ComponentTasks] = Field(
        description="Tasks broken down by component",
    )


class ProjectDecomposition(BaseModel):
    stories: List[Story] = Field(description="List of user stories")


class AdvancedTaskCreation:
    def __init__(
        self,
        jira_repo: TaskManagerRepositoryInterface,
        user_config: UserConfigInterface,
    ):
        self.jira_repo = jira_repo
        self.user_config = user_config
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-preview-04-17",
            temperature=0.3,
            convert_system_message_to_human=True,
            google_api_key=gemini_connection_settings.token,
        )

    def create_task_decomposition_chain(self, project_info: Dict):
        parser = PydanticOutputParser(pydantic_object=ProjectDecomposition)

        prompt = PromptTemplate(
            template="""You are an expert technical project manager with deep experience in breaking down complex projects into actionable tasks. Your expertise lies in creating well-structured user stories and tasks that align with team capabilities and project goals.

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

{format_instructions}

Process the request by:
1. Understanding the overall goal
2. Breaking it into user stories
3. For each story:
   - Determine required components
   - Break down into specific tasks per component
   - Consider skill requirements and dependencies
4. Structure the output as specified

Remember:
- Tasks should be concrete and actionable
- Include clear acceptance criteria
- Consider team skills and capacity
- Factor in technical dependencies
- Make assignments based on experience level""",
            input_variables=[
                "project_context",
                "description",
                "departments",
                "department_details",
                "assignee_details",
            ],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        def process_task(state):
            project_info = state["project_info"]

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

            result = self.llm.invoke(
                prompt.format(
                    project_context=project_info["project_info"]["description"],
                    description=state["description"],
                    departments=", ".join(project_info["departments"].keys()),
                    department_details="\n\n".join(dept_details),
                    assignee_details="\n".join(assignee_details),
                ),
            )

            parsed = parser.parse(result)
            state["decomposition"] = parsed
            return state

        def assign_tasks(state):
            project_info = state["project_info"]
            decomp = state["decomposition"]

            # Get department leads and members
            dept_leads = {
                comp["name"]: comp["lead"] for comp in project_info["components"]
            }
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
            for story in decomp.stories:
                for comp_tasks in story.component_tasks:
                    dept = comp_tasks.component
                    if dept not in dept_members:
                        continue

                    members = dept_members[dept]
                    leader = dept_leads.get(dept)

                    # Sort members by seniority for task allocation
                    seniors = [m for m in members if m["role"] == "Senior Developer"]
                    mids = [m for m in members if m["role"] == "Mid-level Developer"]
                    juniors = [m for m in members if m["role"] == "Junior Developer"]

                    # Distribute tasks based on complexity (story points)
                    for task in comp_tasks.subtasks:
                        if not task.assignee:  # Only assign if not already assigned
                            if task.story_points >= 5:  # Complex tasks
                                if seniors:
                                    task.assignee = seniors[0]["username"]
                            elif task.story_points >= 2:  # Medium tasks
                                if mids:
                                    task.assignee = mids[0]["username"]
                                elif seniors:
                                    task.assignee = seniors[0]["username"]
                            else:  # Simple tasks
                                if juniors:
                                    task.assignee = juniors[0]["username"]
                                elif mids:
                                    task.assignee = mids[0]["username"]
                                elif seniors:
                                    task.assignee = seniors[0]["username"]

                            # If still no assignee, assign to department lead
                            if not task.assignee and leader:
                                task.assignee = leader

            state["decomposition"] = decomp
            return state

        # Create the graph
        workflow = StateGraph(name="task-decomposition")

        # Add nodes
        workflow.add_node("process", process_task)
        workflow.add_node("assign", assign_tasks)

        # Add edges
        workflow.add_edge("process", "assign")
        workflow.add_edge("assign", END)

        # Set entry point
        workflow.set_entry_point("process")

        return workflow.compile()

    async def create_tasks(self, description: str, project_key: str) -> List[TaskData]:
        """Create multiple stories with their component-specific subtasks."""
        # Load project info from projects_info.json
        with open(
            f"{DEFAULT_PATH}/jira_telegram_bot/settings/projects_info.json",
            "r",
        ) as f:
            projects_info = json.load(f)
            project_info = projects_info.get(project_key)

        if not project_info:
            raise ValueError(f"No project info found for {project_key}")

        # Initialize the graph state
        state = {
            "description": description,
            "project_info": project_info,
        }

        # Run the task decomposition workflow
        chain = self.create_task_decomposition_chain(project_info)
        final_state = chain.invoke(state)
        decomposition = final_state["decomposition"]

        # Create all tasks in Jira
        created_tasks = []

        for story in decomposition.stories:
            # 1. Create the main story
            story_data = TaskData(
                project_key=project_key,
                summary=story.summary,
                description=story.description,
                components=[ct.component for ct in story.component_tasks],
                story_points=story.story_points,
                task_type="Story",
                priority=story.priority,
            )
            story_issue = await self.jira_repo.create_task(story_data)
            created_tasks.append(story_issue)

            # 2. Create subtasks for each component
            for comp_tasks in story.component_tasks:
                for subtask in comp_tasks.subtasks:
                    subtask_data = TaskData(
                        project_key=project_key,
                        summary=subtask.summary,
                        description=subtask.description,
                        components=[comp_tasks.component],
                        story_points=subtask.story_points,
                        assignee=subtask.assignee,
                        task_type="Sub-task",
                        parent_issue_key=story_issue.key,
                    )
                    subtask_issue = await self.jira_repo.create_task(subtask_data)
                    created_tasks.append(subtask_issue)

        return created_tasks
