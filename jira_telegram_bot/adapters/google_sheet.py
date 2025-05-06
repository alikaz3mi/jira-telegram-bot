from __future__ import annotations

import asyncio
import unittest
from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.jira.jira_server_repository import (
    JiraRepository,
)
from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.settings import GOOGLE_SHEETS_SETTINGS


class ISheetClient(ABC):
    """Interface for Google Sheets client implementations."""

    @abstractmethod
    def get_worksheet(self, sheet_id: str, worksheet_index: int = 0):
        """
        Return the worksheet object given a sheet id and an optional worksheet index.

        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_index: Index of the worksheet (default: 0)

        Returns:
            Worksheet object
        """
        pass

    @abstractmethod
    def get_worksheet_by_name(self, sheet_id: str, worksheet_name: str):
        """
        Return the worksheet object given a sheet id and worksheet name.

        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_name: Name of the worksheet

        Returns:
            Worksheet object
        """
        pass


class GoogleSheetClient(ISheetClient):
    """Implementation of Google Sheets client using gspread."""

    def __init__(self, json_token_path: str, scope: List[str] = None):
        """
        Initialize the Google Sheets client with authentication.

        Args:
            json_token_path: Path to the Google API token JSON file
            scope: List of OAuth scopes (default: None, uses standard scopes)
        """
        # Define the default scope if not provided.
        if scope is None:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive",
            ]
        # Authenticate using the service account JSON token.
        try:
            self.credentials = ServiceAccountCredentials.from_json_keyfile_name(
                json_token_path,
                scope,
            )
            self.client = gspread.authorize(self.credentials)
            LOGGER.debug("Successfully authenticated with Google Sheets API")
        except Exception as e:
            LOGGER.error(f"Failed to authenticate with Google Sheets API: {e}")
            raise

    def get_worksheet(self, sheet_id: str, worksheet_index: int = 0):
        """
        Get worksheet by index.

        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_index: Index of the worksheet (default: 0)

        Returns:
            Worksheet object
        """
        try:
            # Open the spreadsheet by its ID.
            spreadsheet = self.client.open_by_key(sheet_id)
            return spreadsheet.get_worksheet(worksheet_index)
        except Exception as e:
            LOGGER.error(f"Error getting worksheet by index {worksheet_index}: {e}")
            raise

    def get_worksheet_by_name(self, sheet_id: str, worksheet_name: str):
        """
        Get worksheet by name.

        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_name: Name of the worksheet

        Returns:
            Worksheet object
        """
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            return spreadsheet.worksheet(worksheet_name)
        except Exception as e:
            LOGGER.error(f"Error getting worksheet by name '{worksheet_name}': {e}")
            raise


