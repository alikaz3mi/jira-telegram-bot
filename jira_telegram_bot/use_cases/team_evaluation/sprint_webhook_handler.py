"""Sprint webhook handler for team evaluation."""

from datetime import datetime
from typing import Dict, Any, List

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.team_evaluation import SprintClosedEvent
from jira_telegram_bot.use_cases.team_evaluation.sprint_closed_team_evaluation_use_case import SprintClosedTeamEvaluationUseCase


class SprintWebhookHandler:
    """Handler for sprint-related webhooks."""

    def __init__(self, team_evaluation_use_case: SprintClosedTeamEvaluationUseCase):
        """Initialize the handler.
        
        Args:
            team_evaluation_use_case: Team evaluation use case
        """
        self.team_evaluation_use_case = team_evaluation_use_case

    async def handle_sprint_event(self, webhook_payload: Dict[str, Any]) -> None:
        """Handle sprint webhook events.
        
        Args:
            webhook_payload: Raw webhook payload from Jira
        """
        try:
            # Extract event type
            event_type = webhook_payload.get("webhookEvent", "")
            
            if event_type == "sprint_closed":
                await self._handle_sprint_closed(webhook_payload)
            else:
                LOGGER.debug(f"Ignoring sprint event type: {event_type}")
                
        except Exception as e:
            LOGGER.error(f"Error handling sprint webhook: {e}")
            raise

    async def _handle_sprint_closed(self, payload: Dict[str, Any]) -> None:
        """Handle sprint closed event.
        
        Args:
            payload: Webhook payload
        """
        try:
            # Extract sprint information from payload
            sprint_data = payload.get("sprint", {})
            
            if not sprint_data:
                LOGGER.error("No sprint data in webhook payload")
                return
            
            # Build sprint closed event
            event = SprintClosedEvent(
                sprint_id=sprint_data.get("id"),
                sprint_name=sprint_data.get("name", ""),
                project_keys=self._extract_project_keys(payload),
                ended_at=self._parse_end_date(sprint_data.get("endDate"))
            )
            
            LOGGER.info(f"Received sprint closed event: {event.sprint_name} (ID: {event.sprint_id})")
            
            # Process the event
            await self.team_evaluation_use_case.process_sprint_closed(event)
            
        except Exception as e:
            LOGGER.error(f"Error processing sprint closed event: {e}")
            raise

    def _extract_project_keys(self, payload: Dict[str, Any]) -> List[str]:
        """Extract project keys from webhook payload.
        
        Args:
            payload: Webhook payload
            
        Returns:
            List of project keys
        """
        project_keys = []
        
        # Try to get from various payload locations
        if "project" in payload:
            project_keys.append(payload["project"].get("key", ""))
        
        # If no project keys found, try to extract from sprint board info
        sprint_data = payload.get("sprint", {})
        if "originBoardId" in sprint_data:
            # Would need to query Jira to get projects for this board
            # For now, log and continue
            LOGGER.warning("Need to query Jira for project keys from board ID")
        
        # Filter out empty keys
        project_keys = [key for key in project_keys if key]
        
        if not project_keys:
            LOGGER.warning("No project keys found in sprint webhook payload")
        
        return project_keys

    def _parse_end_date(self, end_date_str: str) -> datetime:
        """Parse end date from webhook payload.
        
        Args:
            end_date_str: End date string
            
        Returns:
            Parsed datetime
        """
        if not end_date_str:
            return datetime.now()
        
        try:
            # Handle various Jira date formats
            # ISO format: 2024-03-15T23:59:59.000Z
            if "T" in end_date_str:
                return datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            
            # Date only: 2024-03-15
            return datetime.strptime(end_date_str, "%Y-%m-%d")
            
        except ValueError as e:
            LOGGER.warning(f"Could not parse end date '{end_date_str}': {e}")
            return datetime.now()
