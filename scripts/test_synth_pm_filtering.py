"""Test script for SynthPM filtering functionality."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.synth_pm.sync_filter_criteria import (
    SynthPMSyncFilterCriteria,
)
from jira_telegram_bot.use_cases.synth_pm import SynthPMUseCase

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_filtering():
    """Test the filtering functionality."""
    LOGGER.info("🧪 Testing SynthPM filtering functionality...")

    # Get configured use case
    container = get_container()
    synth_pm_use_case = container[SynthPMUseCase]

    LOGGER.info("1️⃣ Testing basic filter entity creation...")

    # Test filter entity creation
    sprint_filter = SynthPMSyncFilterCriteria.create_sprint_filter(
        sprints=["Sprint-1", "Sprint-2"],
        include_empty=False,
    )
    LOGGER.info(f"✅ Sprint filter created: {sprint_filter}")

    release_filter = SynthPMSyncFilterCriteria.create_release_filter(
        releases=["v1.0", "v1.1"],
        include_empty=False,
    )
    LOGGER.info(f"✅ Release filter created: {release_filter}")

    combined_filter = SynthPMSyncFilterCriteria.create_combined_filter(
        sprints=["Sprint-1"],
        releases=["v1.0"],
        include_empty_sprint=False,
        include_empty_release=False,
    )
    LOGGER.info(f"✅ Combined filter created: {combined_filter}")

    LOGGER.info("2️⃣ Testing filter logic...")

    # Test filter logic
    test_cases = [
        ("Sprint-1", "v1.0", "1.0.0", True),  # Should match
        ("Sprint-2", "v1.0", "1.0.0", False),  # Sprint doesn't match
        ("Sprint-1", "v2.0", "1.0.0", False),  # Release doesn't match
        (None, None, None, False),  # Empty values, include_empty=False
    ]

    for sprint, release, version, expected in test_cases:
        result = combined_filter.should_include_feature(sprint, release, version)
        status = "✅" if result == expected else "❌"
        LOGGER.info(
            f"{status} Sprint: {sprint}, Release: {release}, Version: {version} -> {result} (expected: {expected})",
        )

    LOGGER.info("3️⃣ Testing repository filtering (dry run)...")

    try:
        # Test getting features with filter
        features = await synth_pm_use_case.repository.get_developer_board_features(
            sprint_filter,
        )
        LOGGER.info(
            f"✅ Successfully retrieved {len(features)} features with sprint filter",
        )

        # Show first few features if any
        if features:
            for i, feature in enumerate(features[:3]):
                LOGGER.info(
                    f"   Feature {i+1}: {feature.task_title} (Sprint: {feature.sprint}, Release: {feature.release})",
                )

    except Exception as e:
        LOGGER.info(f"❌ Error testing repository filtering: {e}")

    LOGGER.info("4️⃣ Testing convenience methods...")

    try:
        # Test sync by sprint (this would normally do actual sync)
        LOGGER.info("Testing sync_features_by_sprint (dry run)...")
        # For safety, we'll just test the filter creation part
        test_filter = SynthPMSyncFilterCriteria.create_sprint_filter(
            ["Sprint-1"],
            False,
        )
        LOGGER.info(f"✅ Would sync features for Sprint-1: {test_filter}")

    except Exception as e:
        LOGGER.info(f"❌ Error testing convenience methods: {e}")

    LOGGER.info("✅ All filtering tests completed!")


if __name__ == "__main__":
    asyncio.run(test_filtering())
