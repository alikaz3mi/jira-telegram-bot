"""Test cases for generate user story AI agent models."""

import unittest
from typing import Dict
from typing import List

from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryInput
from jira_telegram_bot.entities.ai_agent_models.generate_user_story import GenerateUserStoryResult
from jira_telegram_bot.entities.ai_agent_models.generate_user_story import UserStoryCandidate


class TestGenerateUserStoryInput(unittest.TestCase):
    """Test cases for GenerateUserStoryInput entity."""

    def test_create_with_minimal_data(self):
        """Test creating input with minimal required data."""
        # Arrange & Act
        input_data = GenerateUserStoryInput(
            raw_text="Create login feature",
            project_key="PROJ"
        )
        
        # Assert
        self.assertEqual(input_data.raw_text, "Create login feature")
        self.assertEqual(input_data.project_key, "PROJ")
        self.assertIsNone(input_data.project_context)
        self.assertEqual(input_data.available_components, [])
        self.assertEqual(input_data.available_epics, [])
        self.assertIsNone(input_data.current_sprint_info)

    def test_create_with_full_data(self):
        """Test creating input with all fields populated."""
        # Arrange
        available_components = ["backend", "frontend", "database"]
        available_epics = [
            {"key": "PROJ-100", "summary": "User Management Epic"},
            {"key": "PROJ-200", "summary": "Authentication Epic"}
        ]
        current_sprint_info = {
            "name": "Sprint 1",
            "goal": "Implement user authentication"
        }
        
        # Act
        input_data = GenerateUserStoryInput(
            raw_text="Create secure login with 2FA",
            project_key="PROJ",
            project_context="E-commerce platform for online retail",
            available_components=available_components,
            available_epics=available_epics,
            current_sprint_info=current_sprint_info
        )
        
        # Assert
        self.assertEqual(input_data.raw_text, "Create secure login with 2FA")
        self.assertEqual(input_data.project_key, "PROJ")
        self.assertEqual(input_data.project_context, "E-commerce platform for online retail")
        self.assertEqual(input_data.available_components, available_components)
        self.assertEqual(input_data.available_epics, available_epics)
        self.assertEqual(input_data.current_sprint_info, current_sprint_info)


class TestUserStoryCandidate(unittest.TestCase):
    """Test cases for UserStoryCandidate entity."""

    def test_create_with_minimal_data(self):
        """Test creating candidate with minimal required data."""
        # Arrange & Act
        candidate = UserStoryCandidate(
            summary="As a user, I want to login",
            description="User authentication feature"
        )
        
        # Assert
        self.assertEqual(candidate.summary, "As a user, I want to login")
        self.assertEqual(candidate.description, "User authentication feature")
        self.assertEqual(candidate.acceptance_criteria, [])
        self.assertIsNone(candidate.story_points)
        self.assertEqual(candidate.priority, "Medium")
        self.assertEqual(candidate.components, [])
        self.assertEqual(candidate.labels, [])
        self.assertIsNone(candidate.epic_link)
        self.assertIsNone(candidate.assignee_suggestion)

    def test_create_with_full_data(self):
        """Test creating candidate with all fields populated."""
        # Arrange
        acceptance_criteria = [
            "Given a valid username and password, when user clicks login, then user is authenticated",
            "Given invalid credentials, when user clicks login, then error message is shown"
        ]
        components = ["authentication", "frontend"]
        labels = ["security", "high-priority"]
        
        # Act
        candidate = UserStoryCandidate(
            summary="As a user, I want secure login with 2FA",
            description="Secure authentication with two-factor authentication",
            acceptance_criteria=acceptance_criteria,
            story_points=8,
            priority="High",
            components=components,
            labels=labels,
            epic_link="PROJ-100",
            assignee_suggestion="john.doe"
        )
        
        # Assert
        self.assertEqual(candidate.summary, "As a user, I want secure login with 2FA")
        self.assertEqual(candidate.description, "Secure authentication with two-factor authentication")
        self.assertEqual(candidate.acceptance_criteria, acceptance_criteria)
        self.assertEqual(candidate.story_points, 8)
        self.assertEqual(candidate.priority, "High")
        self.assertEqual(candidate.components, components)
        self.assertEqual(candidate.labels, labels)
        self.assertEqual(candidate.epic_link, "PROJ-100")
        self.assertEqual(candidate.assignee_suggestion, "john.doe")


class TestGenerateUserStoryResult(unittest.TestCase):
    """Test cases for GenerateUserStoryResult entity."""

    def test_create_with_minimal_data(self):
        """Test creating result with minimal required data."""
        # Arrange
        user_story = UserStoryCandidate(
            summary="As a user, I want to login",
            description="Simple login feature"
        )
        
        # Act
        result = GenerateUserStoryResult(user_story=user_story)
        
        # Assert
        self.assertEqual(result.user_story, user_story)
        self.assertIsNone(result.confidence_score)
        self.assertIsNone(result.reasoning)
        self.assertEqual(result.alternative_suggestions, [])
        self.assertIsNone(result.processing_metadata)

    def test_create_with_full_data(self):
        """Test creating result with all fields populated."""
        # Arrange
        main_story = UserStoryCandidate(
            summary="As a user, I want secure login",
            description="Secure authentication feature",
            story_points=5
        )
        
        alternative_story = UserStoryCandidate(
            summary="As a user, I want social login",
            description="Social media authentication",
            story_points=3
        )
        
        processing_metadata = {
            "model_used": "gpt-4",
            "processing_time": 1.5,
            "tokens_used": 150
        }
        
        # Act
        result = GenerateUserStoryResult(
            user_story=main_story,
            confidence_score=0.85,
            reasoning="High confidence based on clear requirements and standard patterns",
            alternative_suggestions=[alternative_story],
            processing_metadata=processing_metadata
        )
        
        # Assert
        self.assertEqual(result.user_story, main_story)
        self.assertEqual(result.confidence_score, 0.85)
        self.assertEqual(result.reasoning, "High confidence based on clear requirements and standard patterns")
        self.assertEqual(result.alternative_suggestions, [alternative_story])
        self.assertEqual(result.processing_metadata, processing_metadata)
