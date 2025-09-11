"""API endpoint for SynthPM operations."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.api_schemas import WebhookResponse
from jira_telegram_bot.frameworks.api.base_endpoint import ServiceAPIEndpointBluePrint
from jira_telegram_bot.use_cases.synth_pm import SynthPMUseCase


class SynthPMEndpoint(ServiceAPIEndpointBluePrint):
    """API endpoint for SynthPM operations."""

    def __init__(self, synth_developer_board_use_case: SynthPMUseCase):
        """Initialize the endpoint.

        Args:
            synth_developer_board_use_case: Use case for SynthPM operations
        """
        self.synth_developer_board_use_case = synth_developer_board_use_case
        super().__init__()

    def create_rest_api_route(self) -> APIRouter:
        """Create and configure the API router for SynthPM.

        Returns:
            Configured APIRouter for SynthPM endpoints
        """
        api_route = APIRouter(
            prefix="/synth-developer-board",
            tags=["SynthPM"],
        )

        @api_route.post(
            "/sync",
            summary="Synchronize PM features",
            description="Synchronize PM features between Google Sheets, Jira, and Telegram",
            response_model=WebhookResponse,
        )
        async def sync_developer_board_features():
            """Synchronize PM features."""
            try:
                result = (
                    await self.synth_developer_board_use_case.sync_developer_board_features()
                )
                return JSONResponse(content=result)

            except Exception as e:
                LOGGER.error(f"Error syncing PM features: {str(e)}", exc_info=True)
                return JSONResponse(
                    content=WebhookResponse(
                        status="error",
                        message=f"Sync error: {str(e)}",
                    ).model_dump(),
                    status_code=500,
                )

        @api_route.post(
            "/jira-webhook",
            summary="Handle Jira webhook for PM features",
            description="Process Jira webhook events for PM feature updates",
            response_model=WebhookResponse,
        )
        async def jira_webhook(request: Request):
            """Handle Jira webhook events for PM features."""
            try:
                webhook_data = await request.json()
                LOGGER.debug(f"Received Jira webhook for PM: {webhook_data}")

                result = await self.synth_developer_board_use_case.handle_jira_webhook(
                    webhook_data,
                )
                return JSONResponse(content=result)

            except Exception as e:
                LOGGER.error(f"Error handling Jira webhook: {str(e)}", exc_info=True)
                return JSONResponse(
                    content=WebhookResponse(
                        status="error",
                        message=f"Webhook error: {str(e)}",
                    ).model_dump(),
                    status_code=500,
                )

        @api_route.post(
            "/sheet-update",
            summary="Handle Google Sheets update",
            description="Process manual updates to Google Sheets",
            response_model=WebhookResponse,
        )
        async def sheet_update(request: Request):
            """Handle Google Sheets update events."""
            try:
                update_data = await request.json()
                LOGGER.debug(f"Received sheet update: {update_data}")

                # Extract row number and updates from request
                row_number = update_data.get("row_number")
                updates = update_data.get("updates", {})

                if not row_number:
                    raise HTTPException(
                        status_code=400,
                        detail="Row number is required",
                    )

                result = await self.synth_developer_board_use_case.handle_sheet_update(
                    row_number,
                    updates,
                )
                return JSONResponse(content=result)

            except HTTPException:
                raise
            except Exception as e:
                LOGGER.error(f"Error handling sheet update: {str(e)}", exc_info=True)
                return JSONResponse(
                    content=WebhookResponse(
                        status="error",
                        message=f"Sheet update error: {str(e)}",
                    ).model_dump(),
                    status_code=500,
                )

        return api_route
