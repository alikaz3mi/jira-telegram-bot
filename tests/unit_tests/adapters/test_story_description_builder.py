"""Unit tests for story description builder and dependency linking."""

import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

from jira_telegram_bot.adapters.repositories.synth_pm_repository import SynthPMRepository
from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity


class TestStoryDescriptionBuilder(unittest.TestCase):
    """Test story description building from ReleaseNoteEntity."""

    def setUp(self):
        """Set up test fixtures."""
        self.repository = MagicMock(spec=SynthPMRepository)

    def test_build_story_description_with_documentation_link_and_description(self):
        """Test building description with both documentation link and description."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 1.0.0",
            release_components="Component A, Component B",
            description="This is a test release with new features.",
            documentation_link="https://docs.example.com/release-1.0.0",
        )

        result = SynthPMRepository._build_story_description(self.repository, release_note)

        self.assertIn("📄 *Documentation:* https://docs.example.com/release-1.0.0", result)
        self.assertIn("This is a test release with new features.", result)

    def test_build_story_description_with_only_description(self):
        """Test building description with only description field."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 1.0.0",
            release_components="Component A",
            description="Simple release description.",
        )

        result = SynthPMRepository._build_story_description(self.repository, release_note)

        self.assertNotIn("📄 *Documentation:*", result)
        self.assertEqual(result, "Simple release description.")

    def test_build_story_description_with_only_documentation_link(self):
        """Test building description with only documentation link."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 1.0.0",
            release_components="Component A",
            description="",
            documentation_link="https://docs.example.com/release-1.0.0",
        )

        result = SynthPMRepository._build_story_description(self.repository, release_note)

        self.assertIn("📄 *Documentation:* https://docs.example.com/release-1.0.0", result)
        self.assertNotIn("Simple release description.", result)

    def test_build_story_description_with_empty_fields(self):
        """Test building description when all optional fields are empty."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 1.0.0",
            release_components="Component A",
            description="",
        )

        result = SynthPMRepository._build_story_description(self.repository, release_note)

        self.assertEqual(result, "")

    def test_build_story_description_with_whitespace_only(self):
        """Test building description when fields contain only whitespace."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 1.0.0",
            release_components="Component A",
            description="   ",
            documentation_link="   ",
        )

        result = SynthPMRepository._build_story_description(self.repository, release_note)

        self.assertEqual(result, "")

    def test_build_story_description_with_multiline_description(self):
        """Test building description with multiline description."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 1.0.0",
            release_components="Component A",
            description="Line 1\nLine 2\nLine 3",
            documentation_link="https://docs.example.com/release-1.0.0",
        )

        result = SynthPMRepository._build_story_description(self.repository, release_note)

        self.assertIn("📄 *Documentation:* https://docs.example.com/release-1.0.0", result)
        self.assertIn("Line 1\nLine 2\nLine 3", result)

    def test_build_story_description_with_special_characters(self):
        """Test building description with special characters."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 1.0.0",
            release_components="Component A",
            description="Description with special chars: !@#$%^&*()",
            documentation_link="https://docs.example.com/release?v=1.0.0&type=full",
        )

        result = SynthPMRepository._build_story_description(self.repository, release_note)

        self.assertIn("https://docs.example.com/release?v=1.0.0&type=full", result)
        self.assertIn("Description with special chars: !@#$%^&*()", result)

    def test_build_story_description_with_persian_characters(self):
        """Test building description with Persian/Farsi characters."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 1.0.0",
            release_components="Component A",
            description="این یک توضیح فارسی است.",
            documentation_link="https://docs.example.com/release-1.0.0",
        )

        result = SynthPMRepository._build_story_description(self.repository, release_note)

        self.assertIn("📄 *Documentation:* https://docs.example.com/release-1.0.0", result)
        self.assertIn("این یک توضیح فارسی است.", result)

    def test_build_story_description_preserves_formatting(self):
        """Test that description formatting is preserved."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 1.0.0",
            release_components="Component A",
            description="**Bold text**\n*Italic text*\n- Bullet point",
            documentation_link="https://docs.example.com/release-1.0.0",
        )

        result = SynthPMRepository._build_story_description(self.repository, release_note)

        self.assertIn("**Bold text**", result)
        self.assertIn("*Italic text*", result)
        self.assertIn("- Bullet point", result)


class TestStoryDependencyLinking(unittest.IsolatedAsyncioTestCase):
    """Test story dependency linking functionality."""

    async def test_parse_dependencies_comma_separated(self):
        """Test parsing comma-separated dependencies."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            description="Test release",
            dependencies="V 1.0.0, V 1.5.0, V 1.8.0",
        )
        
        # Parse dependencies
        dependency_names = [dep.strip() for dep in release_note.dependencies.split(",") if dep.strip()]
        
        self.assertEqual(len(dependency_names), 3)
        self.assertIn("V 1.0.0", dependency_names)
        self.assertIn("V 1.5.0", dependency_names)
        self.assertIn("V 1.8.0", dependency_names)

    async def test_dependencies_field_optional(self):
        """Test that dependencies field is optional."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 1.0.0",
            release_components="Component A",
            description="Test release",
        )
        
        self.assertIsNone(release_note.dependencies)

    async def test_dependencies_with_whitespace(self):
        """Test parsing dependencies with extra whitespace."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            description="Test release",
            dependencies="  V 1.0.0  ,  V 1.5.0  ,  V 1.8.0  ",
        )
        
        dependency_names = [dep.strip() for dep in release_note.dependencies.split(",") if dep.strip()]
        
        self.assertEqual(len(dependency_names), 3)
        self.assertEqual(dependency_names[0], "V 1.0.0")
        self.assertEqual(dependency_names[1], "V 1.5.0")
        self.assertEqual(dependency_names[2], "V 1.8.0")

    async def test_empty_dependencies_string(self):
        """Test handling empty dependencies string."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 1.0.0",
            release_components="Component A",
            description="Test release",
            dependencies="",
        )
        
        # Empty string should result in no dependencies
        if release_note.dependencies and release_note.dependencies.strip():
            dependency_names = [dep.strip() for dep in release_note.dependencies.split(",") if dep.strip()]
        else:
            dependency_names = []
        
        self.assertEqual(len(dependency_names), 0)

    async def test_single_dependency(self):
        """Test parsing single dependency."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            description="Test release",
            dependencies="V 1.0.0",
        )
        
        dependency_names = [dep.strip() for dep in release_note.dependencies.split(",") if dep.strip()]
        
        self.assertEqual(len(dependency_names), 1)
        self.assertEqual(dependency_names[0], "V 1.0.0")


