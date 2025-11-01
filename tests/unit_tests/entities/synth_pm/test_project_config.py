"""Unit tests for project configuration entities."""
from __future__ import annotations

import unittest

from jira_telegram_bot.entities.synth_pm.project_config import GoogleDocsConfig
from jira_telegram_bot.entities.synth_pm.project_config import GoogleSheetsConfig
from jira_telegram_bot.entities.synth_pm.project_config import (
    GoogleSheetsReleasesConfig,
)
from jira_telegram_bot.entities.synth_pm.project_config import (
    GoogleSheetsTasksConfig,
)
from jira_telegram_bot.entities.synth_pm.project_config import JiraBoardConfig
from jira_telegram_bot.entities.synth_pm.project_config import JiraConfig
from jira_telegram_bot.entities.synth_pm.project_config import ProjectConfig
from jira_telegram_bot.entities.synth_pm.project_config import ProjectsConfig


class TestGoogleSheetsTasksConfig(unittest.TestCase):
    """Test cases for GoogleSheetsTasksConfig entity."""
    
    def test_create_valid_config(self):
        """Test creating valid GoogleSheetsTasksConfig."""
        config = GoogleSheetsTasksConfig(
            spreadsheet_id="test_id",
            sheet_name="Test Sheet",
            gid=123,
            data_range="A2:Z",
        )
        
        self.assertEqual(config.spreadsheet_id, "test_id")
        self.assertEqual(config.sheet_name, "Test Sheet")
        self.assertEqual(config.gid, 123)
        self.assertEqual(config.data_range, "A2:Z")
    
    def test_config_is_frozen(self):
        """Test that config is immutable."""
        config = GoogleSheetsTasksConfig(
            spreadsheet_id="test_id",
            sheet_name="Test Sheet",
            gid=123,
            data_range="A2:Z",
        )
        
        with self.assertRaises(Exception):
            config.spreadsheet_id = "new_id"


class TestGoogleSheetsReleasesConfig(unittest.TestCase):
    """Test cases for GoogleSheetsReleasesConfig entity."""
    
    def test_create_valid_config(self):
        """Test creating valid GoogleSheetsReleasesConfig."""
        config = GoogleSheetsReleasesConfig(
            sheet_name="Releases",
            data_range="A2:M",
        )
        
        self.assertEqual(config.sheet_name, "Releases")
        self.assertEqual(config.data_range, "A2:M")


class TestGoogleSheetsConfig(unittest.TestCase):
    """Test cases for GoogleSheetsConfig entity."""
    
    def test_create_valid_config(self):
        """Test creating valid GoogleSheetsConfig."""
        tasks_config = GoogleSheetsTasksConfig(
            spreadsheet_id="test_id",
            sheet_name="Tasks",
            gid=123,
            data_range="A2:Z",
        )
        releases_config = GoogleSheetsReleasesConfig(
            sheet_name="Releases",
            data_range="A2:M",
        )
        
        config = GoogleSheetsConfig(
            spreadsheet_id="test_id",
            tasks=tasks_config,
            releases=releases_config,
        )
        
        self.assertEqual(config.spreadsheet_id, "test_id")
        self.assertEqual(config.tasks.sheet_name, "Tasks")
        self.assertEqual(config.releases.sheet_name, "Releases")


class TestGoogleDocsConfig(unittest.TestCase):
    """Test cases for GoogleDocsConfig entity."""
    
    def test_create_valid_config(self):
        """Test creating valid GoogleDocsConfig."""
        config = GoogleDocsConfig(
            document_id="doc_id",
            document_url="https://docs.google.com/document/d/doc_id/edit",
            epic_tab_mappings={"Epic1": "tab1"},
        )
        
        self.assertEqual(config.document_id, "doc_id")
        self.assertEqual(config.document_url, "https://docs.google.com/document/d/doc_id/edit")
        self.assertEqual(config.epic_tab_mappings, {"Epic1": "tab1"})
    
    def test_default_epic_tab_mappings(self):
        """Test default epic_tab_mappings is empty dict."""
        config = GoogleDocsConfig(
            document_id="doc_id",
            document_url="https://docs.google.com/document/d/doc_id/edit",
        )
        
        self.assertEqual(config.epic_tab_mappings, {})


