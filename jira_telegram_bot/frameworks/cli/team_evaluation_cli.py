"""Team evaluation CLI interface."""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import List, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.team_evaluation import TeamEvaluationScoreWeights
from jira_telegram_bot.settings.team_evaluation_settings import TeamEvaluationSettings
from jira_telegram_bot.use_cases.team_evaluation.run_team_evaluation_cli_use_case import RunTeamEvaluationCliUseCase
from jira_telegram_bot.use_cases.interfaces.calendar_repository_interface import CalendarRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.google_sheet_gateway_interface import GoogleSheetGatewayInterface
from jira_telegram_bot.use_cases.interfaces.leave_repository_interface import LeaveRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import TaskManagerRepositoryInterface
from jira_telegram_bot.use_cases.interfaces.user_config_interface import UserConfigInterface


class TeamEvaluationCLI:
    """Command-line interface for team evaluation functionality."""

    def __init__(self):
        """Initialize the CLI."""
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser.
        
        Returns:
            Configured argument parser
        """
        parser = argparse.ArgumentParser(
            description="Team Evaluation CLI - Compute developer metrics for sprint closure",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Compute evaluation for a specific sprint
  %(prog)s --sprint-id 123 --project-keys PROJ1,PROJ2 --sheet-id your_sheet_id

  # Use sprint name instead of ID
  %(prog)s --sprint-name "Sprint 47" --project-keys PARSCHAT --sheet-id your_sheet_id

  # Dry run mode (don't write to sheets)
  %(prog)s --sprint-id 123 --project-keys PROJ1 --sheet-id your_sheet_id --dry-run

  # Custom configuration
  %(prog)s --sprint-id 123 --project-keys PROJ1 --sheet-id your_sheet_id \\
           --weekly-hours 40 --workdays 1,2,3,4,5 --tab-name "My Evaluation"
            """
        )

        # Required arguments (one of sprint-id or sprint-name)
        sprint_group = parser.add_mutually_exclusive_group(required=True)
        sprint_group.add_argument(
            "--sprint-id",
            type=int,
            help="Jira sprint ID to compute metrics for"
        )
        sprint_group.add_argument(
            "--sprint-name",
            type=str,
            help="Jira sprint name to compute metrics for"
        )

        parser.add_argument(
            "--project-keys",
            type=str,
            required=True,
            help="Comma-separated list of Jira project keys (e.g., PROJ1,PROJ2)"
        )

        parser.add_argument(
            "--sheet-id",
            type=str,
            required=True,
            help="Google Sheet ID to write results to"
        )

        # Optional configuration
        parser.add_argument(
            "--tab-name",
            type=str,
            default="Team Evaluation",
            help="Target tab name in Google Sheet (default: Team Evaluation)"
        )

        parser.add_argument(
            "--weekly-hours",
            type=float,
            default=46.0,
            help="Expected weekly work hours (default: 46)"
        )

        parser.add_argument(
            "--workdays",
            type=str,
            default="6,0,1,2,3,5",
            help="Working days as comma-separated numbers (0=Monday, 6=Sunday, default: 6,0,1,2,3,4 for Sat-Thu)"
        )

        parser.add_argument(
            "--dept-inference",
            type=str,
            choices=["component", "label", "user_config"],
            default="component",
            help="Strategy for department detection (default: component)"
        )

        parser.add_argument(
            "--score-weights",
            type=str,
            default='{"deadline": 0.35, "worklog": 0.25, "high_priority": 0.20, "defects": 0.20}',
            help="JSON string for score weighting (default: balanced weights)"
        )

        parser.add_argument(
            "--defect-thresholds",
            type=str,
            default='{"support_per_story": 0.3, "tester_per_story": 0.4, "max_penalty": 60}',
            help="JSON string for defect penalty thresholds"
        )

        parser.add_argument(
            "--expected-hours-mode",
            type=str,
            choices=["weekly", "total"],
            default="weekly",
            help="Expected hours calculation mode (default: weekly)"
        )

        parser.add_argument(
            "--timezone",
            type=str,
            default="Asia/Tehran",
            help="IANA timezone for calculations (default: Asia/Tehran)"
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute metrics but don't write to Google Sheets"
        )

        parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Enable verbose logging"
        )

        return parser

    def _parse_workdays(self, workdays_str: str) -> tuple:
        """Parse workdays string to tuple.
        
        Args:
            workdays_str: Comma-separated workday numbers
            
        Returns:
            Tuple of workday integers
        """
        try:
            return tuple(int(d.strip()) for d in workdays_str.split(","))
        except ValueError as e:
            raise ValueError(f"Invalid workdays format '{workdays_str}': {e}")

    def _parse_json_arg(self, json_str: str, arg_name: str) -> dict:
        """Parse JSON argument string.
        
        Args:
            json_str: JSON string
            arg_name: Argument name for error messages
            
        Returns:
            Parsed dictionary
        """
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON for {arg_name}: {e}")

    def _create_settings_override(self, args: argparse.Namespace) -> dict:
        """Create settings override from CLI arguments.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Settings override dictionary
        """
        # Parse complex arguments
        workdays = self._parse_workdays(args.workdays)
        score_weights_dict = self._parse_json_arg(args.score_weights, "score-weights")
        defect_thresholds = self._parse_json_arg(args.defect_thresholds, "defect-thresholds")

        # Validate score weights
        try:
            score_weights = TeamEvaluationScoreWeights(**score_weights_dict)
        except Exception as e:
            raise ValueError(f"Invalid score weights: {e}")

        return {
            "sheet_id": args.sheet_id,
            "tab_name": args.tab_name,
            "weekly_hours": args.weekly_hours,
            "workdays": workdays,
            "expected_hours_mode": args.expected_hours_mode,
            "dept_inference": args.dept_inference,
            "timezone": args.timezone,
            "score_weights": score_weights,
            "defect_thresholds": defect_thresholds,
            "dry_run": args.dry_run
        }

    async def run(self, args: Optional[List[str]] = None) -> int:
        """Run the CLI with given arguments.
        
        Args:
            args: Command-line arguments (None for sys.argv)
            
        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            # Parse arguments
            parsed_args = self.parser.parse_args(args)

            if parsed_args.verbose:
                import logging
                logging.getLogger("jira_telegram_bot").setLevel(logging.DEBUG)

            LOGGER.info("🚀 Starting Team Evaluation CLI")

            # Create settings override
            settings_override = self._create_settings_override(parsed_args)

            # Override settings in container (temporarily)
            container = get_container()
            
            # Create custom settings instance
            original_settings = container[TeamEvaluationSettings]
            custom_settings = TeamEvaluationSettings(**settings_override)
            container[TeamEvaluationSettings] = lambda: custom_settings

            # Get use case with custom settings
            team_eval_use_case = RunTeamEvaluationCliUseCase(
                task_manager_repo=container[TaskManagerRepositoryInterface],
                user_config_service=container[UserConfigInterface],
                google_sheet_gateway=container[GoogleSheetGatewayInterface],
                calendar_repo=container[CalendarRepositoryInterface],
                leave_repo=container[LeaveRepositoryInterface],
                settings=custom_settings
            )

            # Parse project keys
            project_keys = [key.strip() for key in parsed_args.project_keys.split(",")]

            LOGGER.info(f"📊 Processing sprint: {parsed_args.sprint_name or parsed_args.sprint_id}")
            LOGGER.info(f"📋 Projects: {', '.join(project_keys)}")
            LOGGER.info(f"📄 Sheet: {settings_override['sheet_id']}")
            LOGGER.info(f"📝 Tab: {settings_override['tab_name']}")

            if settings_override['dry_run']:
                LOGGER.info("🧪 DRY RUN MODE - No data will be written")

            # Process the sprint via CLI use case
            await team_eval_use_case.run(
                sprint_id=parsed_args.sprint_id,
                sprint_name=parsed_args.sprint_name,
                project_keys=project_keys
            )

            LOGGER.info("✅ Team evaluation completed successfully!")
            return 0

        except KeyboardInterrupt:
            LOGGER.info("⚠️  Interrupted by user")
            return 1
        except Exception as e:
            LOGGER.error(f"❌ Error: {e}")
            if parsed_args.verbose if 'parsed_args' in locals() else False:
                import traceback
                traceback.print_exc()
            return 1

    def run_sync(self, args: Optional[List[str]] = None) -> int:
        """Synchronous wrapper for the async run method.
        
        Args:
            args: Command-line arguments
            
        Returns:
            Exit code
        """
        return asyncio.run(self.run(args))


def main():
    """Main entry point for the CLI."""
    cli = TeamEvaluationCLI()
    exit_code = cli.run_sync()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