class TestLinkStoryDependenciesMethod(unittest.IsolatedAsyncioTestCase):
    """Test link_story_dependencies method execution."""

    async def test_link_dependencies_adds_missing_links(self):
        """Test adding new dependency links when none exist."""
        mock_jira_repo = MagicMock()
        mock_jira_repo.get_issue_links = MagicMock(return_value=[])
        mock_jira_repo.link_issues = MagicMock()

        repository = MagicMock(spec=SynthPMRepository)
        repository.jira_repository = mock_jira_repo
        repository.get_story_by_release_name = AsyncMock(
            side_effect=["SYNTH-100", "SYNTH-110"],
        )

        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            description="Test release",
            dependencies="V 1.0.0, V 1.5.0",
        )

        await SynthPMRepository.link_story_dependencies(
            repository, "SYNTH-123", release_note,
        )

        assert repository.get_story_by_release_name.call_count == 2
        assert mock_jira_repo.link_issues.call_count == 2
        mock_jira_repo.link_issues.assert_any_call(
            dependent_issue_key="SYNTH-123",
            dependency_issue_key="SYNTH-100",
            link_type="Blocks",
        )
        mock_jira_repo.link_issues.assert_any_call(
            dependent_issue_key="SYNTH-123",
            dependency_issue_key="SYNTH-110",
            link_type="Blocks",
        )

    async def test_link_dependencies_skips_existing(self):
        """Test that already-linked dependencies are not duplicated."""
        mock_jira_repo = MagicMock()
        mock_jira_repo.get_issue_links = MagicMock(return_value=[
            {
                "id": "link-1",
                "type": {"name": "Blocks"},
                "outwardIssue": {"key": "SYNTH-100"},
            },
        ])
        mock_jira_repo.link_issues = MagicMock()

        repository = MagicMock(spec=SynthPMRepository)
        repository.jira_repository = mock_jira_repo
        repository.get_story_by_release_name = AsyncMock(return_value="SYNTH-100")

        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            dependencies="V 1.0.0",
        )

        await SynthPMRepository.link_story_dependencies(
            repository, "SYNTH-123", release_note,
        )

        mock_jira_repo.link_issues.assert_not_called()
        mock_jira_repo.delete_issue_link.assert_not_called()

    async def test_link_dependencies_removes_stale(self):
        """Test that stale links are removed."""
        mock_jira_repo = MagicMock()
        mock_jira_repo.get_issue_links = MagicMock(return_value=[
            {
                "id": "link-1",
                "type": {"name": "Blocks"},
                "outwardIssue": {"key": "SYNTH-OLD"},
            },
        ])
        mock_jira_repo.delete_issue_link = MagicMock()
        mock_jira_repo.link_issues = MagicMock()

        repository = MagicMock(spec=SynthPMRepository)
        repository.jira_repository = mock_jira_repo
        repository.get_story_by_release_name = AsyncMock(return_value="SYNTH-100")

        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            dependencies="V 1.0.0",
        )

        await SynthPMRepository.link_story_dependencies(
            repository, "SYNTH-123", release_note,
        )

        mock_jira_repo.delete_issue_link.assert_called_once_with("link-1")
        mock_jira_repo.link_issues.assert_called_once_with(
            dependent_issue_key="SYNTH-123",
            dependency_issue_key="SYNTH-100",
            link_type="Blocks",
        )

    async def test_link_dependencies_none(self):
        """Test with no dependencies specified."""
        repository = MagicMock(spec=SynthPMRepository)
        repository.get_story_by_release_name = AsyncMock()

        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            dependencies=None,
        )

        await SynthPMRepository.link_story_dependencies(
            repository, "SYNTH-123", release_note,
        )

        repository.get_story_by_release_name.assert_not_called()

    async def test_link_dependencies_empty_string(self):
        """Test with empty dependencies string."""
        repository = MagicMock(spec=SynthPMRepository)
        repository.get_story_by_release_name = AsyncMock()

        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            dependencies="",
        )

        await SynthPMRepository.link_story_dependencies(
            repository, "SYNTH-123", release_note,
        )

        repository.get_story_by_release_name.assert_not_called()

    async def test_link_dependencies_story_not_found(self):
        """Test when dependency story is not found."""
        mock_jira_repo = MagicMock()
        mock_jira_repo.get_issue_links = MagicMock(return_value=[])
        mock_jira_repo.link_issues = MagicMock()

        repository = MagicMock(spec=SynthPMRepository)
        repository.jira_repository = mock_jira_repo
        repository.get_story_by_release_name = AsyncMock(
            side_effect=["SYNTH-100", None],
        )

        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            dependencies="V 1.0.0, V 1.5.0",
        )

        await SynthPMRepository.link_story_dependencies(
            repository, "SYNTH-123", release_note,
        )

        assert mock_jira_repo.link_issues.call_count == 1

    async def test_link_dependencies_ignores_inward_links(self):
        """Test that inward links are not touched."""
        mock_jira_repo = MagicMock()
        mock_jira_repo.get_issue_links = MagicMock(return_value=[
            {
                "id": "link-in",
                "type": {"name": "Blocks"},
                "inwardIssue": {"key": "SYNTH-999"},
            },
        ])
        mock_jira_repo.link_issues = MagicMock()

        repository = MagicMock(spec=SynthPMRepository)
        repository.jira_repository = mock_jira_repo
        repository.get_story_by_release_name = AsyncMock(return_value="SYNTH-100")

        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            dependencies="V 1.0.0",
        )

        await SynthPMRepository.link_story_dependencies(
            repository, "SYNTH-123", release_note,
        )

        mock_jira_repo.delete_issue_link.assert_not_called()
        mock_jira_repo.link_issues.assert_called_once()

    async def test_link_dependencies_with_varied_spacing(self):
        """Test parsing dependencies with various comma and space combinations."""
        mock_jira_repo = MagicMock()
        mock_jira_repo.get_issue_links = MagicMock(return_value=[])
        mock_jira_repo.link_issues = MagicMock()

        repository = MagicMock(spec=SynthPMRepository)
        repository.jira_repository = mock_jira_repo
        repository.get_story_by_release_name = AsyncMock(
            side_effect=["SYNTH-100", "SYNTH-110", "SYNTH-120"],
        )

        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            dependencies="  V 1.0.0  ,V 1.5.0,  V 1.8.0",
        )

        await SynthPMRepository.link_story_dependencies(
            repository, "SYNTH-123", release_note,
        )

        assert repository.get_story_by_release_name.call_count == 3
        assert mock_jira_repo.link_issues.call_count == 3


