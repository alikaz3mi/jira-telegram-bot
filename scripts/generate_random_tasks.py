#!/usr/bin/env python3
"""Script to generate 100 random tasks, stories, epics with components and labels using the task repository interface."""

import random
import sys
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional


from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings
from jira_telegram_bot import LOGGER


class RandomTaskConstants:
    """Constants for random task generation following the project's coding guidelines."""
    
    PROJECT_KEYS = ["C3S", "ENT", "MTP", "RADTHARN", "SILMARIN"]
    
    TASK_TYPES = ["Story", "Task", "Epic", "Bug", "Sub-task"]
    
    PRIORITIES = ["Highest", "High", "Medium", "Low", "Lowest"]
    
    COMPONENTS = [
        "Backend", "Frontend", "DevOps", "UI/UX", "Database", 
        "API", "Authentication", "Notifications", "Analytics", 
        "Testing", "Documentation", "Infrastructure"
    ]
    
    LABELS = [
        "Must-have", "Should-Have", "Could-Have", "Won't-Have",
        "Backend", "Frontend", "Critical", "Enhancement", 
        "Performance", "Security", "Refactoring", "Documentation",
        "Bug-fix", "Feature", "Integration", "Testing"
    ]
    
    STORY_SUMMARIES = [
        "Implement user authentication system",
        "Create responsive dashboard interface", 
        "Optimize database query performance",
        "Add real-time notification system",
        "Develop API endpoint for data export",
        "Implement search functionality",
        "Create user profile management",
        "Add data validation layer",
        "Implement caching mechanism",
        "Create automated testing suite",
        "Add logging and monitoring",
        "Implement error handling",
        "Create documentation system",
        "Add mobile responsive design",
        "Implement security audit",
        "Create backup and recovery system",
        "Add integration with external services",
        "Implement data analytics dashboard",
        "Create user feedback system",
        "Add multi-language support"
    ]
    
    EPIC_SUMMARIES = [
        "User Management System",
        "Authentication & Authorization",
        "Data Analytics Platform", 
        "Mobile Application",
        "API Gateway Implementation",
        "Performance Optimization",
        "Security Enhancement",
        "DevOps Infrastructure",
        "Testing Automation",
        "Documentation Portal"
    ]
    
    STORY_DESCRIPTIONS = [
        "As a user, I want to be able to securely log into the system so that I can access my personal dashboard.",
        "As an admin, I need to manage user permissions so that I can control access to different features.",
        "As a developer, I want to optimize the database queries so that the application performs better.",
        "As a user, I want to receive notifications about important updates so that I stay informed.",
        "As a data analyst, I need to export data in various formats so that I can perform external analysis.",
        "As a user, I want to search through content quickly so that I can find relevant information.",
        "As a user, I want to update my profile information so that my account details are current.",
        "As a system, I need to validate all input data so that data integrity is maintained.",
        "As the application, I want to cache frequently accessed data so that response times are improved.",
        "As a developer, I need automated tests so that I can ensure code quality and prevent regressions."
    ]
    
    ASSIGNEES = [
        "alikaz3mi", "admin"
    ]


