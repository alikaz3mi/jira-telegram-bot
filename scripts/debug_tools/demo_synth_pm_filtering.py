"""Example usage of SynthPM filtering in different scenarios."""
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


async def demo_filtering_scenarios():
    """Demonstrate different filtering scenarios."""
    LOGGER.info("🚀 SynthPM Filtering Demo")

    # Get configured use case
    container = get_container()
    synth_pm_use_case = container[SynthPMUseCase]

    LOGGER.info("📊 Scenario 1: Sync all features (baseline)")
    all_features = await synth_pm_use_case.repository.get_developer_board_features()
    LOGGER.info(f"   Total features in sheet: {len(all_features)}")

    LOGGER.info("📊 Scenario 2: Filter by non-existent sprint")
    sprint_filter = SynthPMSyncFilterCriteria.create_sprint_filter(["Sprint-99"], False)
    filtered_features = await synth_pm_use_case.repository.get_developer_board_features(
        sprint_filter,
    )
    LOGGER.info(f"   Features for Sprint-99: {len(filtered_features)}")

    LOGGER.info("📊 Scenario 3: Include features with empty sprint")
    empty_sprint_filter = SynthPMSyncFilterCriteria.create_sprint_filter(
        ["Sprint-1"],
        True,
    )
    empty_features = await synth_pm_use_case.repository.get_developer_board_features(
        empty_sprint_filter,
    )
    LOGGER.info(f"   Features for Sprint-1 + empty sprints: {len(empty_features)}")

    LOGGER.info("📊 Scenario 4: Filter by release version")
    version_filter = SynthPMSyncFilterCriteria.create_release_filter(
        versions=["1.0.0"],
        include_empty=True,
    )
    version_features = await synth_pm_use_case.repository.get_developer_board_features(
        version_filter,
    )
    LOGGER.info(
        f"   Features for version 1.0.0 + empty versions: {len(version_features)}",
    )

    LOGGER.info("📊 Scenario 5: Combined filtering")
    combined_filter = SynthPMSyncFilterCriteria.create_combined_filter(
        sprints=["Sprint-1", "Sprint-2"],
        releases=["v1.0"],
        include_empty_sprint=True,
        include_empty_release=True,
    )
    combined_features = await synth_pm_use_case.repository.get_developer_board_features(
        combined_filter,
    )
    LOGGER.info(f"   Features matching complex criteria: {len(combined_features)}")

    LOGGER.info("📈 Performance Impact Summary:")
    LOGGER.info(f"   • Baseline (all features): {len(all_features)}")
    LOGGER.info(
        f"   • Sprint filter: {len(filtered_features)} ({100*len(filtered_features)/len(all_features):.1f}% of total)",
    )
    LOGGER.info(
        f"   • Sprint + empty: {len(empty_features)} ({100*len(empty_features)/len(all_features):.1f}% of total)",
    )
    LOGGER.info(
        f"   • Version filter: {len(version_features)} ({100*len(version_features)/len(all_features):.1f}% of total)",
    )
    LOGGER.info(
        f"   • Combined filter: {len(combined_features)} ({100*len(combined_features)/len(all_features):.1f}% of total)",
    )

    LOGGER.info("🎯 Filtering Benefits:")
    LOGGER.info("   • Reduced network calls to Google Sheets")
    LOGGER.info("   • Faster processing with smaller datasets")
    LOGGER.info("   • Focused synchronization for specific sprints/releases")
    LOGGER.info("   • Better performance in CI/CD pipelines")

    LOGGER.info("💡 Usage Examples:")
    LOGGER.info("   # Sync only current sprint")
    LOGGER.info("   python scripts/run_synth_pm.py sync --sprints Sprint-5")
    LOGGER.info("")
    LOGGER.info("   # Sync specific release")
    LOGGER.info("   python scripts/run_synth_pm.py sync --versions 2.1.0")
    LOGGER.info("")
    LOGGER.info("   # Sync multiple sprints with empty features")
    LOGGER.info(
        "   python scripts/run_synth_pm.py sync --sprints Sprint-1 Sprint-2 --include-empty-sprint",
    )


if __name__ == "__main__":
    asyncio.run(demo_filtering_scenarios())
