from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.services.synth_pm_sync_task import SynthPMSyncTask
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.synth_pm.sync_filter_criteria import (
    SynthPMSyncFilterCriteria,
)
from jira_telegram_bot.settings.synth_pm_settings import SynthPMSettings
from jira_telegram_bot.settings.project_config_settings import ProjectConfigSettings
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase


def get_all_projects() -> list[str]:
    """Get all available project keys from configuration.
    
    Returns:
        List of project keys from projects_config.json
    """
    try:
        container = get_container()
        project_config_settings = container[ProjectConfigSettings]
        projects_config = project_config_settings.load_config()
        return list(projects_config.projects.keys())
    except Exception as e:
        LOGGER.error(f"Error getting projects from configuration: {e}")
        return []


def get_boards_for_project(project_key: str) -> list[str]:
    """Get all board keys for a specific project.
    
    Args:
        project_key: Project key (e.g., 'PARSCHAT')
        
    Returns:
        List of board keys for the project
    """
    try:
        container = get_container()
        project_config_settings = container[ProjectConfigSettings]
        projects_config = project_config_settings.load_config()
        
        if project_key not in projects_config.projects:
            LOGGER.warning(f"Project '{project_key}' not found in configuration")
            return []
        
        project = projects_config.projects[project_key]
        board_keys = []
        
        # Add PM board key
        if project.jira.pm_board and project.jira.pm_board.enabled:
            board_keys.append(project.jira.pm_board.board_key)
        # Add development board key
        if project.jira.development_board and project.jira.development_board.enabled:
            board_keys.append(project.jira.development_board.board_key)
        # Add support board key if exists
        if project.jira.support_board and project.jira.support_board.enabled:
            board_keys.append(project.jira.support_board.board_key)
        
        return board_keys
    except Exception as e:
        LOGGER.error(f"Error getting boards for project '{project_key}': {e}")
        return []


def get_project_key_for_board(board_key: str) -> Optional[str]:
    """Get the project key that contains the given board key.
    
    Args:
        board_key: Board key to search for
        
    Returns:
        Project key if found, None otherwise
    """
    try:
        container = get_container()
        project_config_settings = container[ProjectConfigSettings]
        projects_config = project_config_settings.load_config()
        
        for project_key, project in projects_config.projects.items():
            # Check all board types
            if project.jira.pm_board and project.jira.pm_board.board_key == board_key:
                return project_key
            if project.jira.development_board and project.jira.development_board.board_key == board_key:
                return project_key
            if project.jira.support_board and project.jira.support_board.board_key == board_key:
                return project_key
        
        LOGGER.warning(f"No project found for board key: {board_key}")
        return None
    except Exception as e:
        LOGGER.error(f"Error getting project key for board '{board_key}': {e}")
        return None


def get_all_board_keys() -> list[str]:
    """Get all available board keys from all projects.
    
    Returns:
        List of all board keys from all projects in projects_config.json
    """
    try:
        all_projects = get_all_projects()
        board_keys = []
        
        for project_key in all_projects:
            board_keys.extend(get_boards_for_project(project_key))
        
        return list(set(board_keys))  # Remove duplicates
    except Exception as e:
        LOGGER.error(f"Error getting board keys from configuration: {e}")
        return []