class RandomTaskGenerator:
    """Generates random tasks using the task repository interface."""

    def __init__(self, task_repository: TaskManagerRepositoryInterface):
        """Initialize the random task generator.
        
        Args:
            task_repository: The task manager repository interface.
        """
        self.task_repository = task_repository
        self.created_epics = []
        self.created_stories = []

    def _generate_random_date(self, days_ahead: int = 30) -> str:
        """Generate a random date within the next specified days.
        
        Args:
            days_ahead: Number of days in the future to generate date.
            
        Returns:
            Date string in YYYY-MM-DD format.
        """
        future_date = datetime.now() + timedelta(days=random.randint(1, days_ahead))
        return future_date.strftime('%Y-%m-%d')

    def _get_random_components(self, project_key: str) -> List[str]:
        """Get random components for a project.
        
        Args:
            project_key: The project key.
            
        Returns:
            List of random component names.
        """
        # Simplified version - use predefined components for now
        num_components = random.randint(1, 3)
        return random.sample(RandomTaskConstants.COMPONENTS, num_components)

    def _get_random_labels(self, project_key: str) -> List[str]:
        """Get random labels for a project.
        
        Args:
            project_key: The project key.
            
        Returns:
            List of random label names.
        """
        # Simplified version - use predefined labels for now
        num_labels = random.randint(1, 4)
        return random.sample(RandomTaskConstants.LABELS, num_labels)

    def _get_random_sprint(self, project_key: str) -> Optional[dict]:
        """Get a random sprint for a project.
        
        Args:
            project_key: The project key.
            
        Returns:
            Random sprint info or None.
        """
        # Simplified version - return None for now to avoid API complexity
        return None

    def generate_epic(self, project_key: str) -> TaskData:
        """Generate a random epic.
        
        Args:
            project_key: The project key.
            
        Returns:
            TaskData for an epic.
        """
        return TaskData(
            project_key=project_key,
            summary=random.choice(RandomTaskConstants.EPIC_SUMMARIES),
            description=f"Epic for {random.choice(RandomTaskConstants.EPIC_SUMMARIES).lower()} implementation",
            task_type="Epic"
        )

    def generate_story(self, project_key: str, epic_key: Optional[str] = None) -> TaskData:
        """Generate a random story.
        
        Args:
            project_key: The project key.
            epic_key: Optional epic to link to.
            
        Returns:
            TaskData for a story.
        """
        # Only link to epic if it's in the same project
        epic_link = epic_key if epic_key and epic_key.startswith(project_key) else None
        
        return TaskData(
            project_key=project_key,
            summary=random.choice(RandomTaskConstants.STORY_SUMMARIES),
            description=random.choice(RandomTaskConstants.STORY_DESCRIPTIONS),
            task_type="Story",
            epic_link=epic_link
        )

    def generate_task(self, project_key: str, parent_key: Optional[str] = None) -> TaskData:
        """Generate a random task.
        
        Args:
            project_key: The project key.
            parent_key: Optional parent story key.
            
        Returns:
            TaskData for a task.
        """
        # Only create sub-tasks if parent is in the same project and for SILMARIN project only
        # Other projects seem to have issues with Sub-task type
        is_subtask = (parent_key and 
                     parent_key.startswith(project_key) and 
                     project_key == "SILMARIN")
        
        task_type = "Sub-task" if is_subtask else "Task"
        parent_issue_key = parent_key if is_subtask else None
        
        return TaskData(
            project_key=project_key,
            summary=f"Implement {random.choice(['component', 'feature', 'module', 'functionality'])} for {random.choice(['user interface', 'backend service', 'database layer', 'API endpoint'])}",
            description=f"Technical implementation task for {random.choice(['improving', 'adding', 'optimizing', 'refactoring'])} system functionality",
            task_type=task_type,
            parent_issue_key=parent_issue_key
        )

    async def generate_random_tasks(self, total_count: int = 100) -> None:
        """Generate random tasks, stories, and epics.
        
        Args:
            total_count: Total number of tasks to create.
        """
        LOGGER.info(f"Starting generation of {total_count} random tasks")
        
        # Distribution: 10% epics, 40% stories, 50% tasks/sub-tasks
        epic_count = max(1, total_count // 10)
        story_count = max(1, total_count * 40 // 100)
        task_count = total_count - epic_count - story_count
        
        created_count = 0
        
        try:
            # Generate epics first
            LOGGER.info(f"Creating {epic_count} epics...")
            for i in range(epic_count):
                project_key = random.choice(RandomTaskConstants.PROJECT_KEYS)
                epic_data = self.generate_epic(project_key)
                
                try:
                    epic_issue = self.task_repository.create_task(epic_data)
                    self.created_epics.append(epic_issue.key)
                    created_count += 1
                    LOGGER.info(f"Created epic {epic_issue.key}: {epic_data.summary}")
                except Exception as e:
                    LOGGER.error(f"Failed to create epic: {e}")
            
            # Generate stories
            LOGGER.info(f"Creating {story_count} stories...")
            for i in range(story_count):
                project_key = random.choice(RandomTaskConstants.PROJECT_KEYS)
                epic_key = random.choice(self.created_epics) if self.created_epics and random.random() > 0.3 else None
                story_data = self.generate_story(project_key, epic_key)
                
                try:
                    story_issue = self.task_repository.create_task(story_data)
                    self.created_stories.append(story_issue.key)
                    created_count += 1
                    LOGGER.info(f"Created story {story_issue.key}: {story_data.summary}")
                except Exception as e:
                    LOGGER.error(f"Failed to create story: {e}")
            
            # Generate tasks and sub-tasks
            LOGGER.info(f"Creating {task_count} tasks...")
            for i in range(task_count):
                project_key = random.choice(RandomTaskConstants.PROJECT_KEYS)
                parent_key = random.choice(self.created_stories) if self.created_stories and random.random() > 0.6 else None
                task_data = self.generate_task(project_key, parent_key)
                
                try:
                    task_issue = self.task_repository.create_task(task_data)
                    created_count += 1
                    LOGGER.info(f"Created task {task_issue.key}: {task_data.summary}")
                except Exception as e:
                    LOGGER.error(f"Failed to create task: {e}")
                    
        except Exception as e:
            LOGGER.error(f"Error during task generation: {e}")
        
        LOGGER.info(f"Task generation completed. Created {created_count} out of {total_count} requested tasks")
        LOGGER.info(f"Created {len(self.created_epics)} epics and {len(self.created_stories)} stories")


async def main():
    """Main function to run the random task generator."""
    try:
        print("🚀 Starting random task generation...")
        
        # Get the container and task repository
        container = get_container()
        task_repository = container[TaskManagerRepositoryInterface]
        
        print(f"✅ Successfully initialized task repository: {type(task_repository).__name__}")
        
        # Create generator and generate tasks
        generator = RandomTaskGenerator(task_repository)
        await generator.generate_random_tasks(100)
        
        print("✅ Random task generation completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
