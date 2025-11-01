"""Unit tests for DocumentationGenerationUseCase."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from unittest.mock import call

from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    AcceptanceCriteriaSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    ApiListSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    DepartmentChip,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    DocumentColor,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    FeatureDocumentation,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    FeatureTableInfo,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    SubtaskInfo,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    SubtasksSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    UserStorySection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    WireframeSection,
)
from jira_telegram_bot.entities.synth_pm.pm_board_features import (
    SynthPMFeatureEntity,
)
from jira_telegram_bot.use_cases.documentation_generation_usecase import (
    DocumentationGenerationUseCase,
)


class TestDocumentationGenerationUseCase(unittest.TestCase):
    """Test cases for DocumentationGenerationUseCase."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.google_docs_repo = MagicMock()
        self.user_config_interface = MagicMock()
        
        self.usecase = DocumentationGenerationUseCase(
            google_docs_repository=self.google_docs_repo,
            user_config=self.user_config_interface,
        )
        
        self.feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            description="Test Description",
            frontend="8",
            backend="16",
            ui_ux="4",
            jira_issue_key="FEAT-1",
        )
        
        self.release_note = MagicMock()
        self.release_note.release_version = "v1.0.0"


class TestBuildFeatureDocumentation(TestDocumentationGenerationUseCase):
    """Test building feature documentation."""
    
    def test_build_feature_documentation_basic(self):
        """Test building basic feature documentation."""
        doc = self.usecase._build_feature_documentation(
            self.feature,
            "epic_123",
        )
        
        self.assertIsInstance(doc, FeatureDocumentation)
        self.assertEqual(doc.feature_title, "Test Feature")
        self.assertEqual(doc.jira_issue_key, "FEAT-1")
        self.assertEqual(doc.epic_tab_id, "epic_123")
        self.assertIsInstance(doc.table_info, FeatureTableInfo)
        self.assertIsInstance(doc.user_story, UserStorySection)
        self.assertIsInstance(doc.acceptance_criteria, AcceptanceCriteriaSection)
        self.assertIsInstance(doc.wireframe, WireframeSection)
        self.assertIsInstance(doc.api_list, ApiListSection)
        self.assertIsInstance(doc.subtasks, SubtasksSection)
    
    def test_build_feature_documentation_without_issue_key(self):
        """Test building documentation when feature has no issue key."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            jira_issue_key=None,
        )
        
        doc = self.usecase._build_feature_documentation(feature, "epic_123")
        
        self.assertIsNone(doc.jira_issue_key)


class TestBuildTableInfo(TestDocumentationGenerationUseCase):
    """Test building feature table info."""
    
    def test_build_table_info(self):
        """Test building table info with all departments."""
        table_info = self.usecase._build_table_info(self.feature)
        
        self.assertIsInstance(table_info, FeatureTableInfo)
        self.assertEqual(len(table_info.department_chips), 3)
        
        departments = {chip.department for chip in table_info.department_chips}
        self.assertIn("Frontend", departments)
        self.assertIn("Backend", departments)
        self.assertIn("UI/UX", departments)
    
    def test_build_table_info_with_zero_hours(self):
        """Test building table info excludes departments with zero hours."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            frontend="8",
            backend="0",
            ui_ux="",
        )
        
        table_info = self.usecase._build_table_info(feature)
        
        self.assertEqual(len(table_info.department_chips), 1)
        self.assertEqual(table_info.department_chips[0].department, "Frontend")
    
    def test_build_table_info_no_departments(self):
        """Test building table info with no departments."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            frontend="0",
            backend="0",
        )
        
        table_info = self.usecase._build_table_info(feature)
        
        self.assertEqual(len(table_info.department_chips), 0)


class TestBuildDepartmentChips(TestDocumentationGenerationUseCase):
    """Test building department chips."""
    
    def test_build_department_chips(self):
        """Test building department chips."""
        chips = self.usecase._build_department_chips(self.feature)
        
        self.assertEqual(len(chips), 3)
        
        frontend_chip = next(c for c in chips if c.department == "Frontend")
        self.assertEqual(frontend_chip.estimated_hours, 8)
        
        backend_chip = next(c for c in chips if c.department == "Backend")
        self.assertEqual(backend_chip.estimated_hours, 16)


class TestBuildSections(TestDocumentationGenerationUseCase):
    """Test building individual sections."""
    
    def test_build_user_story_section(self):
        """Test building user story section."""
        section = self.usecase._build_user_story_section()
        
        self.assertIsInstance(section, UserStorySection)
        self.assertEqual(section.title, "User Story")
        self.assertIsNone(section.content)
    
    def test_build_acceptance_criteria_section(self):
        """Test building acceptance criteria section."""
        section = self.usecase._build_acceptance_criteria_section()
        
        self.assertIsInstance(section, AcceptanceCriteriaSection)
        self.assertEqual(section.title, "Acceptance Criteria")
        self.assertEqual(len(section.criteria), 0)
    
    def test_build_wireframe_section(self):
        """Test building wireframe section."""
        section = self.usecase._build_wireframe_section()
        
        self.assertIsInstance(section, WireframeSection)
        self.assertEqual(section.title, "Wireframe/Design")
        self.assertEqual(len(section.wireframe_links), 0)
    
    def test_build_api_list_section(self):
        """Test building API list section."""
        section = self.usecase._build_api_list_section(self.feature)
        
        self.assertIsInstance(section, ApiListSection)
        self.assertIn("FEAT-1", section.title)
        self.assertEqual(len(section.api_items), 0)
    
    def test_build_api_list_section_without_issue_key(self):
        """Test building API list when feature has no issue key."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            jira_issue_key=None,
        )
        
        section = self.usecase._build_api_list_section(feature)
        
        self.assertEqual(section.title, "API List for N/A")


