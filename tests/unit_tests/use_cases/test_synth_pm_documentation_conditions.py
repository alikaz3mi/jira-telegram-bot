"""Tests for SynthPM documentation generation conditions."""
from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.synth_pm import SynthPMUseCase


class TestSynthPMDocumentationConditions:
    """Test documentation generation conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock dependencies
        self.mock_repository = AsyncMock()
        self.mock_notification_gateway = AsyncMock()
        self.mock_generate_acceptance_criteria_use_case = AsyncMock()
        self.mock_generate_test_scenarios_use_case = AsyncMock()
        self.mock_user_config = AsyncMock()
        self.mock_settings = Mock()
        self.mock_settings.developer_board_project_key = "TEST"

        # Create use case instance
        self.use_case = SynthPMUseCase(
            repository=self.mock_repository,
            settings=self.mock_settings,
            user_config=self.mock_user_config,
            notification_gateway=self.mock_notification_gateway,
            generate_acceptance_criteria_use_case=self.mock_generate_acceptance_criteria_use_case,
            generate_test_scenarios_use_case=self.mock_generate_test_scenarios_use_case,
        )

    @pytest.mark.asyncio
    async def test_generate_documentation_skips_when_no_content(self):
        """Test that documentation generation is skipped when feature has no relevant content."""
        # Create feature without description, acceptance_criteria, or test_cases
        feature = SynthPMFeatureEntity(
            sheet_row_number=1,
            task_title="Feature Without Content",
            task_description="",  # Empty
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Epic 1",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["feature"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="Medium",
            risk_assessment="Low",
            acceptance_criteria="",  # Empty
            test_cases="",  # Empty
            dependencies="Database",
            row_number=1,
            description=None,  # None
        )

        # Mock project info
        project_info = {"description": "Test project", "keywords": ["test"]}

        # Call the method
        result = await self.use_case.generate_feature_documentation(
            feature,
            project_info,
        )

        # Assert that generation was skipped
        assert result["status"] == "skipped"
        assert (
            "no content available for documentation generation"
            in result["message"].lower()
        )

        # Verify that AI use cases were not called
        self.mock_generate_acceptance_criteria_use_case.execute.assert_not_called()
        self.mock_generate_test_scenarios_use_case.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_documentation_proceeds_with_description(self):
        """Test that documentation generation proceeds when feature has description."""
        # Create feature with description
        feature = SynthPMFeatureEntity(
            sheet_row_number=1,
            task_title="Feature With Description",
            task_description="Feature task description",
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Epic 1",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["feature"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="Medium",
            risk_assessment="Low",
            acceptance_criteria="",  # Empty
            test_cases="",  # Empty
            dependencies="Database",
            row_number=1,
            description="This feature has a description",  # Has content
        )

        # Mock AI responses
        mock_acceptance_result = Mock()
        mock_acceptance_result.user_story = "Test user story"
        mock_acceptance_result.acceptance_criteria = ["Criteria 1", "Criteria 2"]
        mock_acceptance_result.delivery_process = ["Step 1", "Step 2"]

        mock_test_result = Mock()
        mock_test_result.test_scenarios = [
            Mock(
                **{
                    "dict.return_value": {
                        "test_number": 1,
                        "description": "Test scenario 1",
                    },
                },
            ),
        ]

        self.mock_generate_acceptance_criteria_use_case.execute.return_value = (
            mock_acceptance_result
        )
        self.mock_generate_test_scenarios_use_case.execute.return_value = (
            mock_test_result
        )

        # Mock project info
        project_info = {"description": "Test project", "keywords": ["test"]}

        # Call the method
        result = await self.use_case.generate_feature_documentation(
            feature,
            project_info,
        )

        # Assert that generation was successful
        assert result["status"] == "success"
        assert "documentation" in result
        assert result["user_story"] == "Test user story"

        # Verify that AI use cases were called
        self.mock_generate_acceptance_criteria_use_case.execute.assert_called_once()
        self.mock_generate_test_scenarios_use_case.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_documentation_proceeds_with_acceptance_criteria(self):
        """Test that documentation generation proceeds when feature has acceptance criteria."""
        # Create feature with acceptance criteria
        feature = SynthPMFeatureEntity(
            sheet_row_number=1,
            task_title="Feature With Acceptance Criteria",
            task_description="",
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Epic 1",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["feature"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="Medium",
            risk_assessment="Low",
            acceptance_criteria="Feature must work correctly",  # Has content
            test_cases="",  # Empty
            dependencies="Database",
            row_number=1,
            description=None,
        )

        # Mock AI responses
        mock_acceptance_result = Mock()
        mock_acceptance_result.user_story = "Test user story"
        mock_acceptance_result.acceptance_criteria = ["Criteria 1"]
        mock_acceptance_result.delivery_process = ["Step 1"]

        mock_test_result = Mock()
        mock_test_result.test_scenarios = []

        self.mock_generate_acceptance_criteria_use_case.execute.return_value = (
            mock_acceptance_result
        )
        self.mock_generate_test_scenarios_use_case.execute.return_value = (
            mock_test_result
        )

        # Mock project info
        project_info = {"description": "Test project", "keywords": ["test"]}

        # Call the method
        result = await self.use_case.generate_feature_documentation(
            feature,
            project_info,
        )

        # Assert that generation was successful
        assert result["status"] == "success"
        assert "documentation" in result

        # Verify that AI use cases were called
        self.mock_generate_acceptance_criteria_use_case.execute.assert_called_once()
        self.mock_generate_test_scenarios_use_case.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_documentation_proceeds_with_test_cases(self):
        """Test that documentation generation proceeds when feature has test cases."""
        # Create feature with test cases
        feature = SynthPMFeatureEntity(
            sheet_row_number=1,
            task_title="Feature With Test Cases",
            task_description="",
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Epic 1",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["feature"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="Medium",
            risk_assessment="Low",
            acceptance_criteria="",  # Empty
            test_cases="Test case 1: Verify functionality",  # Has content
            dependencies="Database",
            row_number=1,
            description=None,
        )

        # Mock AI responses
        mock_acceptance_result = Mock()
        mock_acceptance_result.user_story = "Test user story"
        mock_acceptance_result.acceptance_criteria = ["Criteria 1"]
        mock_acceptance_result.delivery_process = ["Step 1"]

        mock_test_result = Mock()
        mock_test_result.test_scenarios = []

        self.mock_generate_acceptance_criteria_use_case.execute.return_value = (
            mock_acceptance_result
        )
        self.mock_generate_test_scenarios_use_case.execute.return_value = (
            mock_test_result
        )

        # Mock project info
        project_info = {"description": "Test project", "keywords": ["test"]}

        # Call the method
        result = await self.use_case.generate_feature_documentation(
            feature,
            project_info,
        )

        # Assert that generation was successful
        assert result["status"] == "success"
        assert "documentation" in result

        # Verify that AI use cases were called
        self.mock_generate_acceptance_criteria_use_case.execute.assert_called_once()
        self.mock_generate_test_scenarios_use_case.execute.assert_called_once()
