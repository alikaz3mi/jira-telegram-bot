"""Use case for updating Google Sheets with metric data."""

from datetime import datetime, date
from typing import Dict, Any, Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.metrics.metric_event import MetricEvent
from jira_telegram_bot.entities.metrics.constants import MetricType, SheetName
from jira_telegram_bot.entities.metrics.daily_metric_row import DailyMetricRow
from jira_telegram_bot.entities.metrics.sprint_metric_row import SprintMetricRow
from jira_telegram_bot.use_cases.interfaces.metrics.spreadsheet_gateway_interface import SpreadsheetGatewayInterface
from jira_telegram_bot.use_cases.interfaces.metrics.user_setting_configuration_repository_interface import UserSettingConfigurationRepositoryInterface
from jira_telegram_bot.utils.retry_decorator import retry_async


class UpdateSheetUseCase:
    """Use case for updating Google Sheets with metric data."""
    
    def __init__(
        self,
        spreadsheet_gateway: SpreadsheetGatewayInterface,
        user_config_repository: UserSettingConfigurationRepositoryInterface
    ):
        """Initialize the use case.
        
        Args:
            spreadsheet_gateway: Gateway for Google Sheets operations
            user_config_repository: Repository for user/project configuration
        """
        self.spreadsheet_gateway = spreadsheet_gateway
        self.user_config_repository = user_config_repository
    
    @retry_async(exceptions=(Exception,), tries=5, backoff=2)
    async def update_daily_scoreboard(self, event: MetricEvent) -> bool:
        """Update daily scoreboard sheet with metric data.
        
        Args:
            event: Metric event to process
            
        Returns:
            True if update was successful, False otherwise
        """
        LOGGER.debug(f"Updating daily scoreboard for event: {event.event_id}")
        
        try:
            # Get sheet configuration
            sheet_config = await self.user_config_repository.get_sheet_configuration(
                SheetName.DAILY_SCOREBOARD
            )
            if not sheet_config:
                LOGGER.error("Daily scoreboard sheet configuration not found")
                return False
            
            # Get developer mapping
            developer_mapping = await self.user_config_repository.get_developer_sheet_mapping(
                event.developer_key
            )
            if not developer_mapping:
                LOGGER.warning(f"No sheet mapping found for developer: {event.developer_key}")
                return False
            
            # Get current sheet data
            sheet_id = sheet_config["sheet_id"]
            range_name = sheet_config["range_template"]
            current_data = await self.spreadsheet_gateway.get_sheet_values(sheet_id, range_name)
            
            # Find or create row for developer and date
            event_date = event.timestamp.date()
            row_index = self._find_daily_row_index(
                current_data, 
                developer_mapping["display_name"], 
                event_date
            )
            
            if row_index is None:
                # Create new row
                new_row = self._create_daily_row(event, developer_mapping["display_name"])
                return await self._append_daily_row(sheet_id, range_name, new_row)
            else:
                # Update existing row
                return await self._update_daily_row(
                    sheet_id, range_name, row_index, event, current_data
                )
                
        except Exception as e:
            LOGGER.error(f"Error updating daily scoreboard: {e}")
            return False
    
    @retry_async(exceptions=(Exception,), tries=5, backoff=2)
    async def update_sprint_matrix(self, event: MetricEvent) -> bool:
        """Update sprint metrics matrix with metric data.
        
        Args:
            event: Metric event to process
            
        Returns:
            True if update was successful, False otherwise
        """
        LOGGER.debug(f"Updating sprint matrix for event: {event.event_id}")
        
        if not event.sprint_id:
            LOGGER.debug("No sprint ID in event, skipping sprint matrix update")
            return True
        
        try:
            # Get sheet configuration
            sheet_config = await self.user_config_repository.get_sheet_configuration(
                SheetName.DEVELOPER_METRICS_MATRIX
            )
            if not sheet_config:
                LOGGER.error("Sprint matrix sheet configuration not found")
                return False
            
            # Get developer mapping
            developer_mapping = await self.user_config_repository.get_developer_sheet_mapping(
                event.developer_key
            )
            if not developer_mapping:
                LOGGER.warning(f"No sheet mapping found for developer: {event.developer_key}")
                return False
            
            # Get current sheet data
            sheet_id = sheet_config["sheet_id"]
            range_name = sheet_config["range_template"]
            current_data = await self.spreadsheet_gateway.get_sheet_values(sheet_id, range_name)
            
            # Find or create row for developer
            row_index = self._find_sprint_row_index(
                current_data, 
                developer_mapping["display_name"]
            )
            
            if row_index is None:
                # Create new row
                new_row = self._create_sprint_row(event, developer_mapping["display_name"])
                return await self._append_sprint_row(sheet_id, range_name, new_row)
            else:
                # Update existing row
                return await self._update_sprint_row(
                    sheet_id, range_name, row_index, event, current_data
                )
                
        except Exception as e:
            LOGGER.error(f"Error updating sprint matrix: {e}")
            return False
    
    def _find_daily_row_index(
        self, 
        sheet_data: list[list[Any]], 
        developer_name: str, 
        target_date: date
    ) -> Optional[int]:
        """Find the row index for a developer and date in daily scoreboard.
        
        Args:
            sheet_data: Current sheet data
            developer_name: Developer display name
            target_date: Date to find
            
        Returns:
            Row index (0-based) or None if not found
        """
        for i, row in enumerate(sheet_data):
            if len(row) >= 2:
                row_developer = row[0] if row else ""
                row_date_str = row[1] if len(row) > 1 else ""
                
                if row_developer == developer_name:
                    try:
                        # Parse date from various formats
                        row_date = datetime.strptime(row_date_str, "%Y-%m-%d").date()
                        if row_date == target_date:
                            return i
                    except (ValueError, AttributeError):
                        continue
        
        return None
    
    def _find_sprint_row_index(
        self, 
        sheet_data: list[list[Any]], 
        developer_name: str
    ) -> Optional[int]:
        """Find the row index for a developer in sprint matrix.
        
        Args:
            sheet_data: Current sheet data
            developer_name: Developer display name
            
        Returns:
            Row index (0-based) or None if not found
        """
        for i, row in enumerate(sheet_data):
            if row and row[0] == developer_name:
                return i
        
        return None
    
    def _create_daily_row(self, event: MetricEvent, developer_name: str) -> list[Any]:
        """Create a new daily metrics row.
        
        Args:
            event: Metric event
            developer_name: Developer display name
            
        Returns:
            List representing the row data
        """
        daily_row = DailyMetricRow(
            developer_name=developer_name,
            metric_date=event.timestamp.date(),
            today_deadlines=1 if event.metric_type in [MetricType.DEADLINE_HIT, MetricType.DEADLINE_MISSED] else 0,
            resolved_tasks=1 if event.metric_type == MetricType.TASK_RESOLVED else 0,
            logged_time=event.value if event.metric_type == MetricType.TIME_LOGGED else 0.0,
            commits=1 if event.metric_type == MetricType.COMMIT_MADE else 0,
            comments=event.metadata.get("commit_message") or event.metadata.get("summary")
        )
        
        return [
            daily_row.developer_name,
            daily_row.metric_date.strftime("%Y-%m-%d"),
            daily_row.today_deadlines,
            daily_row.resolved_tasks,
            daily_row.logged_time,
            daily_row.commits,
            daily_row.comments or ""
        ]
    
    def _create_sprint_row(self, event: MetricEvent, developer_name: str) -> list[Any]:
        """Create a new sprint metrics row.
        
        Args:
            event: Metric event
            developer_name: Developer display name
            
        Returns:
            List representing the row data
        """
        sprint_row = SprintMetricRow(
            developer_name=developer_name,
            all_tasks=1 if event.metric_type == MetricType.TASK_CREATED else 0,
            completed_tasks=1 if event.metric_type == MetricType.TASK_RESOLVED else 0,
            resolved_stories=1 if event.metric_type == MetricType.TASK_RESOLVED and event.metadata.get("issue_type") == "Story" else 0,
            resolved_bugs=1 if event.metric_type == MetricType.TASK_RESOLVED and event.metadata.get("issue_type") == "Bug" else 0,
            logged_time=event.value if event.metric_type == MetricType.TIME_LOGGED else 0.0,
            merge_requests=1 if event.metric_type == MetricType.MERGE_REQUEST_OPENED else 0,
            successful_merges=1 if event.metric_type == MetricType.MERGE_REQUEST_MERGED else 0
        )
        
        return [
            sprint_row.developer_name,
            sprint_row.all_tasks,
            sprint_row.completed_tasks,
            sprint_row.releases_related_to_person,
            sprint_row.stories_related_to_person,
            sprint_row.resolved_stories,
            sprint_row.resolved_bugs,
            sprint_row.delivery_delay_by_day,
            sprint_row.bug_delivery_delay_by_day,
            sprint_row.logged_time,
            sprint_row.eta_completing_all_tasks,
            sprint_row.logged_time_support_epic,
            sprint_row.logged_meeting,
            sprint_row.documentatio_merge_requests,
            sprint_row.merge_requests,
            sprint_row.successful_merges
        ]
    
    async def _append_daily_row(self, sheet_id: str, range_name: str, row_data: list[Any]) -> bool:
        """Append a new daily row to the sheet.
        
        Args:
            sheet_id: Google Sheet ID
            range_name: Range to append to
            row_data: Row data to append
            
        Returns:
            True if successful, False otherwise
        """
        return await self.spreadsheet_gateway.append_rows(sheet_id, range_name, [row_data])
    
    async def _append_sprint_row(self, sheet_id: str, range_name: str, row_data: list[Any]) -> bool:
        """Append a new sprint row to the sheet.
        
        Args:
            sheet_id: Google Sheet ID
            range_name: Range to append to
            row_data: Row data to append
            
        Returns:
            True if successful, False otherwise
        """
        return await self.spreadsheet_gateway.append_rows(sheet_id, range_name, [row_data])
    
    async def _update_daily_row(
        self, 
        sheet_id: str, 
        range_name: str, 
        row_index: int, 
        event: MetricEvent, 
        current_data: list[list[Any]]
    ) -> bool:
        """Update an existing daily row with new metric data.
        
        Args:
            sheet_id: Google Sheet ID
            range_name: Range containing the row
            row_index: Index of the row to update
            event: Metric event with new data
            current_data: Current sheet data
            
        Returns:
            True if successful, False otherwise
        """
        if row_index >= len(current_data):
            return False
        
        current_row = current_data[row_index]
        
        # Update the row based on metric type
        updated_row = current_row[:]
        
        if event.metric_type in [MetricType.DEADLINE_HIT, MetricType.DEADLINE_MISSED]:
            updated_row[2] = int(updated_row[2] or 0) + 1  # today_deadlines
        elif event.metric_type == MetricType.TASK_RESOLVED:
            updated_row[3] = int(updated_row[3] or 0) + 1  # resolved_tasks
        elif event.metric_type == MetricType.TIME_LOGGED:
            updated_row[4] = float(updated_row[4] or 0) + event.value  # logged_time
        elif event.metric_type == MetricType.COMMIT_MADE:
            updated_row[5] = int(updated_row[5] or 0) + 1  # commits
            # Update comments with latest commit message
            if event.metadata.get("commit_message"):
                updated_row[6] = event.metadata["commit_message"]
        
        # Update the specific cell range
        cell_range = f"A{row_index + 1}:G{row_index + 1}"
        return await self.spreadsheet_gateway.update_cells(sheet_id, cell_range, [updated_row])
    
    async def _update_sprint_row(
        self, 
        sheet_id: str, 
        range_name: str, 
        row_index: int, 
        event: MetricEvent, 
        current_data: list[list[Any]]
    ) -> bool:
        """Update an existing sprint row with new metric data.
        
        Args:
            sheet_id: Google Sheet ID
            range_name: Range containing the row
            row_index: Index of the row to update
            event: Metric event with new data
            current_data: Current sheet data
            
        Returns:
            True if successful, False otherwise
        """
        if row_index >= len(current_data):
            return False
        
        current_row = current_data[row_index]
        updated_row = current_row[:]
        
        # Update the row based on metric type
        if event.metric_type == MetricType.TASK_CREATED:
            updated_row[1] = int(updated_row[1] or 0) + 1  # all_tasks
        elif event.metric_type == MetricType.TASK_RESOLVED:
            updated_row[2] = int(updated_row[2] or 0) + 1  # completed_tasks
            
            # Update specific counters based on issue type
            issue_type = event.metadata.get("issue_type", "")
            if issue_type == "Story":
                updated_row[5] = int(updated_row[5] or 0) + 1  # resolved_stories
            elif issue_type == "Bug":
                updated_row[6] = int(updated_row[6] or 0) + 1  # resolved_bugs
                
        elif event.metric_type == MetricType.TIME_LOGGED:
            updated_row[9] = float(updated_row[9] or 0) + event.value  # logged_time
        elif event.metric_type == MetricType.MERGE_REQUEST_OPENED:
            updated_row[14] = int(updated_row[14] or 0) + 1  # merge_requests
        elif event.metric_type == MetricType.MERGE_REQUEST_MERGED:
            updated_row[15] = int(updated_row[15] or 0) + 1  # successful_merges
        
        # Update the specific cell range
        cell_range = f"A{row_index + 1}:P{row_index + 1}"
        return await self.spreadsheet_gateway.update_cells(sheet_id, cell_range, [updated_row])