class TestJiraBoardConfig(unittest.TestCase):
    """Test cases for JiraBoardConfig entity."""
    
    def test_create_valid_config(self):
        """Test creating valid JiraBoardConfig."""
        config = JiraBoardConfig(
            board_key="TEST",
            board_id=123,
            enabled=True,
        )
        
        self.assertEqual(config.board_key, "TEST")
        self.assertEqual(config.board_id, 123)
        self.assertTrue(config.enabled)
    
    def test_default_values(self):
        """Test default values for optional fields."""
        config = JiraBoardConfig(board_key="TEST")
        
        self.assertIsNone(config.board_id)
        self.assertTrue(config.enabled)


class TestJiraConfig(unittest.TestCase):
    """Test cases for JiraConfig entity."""
    
    def test_create_valid_config(self):
        """Test creating valid JiraConfig."""
        pm_board = JiraBoardConfig(board_key="PM")
        dev_board = JiraBoardConfig(board_key="DEV")
        support_board = JiraBoardConfig(board_key="SUP")
        
        config = JiraConfig(
            pm_board=pm_board,
            development_board=dev_board,
            support_board=support_board,
        )
        
        self.assertEqual(config.pm_board.board_key, "PM")
        self.assertEqual(config.development_board.board_key, "DEV")
        self.assertEqual(config.support_board.board_key, "SUP")
    
    def test_optional_support_board(self):
        """Test that support_board is optional."""
        pm_board = JiraBoardConfig(board_key="PM")
        dev_board = JiraBoardConfig(board_key="DEV")
        
        config = JiraConfig(
            pm_board=pm_board,
            development_board=dev_board,
        )
        
        self.assertIsNone(config.support_board)


class TestProjectConfig(unittest.TestCase):
    """Test cases for ProjectConfig entity."""
    
    def setUp(self):
        """Set up test fixtures."""
        tasks_config = GoogleSheetsTasksConfig(
            spreadsheet_id="test_id",
            sheet_name="Tasks",
            gid=123,
            data_range="A2:Z",
        )
        releases_config = GoogleSheetsReleasesConfig(
            sheet_name="Releases",
            data_range="A2:M",
        )
        self.google_sheets = GoogleSheetsConfig(
            spreadsheet_id="test_id",
            tasks=tasks_config,
            releases=releases_config,
        )
        
        self.google_docs = GoogleDocsConfig(
            document_id="doc_id",
            document_url="https://docs.google.com/document/d/doc_id/edit",
        )
        
        pm_board = JiraBoardConfig(board_key="PM")
        dev_board = JiraBoardConfig(board_key="DEV")
        self.jira = JiraConfig(
            pm_board=pm_board,
            development_board=dev_board,
        )
    
    def test_create_valid_config(self):
        """Test creating valid ProjectConfig."""
        config = ProjectConfig(
            project_name="Test Project",
            google_sheets=self.google_sheets,
            google_docs=self.google_docs,
            jira=self.jira,
        )
        
        self.assertEqual(config.project_name, "Test Project")
        self.assertEqual(config.google_sheets.spreadsheet_id, "test_id")
        self.assertEqual(config.google_docs.document_id, "doc_id")
        self.assertEqual(config.jira.pm_board.board_key, "PM")