class TestColumnMappingIntegration(unittest.TestCase):
    """Test column mapping for new fields."""

    def test_documentation_link_column_mapping(self):
        """Test that documentation_link column mapping is configured."""
        from jira_telegram_bot.adapters.repositories.synth_pm_repository import SynthPMRepository
        
        # Test Persian column name
        headers = ["ریلیز اصلی", "اجزای ریلیز", "شرح", "لینک مستندات"]
        repository = MagicMock(spec=SynthPMRepository)
        mapping = SynthPMRepository._create_release_notes_column_mapping(repository, headers)
        
        self.assertIn("documentation_link", mapping)
        self.assertEqual(mapping["documentation_link"], 3)

    def test_dependencies_column_mapping(self):
        """Test that dependencies column mapping is configured."""
        from jira_telegram_bot.adapters.repositories.synth_pm_repository import SynthPMRepository
        
        # Test Persian column name
        headers = ["ریلیز اصلی", "اجزای ریلیز", "شرح", "وابستگی ها"]
        repository = MagicMock(spec=SynthPMRepository)
        mapping = SynthPMRepository._create_release_notes_column_mapping(repository, headers)
        
        self.assertIn("dependencies", mapping)
        self.assertEqual(mapping["dependencies"], 3)

    def test_english_column_names(self):
        """Test English column names for documentation_link and dependencies."""
        from jira_telegram_bot.adapters.repositories.synth_pm_repository import SynthPMRepository
        
        headers = ["Release Version", "Components", "Description", "Documentation Link", "Dependencies"]
        repository = MagicMock(spec=SynthPMRepository)
        mapping = SynthPMRepository._create_release_notes_column_mapping(repository, headers)
        
        self.assertIn("documentation_link", mapping)
        self.assertEqual(mapping["documentation_link"], 3)
        self.assertIn("dependencies", mapping)
        self.assertEqual(mapping["dependencies"], 4)