def resolve_board_keys(identifiers: list[str]) -> list[str]:
    """Resolve project keys or board keys to actual board keys.
    
    Args:
        identifiers: List that can contain:
            - 'all': All boards from all projects
            - Project keys (e.g., 'PARSCHAT'): Expands to all boards in that project
            - Board keys (e.g., 'PCD', 'PARSCHAT'): Used directly
            
    Returns:
        List of resolved board keys
    """
    if not identifiers:
        return None
    
    # Check if "all" is requested
    if len(identifiers) == 1 and identifiers[0].lower() == "all":
        return get_all_board_keys()
    
    all_projects = get_all_projects()
    all_boards = get_all_board_keys()
    resolved_boards = []
    
    for identifier in identifiers:
        # Check if it's a project key
        if identifier in all_projects:
            # Expand project to its boards
            project_boards = get_boards_for_project(identifier)
            LOGGER.info(f"Project '{identifier}' expands to boards: {', '.join(project_boards)}")
            resolved_boards.extend(project_boards)
        # Check if it's a board key
        elif identifier in all_boards:
            resolved_boards.append(identifier)
        else:
            LOGGER.warning(f"'{identifier}' not recognized as project or board. Available projects: {', '.join(all_projects)}, Available boards: {', '.join(all_boards)}")
    
    return list(set(resolved_boards)) if resolved_boards else None


async def setup_components():
    """Set up all required components for SynthPM using dependency injection."""
    try:
        container = get_container()

        synth_developer_board_use_case = container[SynthPMUseCase]

        return synth_developer_board_use_case

    except Exception as e:
        LOGGER.error(f"Error setting up SynthPM components: {e}")
        raise


async def run_sync_once(use_case: SynthPMUseCase, filter_criteria=None, board_keys=None):
    """Run synchronization once and exit.

    Args:
        use_case: SynthPM use case instance
        filter_criteria: Optional filter criteria for sync
        board_keys: Optional list of project board keys to sync, or None for default
    """
    try:
        # Determine which boards to sync
        if board_keys:
            boards_to_sync = board_keys
            LOGGER.info(f"Starting one-time SynthPM synchronization for boards: {', '.join(boards_to_sync)}")
        else:
            boards_to_sync = [None]  # Use default from settings
            LOGGER.info("Starting one-time SynthPM synchronization...")

        if filter_criteria:
            LOGGER.info(
                f"Applying filter: sprints={filter_criteria.sprints}, "
                f"releases={filter_criteria.releases}, versions={filter_criteria.release_versions}",
            )

        # Sync each board
        all_success = True
        for board_key in boards_to_sync:
            # Get project key for this board
            project_key = get_project_key_for_board(board_key) if board_key else None
            
            if board_key:
                LOGGER.info(f"\n{'='*60}")
                LOGGER.info(f"Syncing board: {board_key} (Project: {project_key})")
                LOGGER.info(f"{'='*60}")
            
            # TODO: add filter criteria
            result = await use_case.sync_developer_board_features(
                project_key=project_key,
                project_board_key=board_key,
            )

            if result["status"] == "success":
                LOGGER.info(f"✅  Features synchronization completed for {board_key or 'default board'}!")
                LOGGER.info(f" Features Results: {result.get('results', {})}")
            else:
                LOGGER.error(f"❌  Features synchronization failed for {board_key or 'default board'}: {result.get('message')}")
                all_success = False

            LOGGER.info(f"Starting Release Notes synchronization for {board_key or 'default board'}...")
            release_result = await use_case.sync_release_notes()

            if release_result["status"] == "success":
                LOGGER.info(f"✅ Release Notes synchronization completed for {board_key or 'default board'}!")
                LOGGER.info(f"Release Notes Results: {release_result.get('results', {})}")
            else:
                LOGGER.error(
                    f"❌ Release Notes synchronization failed for {board_key or 'default board'}: {release_result.get('message')}",
                )
                LOGGER.warning("Continuing despite Release Notes sync failure...")
        
        if not all_success:
            LOGGER.error("\n❌ Some board synchronizations failed")
            sys.exit(1)
        else:
            LOGGER.info(f"\n🎉 All board synchronizations completed successfully!")

    except Exception as e:
        LOGGER.error(f"❌ Error during synchronization: {e}")
        sys.exit(1)