class TestBuildSubtasksSection(TestDocumentationGenerationUseCase):
    """Test building subtasks section."""
    
    def test_build_subtasks_section_with_subtasks(self):
        """Test building subtasks section with subtasks."""
        subtask1 = MagicMock()
        subtask1.key = "SUB-1"
        subtask1.fields.summary = "Subtask 1"
        subtask1.fields.assignee = MagicMock(displayName="John Doe")
        subtask1.fields.status.name = "In Progress"
        
        subtask2 = MagicMock()
        subtask2.key = "SUB-2"
        subtask2.fields.summary = "Subtask 2"
        subtask2.fields.assignee = None
        subtask2.fields.status.name = "To Do"
        
        jira_subtasks = [subtask1, subtask2]
        
        section = self.usecase._build_subtasks_section(jira_subtasks)
        
        self.assertIsInstance(section, SubtasksSection)
        self.assertEqual(len(section.subtasks), 2)
        
        self.assertEqual(section.subtasks[0].issue_key, "SUB-1")
        self.assertEqual(section.subtasks[0].summary, "Subtask 1")
        self.assertEqual(section.subtasks[0].assignee, "John Doe")
        self.assertEqual(section.subtasks[0].status, "In Progress")
        
        self.assertEqual(section.subtasks[1].issue_key, "SUB-2")
        self.assertEqual(section.subtasks[1].assignee, "Unassigned")
    
    def test_build_subtasks_section_empty(self):
        """Test building subtasks section with no subtasks."""
        section = self.usecase._build_subtasks_section([])
        
        self.assertEqual(len(section.subtasks), 0)


class TestConvertToSubtaskInfo(TestDocumentationGenerationUseCase):
    """Test converting Jira subtask to SubtaskInfo."""
    
    def test_convert_jira_subtask_to_subtask_info(self):
        """Test converting Jira subtask to SubtaskInfo."""
        jira_subtask = MagicMock()
        jira_subtask.key = "SUB-1"
        jira_subtask.fields.summary = "Test Subtask"
        jira_subtask.fields.assignee = MagicMock(displayName="John Doe")
        jira_subtask.fields.status.name = "In Progress"
        
        subtask_info = self.usecase._convert_jira_subtask_to_subtask_info(
            jira_subtask,
        )
        
        self.assertIsInstance(subtask_info, SubtaskInfo)
        self.assertEqual(subtask_info.issue_key, "SUB-1")
        self.assertEqual(subtask_info.summary, "Test Subtask")
        self.assertEqual(subtask_info.assignee, "John Doe")
        self.assertEqual(subtask_info.status, "In Progress")
    
    def test_convert_jira_subtask_unassigned(self):
        """Test converting unassigned Jira subtask."""
        jira_subtask = MagicMock()
        jira_subtask.key = "SUB-1"
        jira_subtask.fields.summary = "Test Subtask"
        jira_subtask.fields.assignee = None
        jira_subtask.fields.status.name = "To Do"
        
        subtask_info = self.usecase._convert_jira_subtask_to_subtask_info(
            jira_subtask,
        )
        
        self.assertEqual(subtask_info.assignee, "Unassigned")


class TestDetermineColorCode(TestDocumentationGenerationUseCase):
    """Test determining color code from release note."""
    
    def test_determine_color_code_red(self):
        """Test determining red color code."""
        release_note = MagicMock()
        release_note.frontend_status = "Not Started"
        release_note.backend_status = "Not Started"
        
        color = self.usecase._determine_color_code(release_note)
        
        self.assertEqual(color, DocumentColor.RED)
    
    def test_determine_color_code_yellow(self):
        """Test determining yellow color code."""
        release_note = MagicMock()
        release_note.frontend_status = "In Progress"
        release_note.backend_status = "Not Started"
        
        color = self.usecase._determine_color_code(release_note)
        
        self.assertEqual(color, DocumentColor.YELLOW)
    
    def test_determine_color_code_green(self):
        """Test determining green color code."""
        release_note = MagicMock()
        release_note.frontend_status = "Done"
        release_note.backend_status = "Done"
        
        color = self.usecase._determine_color_code(release_note)
        
        self.assertEqual(color, DocumentColor.GREEN)
    
    def test_determine_color_code_default(self):
        """Test determining default color code."""
        release_note = MagicMock()
        release_note.frontend_status = None
        release_note.backend_status = None
        
        color = self.usecase._determine_color_code(release_note)
        
        self.assertEqual(color, DocumentColor.DEFAULT)


