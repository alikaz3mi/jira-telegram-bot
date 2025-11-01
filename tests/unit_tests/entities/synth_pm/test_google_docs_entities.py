"""Unit tests for Google Docs entities."""
from __future__ import annotations

import unittest

from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    AcceptanceCriteriaSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import ApiListSection
from jira_telegram_bot.entities.synth_pm.google_docs_entities import DepartmentChip
from jira_telegram_bot.entities.synth_pm.google_docs_entities import DocumentColor
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    DocumentationTaskInfo,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import EpicTab
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    ExpectedOutputSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    FeatureDocumentation,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    FeatureTableInfo,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    FinalDesignSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import SubtaskInfo
from jira_telegram_bot.entities.synth_pm.google_docs_entities import SubtasksSection
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    TableOfContents,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    UserStorySection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    WireframeSection,
)


class TestDepartmentChip(unittest.TestCase):
    """Test cases for DepartmentChip entity."""
    
    def test_create_chip_without_color(self):
        """Test creating chip without color."""
        chip = DepartmentChip(name="Frontend")
        
        self.assertEqual(chip.name, "Frontend")
        self.assertIsNone(chip.color)
    
    def test_create_chip_with_color(self):
        """Test creating chip with color."""
        chip = DepartmentChip(name="Backend", color="blue")
        
        self.assertEqual(chip.name, "Backend")
        self.assertEqual(chip.color, "blue")
    
    def test_chip_is_frozen(self):
        """Test that chip is immutable."""
        chip = DepartmentChip(name="Frontend")
        
        with self.assertRaises(Exception):
            chip.name = "Backend"


class TestFeatureTableInfo(unittest.TestCase):
    """Test cases for FeatureTableInfo entity."""
    
    def test_create_valid_table_info(self):
        """Test creating valid FeatureTableInfo."""
        departments = [
            DepartmentChip(name="Frontend"),
            DepartmentChip(name="Backend"),
        ]
        
        table_info = FeatureTableInfo(
            release_link="https://jira.com/browse/REL-1",
            feature_link="https://jira.com/browse/FEAT-1",
            departments=departments,
            reporter_email="reporter@example.com",
            start_date="2025-11-01",
            final_delivery_date="2025-11-15",
        )
        
        self.assertEqual(table_info.release_link, "https://jira.com/browse/REL-1")
        self.assertEqual(len(table_info.departments), 2)
        self.assertEqual(table_info.reporter_email, "reporter@example.com")


class TestUserStorySection(unittest.TestCase):
    """Test cases for UserStorySection entity."""
    
    def test_create_with_defaults(self):
        """Test creating UserStorySection with default values."""
        section = UserStorySection(
            story_content="As a user, I want to...",
        )
        
        self.assertEqual(section.heading_level, 2)
        self.assertEqual(section.title, "یوزر استوری")
        self.assertEqual(section.story_content, "As a user, I want to...")


class TestAcceptanceCriteriaSection(unittest.TestCase):
    """Test cases for AcceptanceCriteriaSection entity."""
    
    def test_create_with_criteria_list(self):
        """Test creating AcceptanceCriteriaSection."""
        criteria = [
            "معیار اول",
            "معیار دوم",
            "معیار سوم",
        ]
        
        section = AcceptanceCriteriaSection(criteria_list=criteria)
        
        self.assertEqual(section.heading_level, 2)
        self.assertEqual(section.title, "معیارهای پذیرش")
        self.assertEqual(len(section.criteria_list), 3)


class TestWireframeSection(unittest.TestCase):
    """Test cases for WireframeSection entity."""
    
    def test_create_without_figma_link(self):
        """Test creating WireframeSection without Figma link."""
        section = WireframeSection(
            designer_email="designer@example.com",
        )
        
        self.assertEqual(section.designer_email, "designer@example.com")
        self.assertIsNone(section.figma_link)
    
    def test_create_with_figma_link(self):
        """Test creating WireframeSection with Figma link."""
        section = WireframeSection(
            designer_email="designer@example.com",
            figma_link="https://figma.com/file/abc",
        )
        
        self.assertEqual(section.figma_link, "https://figma.com/file/abc")