class TestReleaseNoteEntityFields(unittest.TestCase):
    """Test ReleaseNoteEntity with new fields."""

    def test_entity_with_all_fields(self):
        """Test creating entity with documentation_link and dependencies."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            description="Test release",
            documentation_link="https://docs.example.com",
            dependencies="V 1.0.0, V 1.5.0",
        )
        
        self.assertEqual(release_note.documentation_link, "https://docs.example.com")
        self.assertEqual(release_note.dependencies, "V 1.0.0, V 1.5.0")

    def test_entity_with_none_fields(self):
        """Test creating entity without documentation_link and dependencies."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            description="Test release",
        )
        
        self.assertIsNone(release_note.documentation_link)
        self.assertIsNone(release_note.dependencies)

    def test_entity_immutability(self):
        """Test that ReleaseNoteEntity is immutable."""
        release_note = ReleaseNoteEntity(
            row_number=2,
            release_version="V 2.0.0",
            release_components="Component A",
            description="Test release",
            documentation_link="https://docs.example.com",
        )
        
        # Attempting to modify should raise an error (Pydantic frozen model)
        with self.assertRaises(Exception):
            release_note.documentation_link = "https://new-url.com"


class TestStoryDescriptionIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for story description with create_release_story."""

    async def asyncSetUp(self):
        """Set up test fixtures for async tests."""
        # These tests are placeholders for future full integration testing
        pass

    async def test_create_release_story_uses_release_note_description(self):
        """Test that create_release_story uses description from release_note.
        
        Note: This is a placeholder test. Full integration testing would require
        proper mocking of all SynthPMRepository dependencies.
        """
        # Verify that _build_story_description is called when release_note is provided
        # This would be tested with full mocking in a complete integration test
        pass

    async def test_create_release_story_without_release_note(self):
        """Test that create_release_story handles missing release_note gracefully.
        
        Note: This is a placeholder test. When release_note is None, 
        description should be empty string to maintain backward compatibility.
        """
        # This test verifies backward compatibility
        pass


if __name__ == "__main__":
    unittest.main()