class SheetRepository:
    """Repository for interacting with Google Sheets data."""

    def __init__(self, sheet_client: ISheetClient):
        """
        Initialize the repository with a sheet client.

        Args:
            sheet_client: An implementation of ISheetClient
        """
        self.sheet_client = sheet_client

    def get_sheet_records(
        self,
        sheet_id: str,
        worksheet_index: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all records from a worksheet by index.

        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_index: Index of the worksheet (default: 0)

        Returns:
            List of records as dictionaries
        """
        try:
            worksheet = self.sheet_client.get_worksheet(sheet_id, worksheet_index)
            records = worksheet.get_all_records()
            LOGGER.debug(
                f"Retrieved {len(records)} records from worksheet index {worksheet_index}",
            )
            return records
        except Exception as e:
            LOGGER.error(f"Error retrieving sheet records: {e}")
            return []

    def get_assignment_records(
        self,
        sheet_id: str,
        worksheet_name: str = "Assignments",
    ) -> List[Dict[str, Any]]:
        """
        Get records from the assignments worksheet in the specified sheet.

        Args:
            sheet_id: The ID of the Google Sheet
            worksheet_name: Name of the worksheet containing assignments (default: "Assignments")

        Returns:
            List of assignment records
        """
        try:
            if isinstance(self.sheet_client, GoogleSheetClient):
                # Directly use client property if available
                worksheet = self.sheet_client.get_worksheet_by_name(
                    sheet_id,
                    worksheet_name,
                )
            else:
                # Fallback for other implementations
                spreadsheet = self.sheet_client.client.open_by_key(sheet_id)
                worksheet = spreadsheet.worksheet(worksheet_name)

            records = worksheet.get_all_records()
            LOGGER.debug(
                f"Retrieved {len(records)} assignment records from worksheet '{worksheet_name}'",
            )
            return records
        except Exception as e:
            LOGGER.error(f"Error fetching assignment records: {e}")
            return []

    def create_jira_tasks_from_assignments(
        self,
        sheet_id: str,
        jira_repository: JiraRepository,
        worksheet_name: str = "Assignments",
        project_key: Optional[str] = None,
        default_task_type: str = "Task",
    ) -> List[str]:
        """
        Create Jira tasks from assignments in the Google Sheet.

        Args:
            sheet_id: The ID of the Google Sheet
            jira_repository: JiraRepository instance to create tasks
            worksheet_name: Name of the worksheet containing assignments
            project_key: Optional project key override
            default_task_type: Default task type if not specified in sheet

        Returns:
            List of created issue keys
        """
        assignments = self.get_assignment_records(sheet_id, worksheet_name)
        created_issues = []

        if not assignments:
            LOGGER.warning(f"No assignments found in worksheet '{worksheet_name}'")
            return []

        LOGGER.info(f"Found {len(assignments)} assignments to process")

        for idx, assignment in enumerate(assignments):
            # Skip rows that are marked as "Skip" or don't have required fields
            if (
                not assignment.get("Summary")
                or assignment.get("Skip", "").lower() == "yes"
            ):
                continue

            task_data = self._create_task_data(
                assignment,
                project_key,
                default_task_type,
            )

            # Set sprint if available
            if assignment.get("Sprint") and task_data.project_key:
                self._set_sprint_for_task(
                    task_data,
                    jira_repository,
                    assignment.get("Sprint"),
                )

            # Create the Jira task
            try:
                LOGGER.info(
                    f"Creating task {idx+1}/{len(assignments)}: {task_data.summary}",
                )
                issue = jira_repository.create_task(task_data)
                created_issues.append(issue.key)
                LOGGER.info(f"Created issue {issue.key}")
            except Exception as e:
                LOGGER.error(f"Error creating task '{task_data.summary}': {e}")

        return created_issues

    def _create_task_data(
        self,
        assignment: Dict[str, Any],
        project_key: Optional[str] = None,
        default_task_type: str = "Task",
    ) -> TaskData:
        """
        Create a TaskData object from an assignment record.

        Args:
            assignment: Assignment record from Google Sheet
            project_key: Optional project key override
            default_task_type: Default task type

        Returns:
            TaskData object
        """
        task_data = TaskData(
            project_key=project_key or assignment.get("Project"),
            summary=assignment.get("Summary", ""),
            description=assignment.get("Description", ""),
            components=self._split_comma_separated(assignment.get("Component", "")),
            task_type=assignment.get("Type", default_task_type),
            story_points=float(assignment.get("Story Points", 0))
            if assignment.get("Story Points")
            else None,
            assignee=assignment.get("Assignee"),
            priority=assignment.get("Priority"),
            epic_link=assignment.get("Epic"),
            labels=self._split_comma_separated(assignment.get("Labels", "")),
        )

        # Set release/fix version if available
        if assignment.get("Release"):
            task_data.release = assignment.get("Release")

        return task_data

    def _set_sprint_for_task(
        self,
        task_data: TaskData,
        jira_repository: JiraRepository,
        sprint_name: str,
    ):
        """
        Set the sprint ID for a task based on sprint name.

        Args:
            task_data: The TaskData object to update
            jira_repository: JiraRepository instance
            sprint_name: Name of the sprint to find
        """
        board_id = jira_repository.get_board_id(task_data.project_key)
        if board_id:
            sprints = jira_repository.get_sprints(board_id)
            for sprint in sprints:
                if sprint.name == sprint_name:
                    task_data.sprint_id = sprint.id
                    LOGGER.debug(
                        f"Found sprint ID {sprint.id} for sprint '{sprint_name}'",
                    )
                    break
            if not task_data.sprint_id:
                LOGGER.warning(
                    f"Could not find sprint '{sprint_name}' for project {task_data.project_key}",
                )

    def _split_comma_separated(self, value: str) -> List[str]:
        """
        Split a comma-separated string into a list of trimmed values.

        Args:
            value: Comma-separated string

        Returns:
            List of trimmed values
        """
        return [item.strip() for item in value.split(",") if item.strip()]


# --- Dummy Classes for Testing Purposes ---


class DummyWorksheet:
    def get_all_records(self):
        # Returns dummy data for testing.
        return [{"Name": "Alice", "Age": 30}, {"Name": "Bob", "Age": 25}]


class DummySheetClient(ISheetClient):
    def get_worksheet(self, sheet_id: str, worksheet_index: int = 0):
        # Returns a dummy worksheet instead of connecting to Google Sheets.
        return DummyWorksheet()

    def get_worksheet_by_name(self, sheet_id: str, worksheet_name: str):
        # Returns a dummy worksheet instead of connecting to Google Sheets.
        return DummyWorksheet()

    @property
    def client(self):
        return self


# --- Unit Tests ---


class TestSheetRepository(unittest.TestCase):
    def test_get_sheet_records(self):
        dummy_client = DummySheetClient()
        repository = SheetRepository(dummy_client)
        records = repository.get_sheet_records("dummy_sheet_id")
        expected = [{"Name": "Alice", "Age": 30}, {"Name": "Bob", "Age": 25}]
        self.assertEqual(records, expected)


# --- Main Function for Actual Usage ---


async def create_tasks_from_sheet() -> List[str]:
    """
    Create Jira tasks from assignments in a Google Sheet.

    Returns:
        List of created issue keys
    """
    try:
        # Initialize the JiraRepository
        from jira_telegram_bot.settings import JIRA_SETTINGS

        jira_repository = JiraRepository(JIRA_SETTINGS)

        # Initialize the Google Sheet client and repository
        sheet_client = GoogleSheetClient(GOOGLE_SHEETS_SETTINGS.token_path)
        repository = SheetRepository(sheet_client)

        # Create tasks from the assignments
        created_issues = repository.create_jira_tasks_from_assignments(
            sheet_id=GOOGLE_SHEETS_SETTINGS.sheet_id,
            jira_repository=jira_repository,
            worksheet_name=GOOGLE_SHEETS_SETTINGS.worksheet_name,
            project_key=None,  # This can be specified in the sheet
        )

        LOGGER.info(
            f"Successfully created {len(created_issues)} tasks: {', '.join(created_issues)}",
        )
        return created_issues
    except Exception as e:
        LOGGER.error(f"An error occurred: {e}")
        return []


def main():
    """Main function for running as a script."""
    try:
        # Initialize the Google Sheet client and repository
        sheet_client = GoogleSheetClient(GOOGLE_SHEETS_SETTINGS.token_path)
        repository = SheetRepository(sheet_client)

        # Fetch records from the first worksheet (worksheet_index = 0)
        records = repository.get_sheet_records(GOOGLE_SHEETS_SETTINGS.sheet_id)
        LOGGER.info("Sheet Records:")
        for record in records:
            LOGGER.info(record)

        # Run the async function to create tasks
        asyncio.run(create_tasks_from_sheet())
    except Exception as e:
        LOGGER.error(f"An error occurred: {e}")


if __name__ == "__main__":
    # Uncomment the next line to run tests
    # unittest.main()

    # Run the main function for actual usage
    main()
