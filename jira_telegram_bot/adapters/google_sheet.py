from __future__ import annotations

import unittest
from abc import ABC
from abc import abstractmethod

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER

# --- Interface and Client Classes ---


class ISheetClient(ABC):
    @abstractmethod
    def get_worksheet(self, sheet_id: str, worksheet_index: int = 0):
        """
        Return the worksheet object given a sheet id and an optional worksheet index.
        """
        pass


class GoogleSheetClient(ISheetClient):
    def __init__(self, json_token_path: str, scope: list = None):
        # Define the default scope if not provided.
        if scope is None:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/drive",
            ]
        # Authenticate using the service account JSON token.
        self.credentials = ServiceAccountCredentials.from_json_keyfile_name(
            json_token_path,
            scope,
        )
        self.client = gspread.authorize(self.credentials)

    def get_worksheet(self, sheet_id: str, worksheet_index: int = 0):
        # Open the spreadsheet by its ID.
        spreadsheet = self.client.open_by_key(sheet_id)
        return spreadsheet.get_worksheet(worksheet_index)


# --- Repository Class ---


class SheetRepository:
    def __init__(self, sheet_client: ISheetClient):
        self.sheet_client = sheet_client

    def get_sheet_records(self, sheet_id: str, worksheet_index: int = 0):
        # Retrieve the worksheet and fetch all records.
        worksheet = self.sheet_client.get_worksheet(sheet_id, worksheet_index)
        return worksheet.get_all_records()


# --- Dummy Classes for Testing Purposes ---


class DummyWorksheet:
    def get_all_records(self):
        # Returns dummy data for testing.
        return [{"Name": "Alice", "Age": 30}, {"Name": "Bob", "Age": 25}]


class DummySheetClient(ISheetClient):
    def get_worksheet(self, sheet_id: str, worksheet_index: int = 0):
        # Returns a dummy worksheet instead of connecting to Google Sheets.
        return DummyWorksheet()


# --- Unit Tests ---


class TestSheetRepository(unittest.TestCase):
    def test_get_sheet_records(self):
        dummy_client = DummySheetClient()
        repository = SheetRepository(dummy_client)
        records = repository.get_sheet_records("dummy_sheet_id")
        expected = [{"Name": "Alice", "Age": 30}, {"Name": "Bob", "Age": 25}]
        self.assertEqual(records, expected)


# --- Main Function for Actual Usage ---


def main():
    # Replace with your actual JSON token path and Google Sheet ID.
    json_token_path = f"{DEFAULT_PATH}/parschat-bcf7f0f46a37.json"

    # To get your Google Sheet ID:
    # 1. Open your Google Sheet in a browser.
    # 2. Look at the URL, e.g.,
    #    https://docs.google.com/spreadsheets/d/1X2YZabcXYZ/edit#gid=0
    # 3. The sheet ID is the part between '/d/' and '/edit', e.g., "1X2YZabcXYZ".
    sheet_id = "14D4u-Z9VBa6WGyw__UQoR1IB2I3LIrMCz0IpbcZnKjY"

    try:
        # Initialize the Google Sheet client and repository.
        sheet_client = GoogleSheetClient(json_token_path)
        repository = SheetRepository(sheet_client)

        # Fetch records from the first worksheet (worksheet_index = 0)
        records = repository.get_sheet_records(sheet_id)
        LOGGER.info("Sheet Records:")
        for record in records:
            LOGGER.info(record)
    except Exception as e:
        LOGGER.error("An error occurred:", e)


if __name__ == "__main__":
    # Uncomment the next line to run tests
    # unittest.main()

    # Run the main function for actual usage
    main()
