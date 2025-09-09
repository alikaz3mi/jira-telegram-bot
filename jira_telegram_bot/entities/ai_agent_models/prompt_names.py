"""Central registry of all AI-agent prompt IDs."""

from __future__ import annotations

from enum import Enum


class PromptNames(str, Enum):
    """Central registry of all AI-agent prompt IDs."""
    
    # Existing prompts from current system
    GENERATE_PROGRESS_REPORT = "generate_progress_report"
    BOARD_SUMMARIZER = "board_summarizer"
    DECOMPOSE_USER_STORY = "decompose_user_story"
    CREATE_SUBTASKS = "create_subtasks"
    GENERATE_USER_STORY = "generate_user_story"
    
    # New SynthPM prompts for feature enhancement
    GENERATE_ACCEPTANCE_CRITERIA = "generate_acceptance_criteria"
    GENERATE_TEST_SCENARIOS = "generate_test_scenarios"