class TestCountDepartmentStatuses(TestDocumentationGenerationUseCase):
    """Test counting department statuses."""
    
    def test_count_department_statuses(self):
        """Test counting department statuses."""
        release_note = MagicMock()
        release_note.frontend_status = "Done"
        release_note.backend_status = "In Progress"
        release_note.ui_ux_status = "Not Started"
        release_note.ai_status = ""
        release_note.devops_status = None
        
        done, in_progress, not_started = self.usecase._count_department_statuses(
            release_note,
        )
        
        self.assertEqual(done, 1)
        self.assertEqual(in_progress, 1)
        self.assertEqual(not_started, 1)


class TestExtractDepartmentStatus(TestDocumentationGenerationUseCase):
    """Test extracting department status."""
    
    def test_extract_department_status(self):
        """Test extracting valid department status."""
        self.assertEqual(
            self.usecase._extract_department_status("Done"),
            "Done",
        )
        self.assertEqual(
            self.usecase._extract_department_status("In Progress"),
            "In Progress",
        )
        self.assertEqual(
            self.usecase._extract_department_status("Not Started"),
            "Not Started",
        )
    
    def test_extract_department_status_invalid(self):
        """Test extracting invalid department status."""
        self.assertIsNone(self.usecase._extract_department_status(""))
        self.assertIsNone(self.usecase._extract_department_status(None))
        self.assertIsNone(self.usecase._extract_department_status("Invalid"))


class TestCreateFeatureDocumentation(TestDocumentationGenerationUseCase):
    """Test creating feature documentation end-to-end."""
    
    def test_create_feature_documentation_async(self):
        """Test creating feature documentation asynchronously."""
        self.google_docs_repo.get_or_create_epic_tab.return_value = "epic_123"
        self.google_docs_repo.create_feature_subtab.return_value = "feature_456"
        
        result = self.usecase.create_feature_documentation(
            feature=self.feature,
            document_id="doc_123",
            epic_name="Epic 1",
            jira_subtasks=[],
            release_note=self.release_note,
        )
        
        self.google_docs_repo.get_or_create_epic_tab.assert_called_once_with(
            document_id="doc_123",
            epic_name="Epic 1",
        )
        
        self.google_docs_repo.create_feature_subtab.assert_called_once()
        args = self.google_docs_repo.create_feature_subtab.call_args
        self.assertEqual(args.kwargs["document_id"], "doc_123")
        self.assertEqual(args.kwargs["epic_tab_id"], "epic_123")
        self.assertIsInstance(
            args.kwargs["feature_documentation"],
            FeatureDocumentation,
        )
        
        self.assertEqual(result, "feature_456")


class TestCreateFeatureDocumentationAsync(TestDocumentationGenerationUseCase):
    """Test async version of create_feature_documentation."""
    
    async def test_create_feature_documentation_async(self):
        """Test creating feature documentation asynchronously."""
        self.google_docs_repo.get_or_create_epic_tab_async = MagicMock(
            return_value="epic_123",
        )
        self.google_docs_repo.create_feature_subtab_async = MagicMock(
            return_value="feature_456",
        )
        
        result = await self.usecase.create_feature_documentation_async(
            feature=self.feature,
            document_id="doc_123",
            epic_name="Epic 1",
            jira_subtasks=[],
            release_note=self.release_note,
        )
        
        self.google_docs_repo.get_or_create_epic_tab_async.assert_called_once()
        self.google_docs_repo.create_feature_subtab_async.assert_called_once()
        self.assertEqual(result, "feature_456")


class TestEdgeCases(TestDocumentationGenerationUseCase):
    """Test edge cases and error handling."""
    
    def test_build_department_chips_invalid_hours(self):
        """Test building chips with invalid hour values."""
        feature = SynthPMFeatureEntity(
            row_number=1,
            sheet_row_number=1,
            task_title="Test Feature",
            frontend="invalid",
            backend="16",
        )
        
        chips = self.usecase._build_department_chips(feature)
        
        self.assertEqual(len(chips), 1)
        self.assertEqual(chips[0].department, "Backend")
    
    def test_convert_subtask_with_missing_fields(self):
        """Test converting subtask with missing fields."""
        jira_subtask = MagicMock()
        jira_subtask.key = "SUB-1"
        jira_subtask.fields.summary = "Test"
        jira_subtask.fields.assignee = None
        jira_subtask.fields.status = None
        
        subtask_info = self.usecase._convert_jira_subtask_to_subtask_info(
            jira_subtask,
        )
        
        self.assertEqual(subtask_info.assignee, "Unassigned")
        self.assertIsNone(subtask_info.status)


if __name__ == "__main__":
    unittest.main()