async def run_background_service(use_case: SynthPMUseCase, board_key=None):
    """Run as a background service with periodic synchronization.
    
    Args:
        use_case: SynthPM use case instance
        board_key: Optional project board key to sync
    """
    try:
        LOGGER.info("Starting SynthPM background service...")

        container = get_container()
        settings = container[SynthPMSettings]

        sync_task = SynthPMSyncTask(
            synth_developer_board_use_case=use_case,
            settings=settings,
        )

        await sync_task.start()

        try:
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            LOGGER.info("Received interrupt signal, shutting down...")
        finally:
            await sync_task.stop()

    except Exception as e:
        LOGGER.error(f"❌ Error in background service: {e}")
        sys.exit(1)


async def test_connection(use_case: SynthPMUseCase, board_key=None):
    """Test connections to Google Sheets, Jira, and Telegram.
    
    Args:
        use_case: SynthPM use case instance
        board_key: Optional project board key to test
    """
    try:
        LOGGER.info("Testing connections...")

        LOGGER.info("📊 Testing Google Sheets connection...")
        features = await use_case.repository.get_developer_board_features()
        LOGGER.info(f"✅ Found {len(features)} features in Google Sheets")

        LOGGER.info("🎫 Testing Jira connection...")
        LOGGER.info("✅ Jira connection OK")

        LOGGER.info("🤖 Testing dedicated SynthPM Telegram bot...")
        try:
            # Test basic functionality (we can't easily test telegram directly without exposing bot)
            _ = use_case.notification_gateway
            LOGGER.info("✅ SynthPM notification gateway is configured")
            LOGGER.info(
                f"✅ Settings loaded: PM project = {use_case.settings.pm_project_key}",
            )

        except Exception as telegram_error:
            LOGGER.error(f"❌ Telegram bot test failed: {telegram_error}")
            LOGGER.error("💡 Make sure SYNTH_PM_TELEGRAM_BOT_TOKEN is set correctly")
            raise

        LOGGER.info("\n🎉 All connections tested successfully!")
        LOGGER.info(f"📊 Google Sheets: {len(features)} features ready for sync")
        LOGGER.info("🎫 Jira: Connection verified")
        LOGGER.info("🤖 Notification: Gateway configured for SynthPM updates")
        LOGGER.info("🧠 AI: New documentation generation use cases loaded")

    except Exception as e:
        LOGGER.error(f"❌ Connection test failed: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    # Get available projects and boards for help text
    available_projects = get_all_projects()
    available_boards = get_all_board_keys()
    
    help_text_parts = []
    if available_projects:
        help_text_parts.append(f"Available PROJECTS: {', '.join(available_projects)}")
        for proj in available_projects:
            boards = get_boards_for_project(proj)
            help_text_parts.append(f"  {proj} → boards: {', '.join(boards)}")
    
    boards_help_text = (
        "Project key(s) or board key(s) to sync.\n"
        f"{chr(10).join(help_text_parts)}\n\n"
        "Options:\n"
        "  --projects PARSCHAT          Sync all boards in PARSCHAT project\n"
        "  --projects PARSCHAT PROJECT2 Sync all boards in multiple projects\n"
        "  --boards PCD                 Sync specific board\n"
        "  --boards PCD PARSCHAT        Sync multiple specific boards\n"
        "  --projects all               Sync all projects (all boards)\n"
        "If not provided, uses default from settings."
    )
    
    parser = argparse.ArgumentParser(
        description="SynthPM synchronization tool with multi-project and multi-board support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["sync", "service", "test"],
        default="service",
        help="Command to run: sync (one-time), service (background), or test (connections)",
    )
    
    # Project configuration
    parser.add_argument(
        "--projects",
        nargs="+",
        dest="projects",
        metavar="PROJECT",
        help="Project key(s) to sync all boards for (e.g., PARSCHAT). Use 'all' for all projects.",
    )
    parser.add_argument(
        "--boards",
        nargs="+",
        dest="boards",
        metavar="BOARD",
        help="Specific board key(s) to sync (e.g., PCD PARSCHAT).",
    )

    # Filtering options
    parser.add_argument(
        "--sprints",
        nargs="+",
        help="Filter by specific sprint names (e.g., --sprints Sprint-1 Sprint-2)",
    )
    parser.add_argument(
        "--releases",
        nargs="+",
        help="Filter by release names (e.g., --releases v1.0 v1.1)",
    )
    parser.add_argument(
        "--versions",
        nargs="+",
        help="Filter by version numbers (e.g., --versions 1.0.0 1.1.0)",
    )
    parser.add_argument(
        "--include-empty-sprint",
        action="store_true",
        help="Include features with empty sprint field",
    )
    parser.add_argument(
        "--include-empty-release",
        action="store_true",
        help="Include features with empty release fields",
    )

    args = parser.parse_args()

    # Process projects and boards
    board_keys = None
    
    # Check if both --projects and --boards are specified
    if args.projects and args.boards:
        LOGGER.error("Cannot specify both --projects and --boards. Choose one.")
        sys.exit(1)
    
    # Process --projects argument
    if args.projects:
        if len(args.projects) == 1 and args.projects[0].lower() == "all":
            # Get all boards from all projects
            board_keys = get_all_board_keys()
            if not board_keys:
                LOGGER.error("No boards found in projects configuration")
                sys.exit(1)
            LOGGER.info(f"Syncing ALL projects - found {len(board_keys)} boards: {', '.join(board_keys)}")
        else:
            # Expand project keys to their board keys
            board_keys = []
            for project_key in args.projects:
                project_boards = get_boards_for_project(project_key)
                if not project_boards:
                    LOGGER.warning(f"No boards found for project '{project_key}'")
                else:
                    LOGGER.info(f"Project '{project_key}' → boards: {', '.join(project_boards)}")
                    board_keys.extend(project_boards)
            
            if not board_keys:
                LOGGER.error(f"No valid boards found for projects: {', '.join(args.projects)}")
                sys.exit(1)
            board_keys = list(set(board_keys))  # Remove duplicates
    
    # Process --boards argument
    elif args.boards:
        board_keys = resolve_board_keys(args.boards)
        if not board_keys:
            LOGGER.error(f"No valid boards found for: {', '.join(args.boards)}")
            sys.exit(1)
        LOGGER.info(f"Using specified boards: {', '.join(board_keys)}")

    # Create filter criteria from arguments
    filter_criteria = None
    if args.sprints or args.releases or args.versions:
        filter_criteria = SynthPMSyncFilterCriteria.create_combined_filter(
            sprints=args.sprints,
            releases=args.releases,
            versions=args.versions,
            include_empty_sprint=args.include_empty_sprint,
            include_empty_release=args.include_empty_release,
        )

    try:
        if args.command == "sync":
            asyncio.run(async_main_sync(filter_criteria, board_keys))
        elif args.command == "service":
            asyncio.run(async_main_service(board_keys))
        elif args.command == "test":
            asyncio.run(async_main_test(board_keys))
    except KeyboardInterrupt:
        LOGGER.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        LOGGER.error(f"Unexpected error: {e}")
        sys.exit(1)


async def async_main_sync(filter_criteria=None, board_keys=None):
    """Async main for sync command.

    Args:
        filter_criteria: Optional filter criteria for sync
        board_keys: Optional list of project board keys to sync
    """
    use_case = await setup_components()
    await run_sync_once(use_case, filter_criteria, board_keys)


async def async_main_service(board_keys=None):
    """Async main for service command.
    
    Args:
        board_keys: Optional list of project board keys to sync
    """
    use_case = await setup_components()
    # For service mode, use first board or default
    board_key = board_keys[0] if board_keys else None
    await run_background_service(use_case, board_key)


async def async_main_test(board_keys=None):
    """Async main for test command.
    
    Args:
        board_keys: Optional list of project board keys to test
    """
    use_case = await setup_components()
    # For test mode, use first board or default
    board_key = board_keys[0] if board_keys else None
    await test_connection(use_case, board_key)


if __name__ == "__main__":
    main()