class TestApiListSection(unittest.TestCase):
    """Test cases for ApiListSection entity."""
    
    def test_create_backend_apis(self):
        """Test creating ApiListSection for Backend."""
        section = ApiListSection(
            department="Backend",
            assignee_emails=["dev1@example.com", "dev2@example.com"],
        )
        
        self.assertEqual(section.title, "لیست API های بکند و خروجی آنها")
        self.assertEqual(section.department, "Backend")
        self.assertEqual(len(section.assignee_emails), 2)
    
    def test_create_ai_apis(self):
        """Test creating ApiListSection for AI."""
        section = ApiListSection(
            department="AI",
            assignee_emails=["ai@example.com"],
        )
        
        self.assertEqual(section.title, "لیست API های هوش و خروجی آن ها")
        self.assertEqual(section.department, "AI")
    
    def test_custom_title(self):
        """Test creating ApiListSection with custom title."""
        section = ApiListSection(
            department="Backend",
            assignee_emails=["dev@example.com"],
            title="Custom Title",
        )
        
        self.assertEqual(section.title, "Custom Title")


class TestSubtaskInfo(unittest.TestCase):
    """Test cases for SubtaskInfo entity."""
    
    def test_create_with_acceptance_criteria(self):
        """Test creating SubtaskInfo with acceptance criteria."""
        subtask = SubtaskInfo(
            title="Implement API",
            jira_link="https://jira.com/browse/SUB-1",
            acceptance_criteria=["API باید RESTful باشد", "Response time < 200ms"],
        )
        
        self.assertEqual(subtask.title, "Implement API")
        self.assertEqual(subtask.jira_link, "https://jira.com/browse/SUB-1")
        self.assertEqual(len(subtask.acceptance_criteria), 2)
    
    def test_create_without_acceptance_criteria(self):
        """Test creating SubtaskInfo without acceptance criteria."""
        subtask = SubtaskInfo(
            title="Implement API",
            jira_link="https://jira.com/browse/SUB-1",
        )
        
        self.assertIsNone(subtask.acceptance_criteria)


class TestSubtasksSection(unittest.TestCase):
    """Test cases for SubtasksSection entity."""
    
    def test_create_with_multiple_subtasks(self):
        """Test creating SubtasksSection with multiple subtasks."""
        subtasks = [
            SubtaskInfo(
                title="Subtask 1",
                jira_link="https://jira.com/browse/SUB-1",
            ),
            SubtaskInfo(
                title="Subtask 2",
                jira_link="https://jira.com/browse/SUB-2",
            ),
        ]
        
        section = SubtasksSection(subtasks=subtasks)
        
        self.assertEqual(section.title, "تسک های زیرمجموعه")
        self.assertEqual(len(section.subtasks), 2)


class TestDocumentationTaskInfo(unittest.TestCase):
    """Test cases for DocumentationTaskInfo entity."""
    
    def test_create_with_default_hours(self):
        """Test creating DocumentationTaskInfo with default hours."""
        task = DocumentationTaskInfo(
            department="Frontend",
            assignee_email="dev@example.com",
            task_title="مستندسازی Frontend",
            parent_issue_key="FEAT-1",
        )
        
        self.assertEqual(task.estimated_hours, 2)
        self.assertEqual(task.department, "Frontend")
    
    def test_create_with_custom_hours(self):
        """Test creating DocumentationTaskInfo with custom hours."""
        task = DocumentationTaskInfo(
            department="Backend",
            assignee_email="dev@example.com",
            estimated_hours=4,
            task_title="مستندسازی Backend",
            parent_issue_key="FEAT-1",
        )
        
        self.assertEqual(task.estimated_hours, 4)