class TestProjectsConfig(unittest.TestCase):
    """Test cases for ProjectsConfig entity."""
    
    def setUp(self):
        """Set up test fixtures."""
        tasks_config = GoogleSheetsTasksConfig(
            spreadsheet_id="test_id_1",
            sheet_name="Tasks",
            gid=123,
            data_range="A2:Z",
        )
        releases_config = GoogleSheetsReleasesConfig(
            sheet_name="Releases",
            data_range="A2:M",
        )
        google_sheets = GoogleSheetsConfig(
            spreadsheet_id="test_id_1",
            tasks=tasks_config,
            releases=releases_config,
        )
        
        google_docs = GoogleDocsConfig(
            document_id="doc_id_1",
            document_url="https://docs.google.com/document/d/doc_id_1/edit",
        )
        
        pm_board = JiraBoardConfig(board_key="PM1")
        dev_board = JiraBoardConfig(board_key="DEV1")
        jira = JiraConfig(
            pm_board=pm_board,
            development_board=dev_board,
        )
        
        self.project1 = ProjectConfig(
            project_name="Project 1",
            google_sheets=google_sheets,
            google_docs=google_docs,
            jira=jira,
        )
        
        tasks_config2 = GoogleSheetsTasksConfig(
            spreadsheet_id="test_id_2",
            sheet_name="Tasks",
            gid=456,
            data_range="A2:Z",
        )
        releases_config2 = GoogleSheetsReleasesConfig(
            sheet_name="Releases",
            data_range="A2:M",
        )
        google_sheets2 = GoogleSheetsConfig(
            spreadsheet_id="test_id_2",
            tasks=tasks_config2,
            releases=releases_config2,
        )
        
        google_docs2 = GoogleDocsConfig(
            document_id="doc_id_2",
            document_url="https://docs.google.com/document/d/doc_id_2/edit",
        )
        
        pm_board2 = JiraBoardConfig(board_key="PM2")
        dev_board2 = JiraBoardConfig(board_key="DEV2")
        jira2 = JiraConfig(
            pm_board=pm_board2,
            development_board=dev_board2,
        )
        
        self.project2 = ProjectConfig(
            project_name="Project 2",
            google_sheets=google_sheets2,
            google_docs=google_docs2,
            jira=jira2,
        )
    
    def test_create_valid_config(self):
        """Test creating valid ProjectsConfig."""
        config = ProjectsConfig(
            projects={
                "PROJECT1": self.project1,
                "PROJECT2": self.project2,
            },
        )
        
        self.assertEqual(len(config.projects), 2)
        self.assertIn("PROJECT1", config.projects)
        self.assertIn("PROJECT2", config.projects)
    
    def test_get_project(self):
        """Test getting project by name."""
        config = ProjectsConfig(
            projects={
                "PROJECT1": self.project1,
                "PROJECT2": self.project2,
            },
        )
        
        project = config.get_project("PROJECT1")
        
        self.assertIsNotNone(project)
        self.assertEqual(project.project_name, "Project 1")
    
    def test_get_project_not_found(self):
        """Test getting non-existent project."""
        config = ProjectsConfig(
            projects={"PROJECT1": self.project1},
        )
        
        project = config.get_project("NONEXISTENT")
        
        self.assertIsNone(project)
    
    def test_get_project_by_board_key(self):
        """Test getting project by board key."""
        config = ProjectsConfig(
            projects={
                "PROJECT1": self.project1,
                "PROJECT2": self.project2,
            },
        )
        
        project = config.get_project_by_board_key("DEV1")
        
        self.assertIsNotNone(project)
        self.assertEqual(project.project_name, "Project 1")
    
    def test_get_project_by_board_key_pm_board(self):
        """Test getting project by PM board key."""
        config = ProjectsConfig(
            projects={
                "PROJECT1": self.project1,
                "PROJECT2": self.project2,
            },
        )
        
        project = config.get_project_by_board_key("PM2")
        
        self.assertIsNotNone(project)
        self.assertEqual(project.project_name, "Project 2")
    
    def test_get_project_by_board_key_not_found(self):
        """Test getting project by non-existent board key."""
        config = ProjectsConfig(
            projects={"PROJECT1": self.project1},
        )
        
        project = config.get_project_by_board_key("NONEXISTENT")
        
        self.assertIsNone(project)
    
    def test_get_project_by_spreadsheet_id(self):
        """Test getting project by spreadsheet ID."""
        config = ProjectsConfig(
            projects={
                "PROJECT1": self.project1,
                "PROJECT2": self.project2,
            },
        )
        
        project = config.get_project_by_spreadsheet_id("test_id_2")
        
        self.assertIsNotNone(project)
        self.assertEqual(project.project_name, "Project 2")
    
    def test_get_project_by_spreadsheet_id_not_found(self):
        """Test getting project by non-existent spreadsheet ID."""
        config = ProjectsConfig(
            projects={"PROJECT1": self.project1},
        )
        
        project = config.get_project_by_spreadsheet_id("nonexistent")
        
        self.assertIsNone(project)


if __name__ == "__main__":
    unittest.main()