class TestFeatureDocumentation(unittest.TestCase):
    """Test cases for FeatureDocumentation entity."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.departments = [DepartmentChip(name="Frontend")]
        self.table_info = FeatureTableInfo(
            release_link="https://jira.com/browse/REL-1",
            feature_link="https://jira.com/browse/FEAT-1",
            departments=self.departments,
            reporter_email="reporter@example.com",
            start_date="2025-11-01",
            final_delivery_date="2025-11-15",
        )
        self.toc = TableOfContents(sections=["یوزر استوری", "معیارهای پذیرش"])
        self.user_story = UserStorySection(story_content="As a user...")
        self.acceptance_criteria = AcceptanceCriteriaSection(
            criteria_list=["معیار اول"],
        )
        self.expected_output = ExpectedOutputSection(
            reporter_email="reporter@example.com",
        )
        self.subtasks = SubtasksSection(subtasks=[])
    
    def test_create_minimal_documentation(self):
        """Test creating minimal FeatureDocumentation."""
        doc = FeatureDocumentation(
            feature_title="Test Feature",
            table_of_contents=self.toc,
            feature_info_table=self.table_info,
            user_story=self.user_story,
            acceptance_criteria=self.acceptance_criteria,
            expected_output=self.expected_output,
            subtasks=self.subtasks,
        )
        
        self.assertEqual(doc.feature_title, "Test Feature")
        self.assertIsNone(doc.wireframe)
        self.assertIsNone(doc.backend_apis)
        self.assertEqual(doc.color_code, DocumentColor.DEFAULT)
    
    def test_create_full_documentation(self):
        """Test creating full FeatureDocumentation with all sections."""
        wireframe = WireframeSection(designer_email="designer@example.com")
        backend_apis = ApiListSection(
            department="Backend",
            assignee_emails=["dev@example.com"],
        )
        
        doc = FeatureDocumentation(
            feature_title="Test Feature",
            table_of_contents=self.toc,
            feature_info_table=self.table_info,
            user_story=self.user_story,
            acceptance_criteria=self.acceptance_criteria,
            wireframe=wireframe,
            backend_apis=backend_apis,
            expected_output=self.expected_output,
            subtasks=self.subtasks,
            color_code=DocumentColor.RED,
        )
        
        self.assertIsNotNone(doc.wireframe)
        self.assertIsNotNone(doc.backend_apis)
        self.assertEqual(doc.color_code, DocumentColor.RED)


class TestEpicTab(unittest.TestCase):
    """Test cases for EpicTab entity."""
    
    def test_create_epic_tab_without_tab_id(self):
        """Test creating EpicTab without tab_id."""
        epic = EpicTab(epic_name="Test Epic")
        
        self.assertEqual(epic.epic_name, "Test Epic")
        self.assertIsNone(epic.tab_id)
        self.assertEqual(len(epic.features), 0)
    
    def test_create_epic_tab_with_features(self):
        """Test creating EpicTab with features."""
        departments = [DepartmentChip(name="Frontend")]
        table_info = FeatureTableInfo(
            release_link="link",
            feature_link="link",
            departments=departments,
            reporter_email="email",
            start_date="date",
            final_delivery_date="date",
        )
        toc = TableOfContents(sections=["section"])
        user_story = UserStorySection(story_content="story")
        acceptance_criteria = AcceptanceCriteriaSection(criteria_list=["criteria"])
        expected_output = ExpectedOutputSection(reporter_email="email")
        subtasks = SubtasksSection(subtasks=[])
        
        feature_doc = FeatureDocumentation(
            feature_title="Feature 1",
            table_of_contents=toc,
            feature_info_table=table_info,
            user_story=user_story,
            acceptance_criteria=acceptance_criteria,
            expected_output=expected_output,
            subtasks=subtasks,
        )
        
        epic = EpicTab(
            epic_name="Test Epic",
            tab_id="tab_1",
            features=[feature_doc],
        )
        
        self.assertEqual(len(epic.features), 1)
        self.assertEqual(epic.features[0].feature_title, "Feature 1")


class TestDocumentColor(unittest.TestCase):
    """Test cases for DocumentColor enum."""
    
    def test_color_values(self):
        """Test DocumentColor enum values."""
        self.assertEqual(DocumentColor.RED.value, "RED")
        self.assertEqual(DocumentColor.YELLOW.value, "YELLOW")
        self.assertEqual(DocumentColor.GREEN.value, "GREEN")
        self.assertEqual(DocumentColor.DEFAULT.value, "DEFAULT")


if __name__ == "__main__":
    unittest.main()
