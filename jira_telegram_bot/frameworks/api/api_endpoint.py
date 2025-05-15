"""API Endpoint class for the FastAPI application."""

from __future__ import annotations

import logging
import multiprocessing
from contextlib import asynccontextmanager, suppress
from typing import AsyncGenerator, Optional, List

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic_settings import BaseSettings

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import startup, shutdown
from jira_telegram_bot.frameworks.api.base_endpoint import ServiceAPIEndpointBluePrint
from jira_telegram_bot.frameworks.api.configs.fastapi_doc import (
    api_prefix,
    fastapi_information,
    fastapi_tags_metadata,
)
from jira_telegram_bot.frameworks.api.registry import SubServiceEndpoints
from jira_telegram_bot.utils.exceptions import CustomException, CustomHTTPException


class APIEndpointConfig(BaseSettings):
    """Configuration settings for the API endpoint.
    
    Attributes:
        information: Information about the API
        tags_metadata: Tags metadata for OpenAPI
        version: API version
        api_version_prefix: API version prefix
        allow_origins: CORS allowed origins
        enable_docs: Whether to enable API documentation
        port: Port to run the server on
    """
    
    information: dict = fastapi_information
    tags_metadata: list = fastapi_tags_metadata
    version: str = fastapi_information.get("version", "1.0.0")
    api_version_prefix: str = api_prefix
    allow_origins: list = ["*"]
    enable_docs: bool = True
    port: int = 8000


class APIEndpoint:
    """Main API endpoint class that configures and runs the FastAPI application."""
    
    def __init__(
        self,
        config: APIEndpointConfig,
        sub_service_endpoints: SubServiceEndpoints,
    ) -> None:
        """Initialize the API endpoint.
        
        Args:
            config: API endpoint configuration
            sub_service_endpoints: Registry of endpoint services
        """
        self.config = config
        self.logger = LOGGER
        self.api_route = APIRouter()
        self.sub_service_endpoints = sub_service_endpoints
        
        # Create the FastAPI application
        self.rest_api_app = self._create_rest_api_app()
        
        # Create base API routes
        self._create_rest_api_route()
        
        # Register subservice endpoints
        self._register_sub_service_endpoints()
        
        # Set the final application
        self.rest_application = self.rest_api_app

    def _create_rest_api_app(self) -> FastAPI:
        """Create and configure the FastAPI application.
        
        Returns:
            Configured FastAPI application
        """
        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            """Define application lifespan events.
            
            Args:
                app: FastAPI application instance
                
            Yields:
                None
            """
            # Startup
            self.logger.info("Starting API server...")
            startup()
            yield
            # Shutdown
            self.logger.info("Shutting down API server...")
            await shutdown()
        
        # Create FastAPI application with lifespan context manager
        app = FastAPI(
            **self.config.information,
            openapi_tags=self.config.tags_metadata,
            lifespan=lifespan,
        )
        
        # Configure CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add exception handlers
        @app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            try:
                errors = [f"{error['loc'][1]}: {error['msg']}" for error in exc.errors()]
            except Exception:
                try:
                    errors = [f"{error['loc'][0]}: {error['msg']}" for error in exc.errors()]
                except Exception:
                    errors = []
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "validation_error",
                    "errors": errors,
                    "information": exc.errors(),
                },
            )
        
        @app.exception_handler(CustomException)
        async def custom_exception_handler(request: Request, exc: CustomException):
            try:
                return JSONResponse(
                    status_code=exc.status_code,
                    content=exc.message,
                    headers=exc.headers if hasattr(exc, 'headers') else None,
                )
            except Exception as e:
                self.logger.error(f"Error while handling CustomException: {str(e)}")
                return JSONResponse(
                    status_code=exc.status_code,
                    content=exc.message,
                )
        
        @app.exception_handler(CustomHTTPException)
        async def custom_http_exception_handler(request: Request, exc: CustomHTTPException):
            try:
                return JSONResponse(
                    status_code=exc.status_code,
                    content=exc.message,
                    headers=exc.to_json() if hasattr(exc, 'to_json') else None,
                )
            except Exception as e:
                self.logger.error(f"Error while handling CustomHTTPException: {str(e)}")
                return JSONResponse(
                    status_code=exc.status_code,
                    content=exc.message,
                )
        
        return app

    def _register_sub_service_endpoints(self) -> None:
        """Register all endpoint services with the FastAPI application."""
        # Include the base API router
        self.rest_api_app.include_router(
            self.api_route,
            prefix=self.config.api_version_prefix
        )
        
        # Include all subservice endpoints
        for endpoint in self.sub_service_endpoints.endpoints:
            endpoint_name = endpoint.__class__.__name__
            self.logger.info(f"Registering endpoint: {endpoint_name}")
            
            # Get the API router - either from api_route attribute or by calling create_rest_api_route
            api_router = endpoint.__dict__.get('api_route', None)
            if api_router is None:
                self.logger.warning(f"No API router found for {endpoint_name}, trying to create one")
                api_router = endpoint.create_rest_api_route()
                
            # Include router in the FastAPI application
            self.rest_api_app.include_router(
                api_router,
                prefix=self.config.api_version_prefix
            )

    def _create_rest_api_route(self) -> None:
        """Create the base API routes."""
        @self.rest_api_app.get(
            "/",
            tags=["Main"],
            name="Root",
            responses={status.HTTP_200_OK: {"description": "Success"}},
        )
        async def root(request: Request):
            """Root endpoint of the API."""
            return RedirectResponse(url=f"{self.config.api_version_prefix}/docs")
        
        if self.config.enable_docs:
            @self.rest_api_app.get(
                "/api",
                tags=["Main"],
                responses={status.HTTP_200_OK: {"description": "Success"}},
            )
            async def api_docs(request: Request):
                """API documentation endpoint."""
                return RedirectResponse(url=f"{self.config.api_version_prefix}/docs")
        
        @self.api_route.get(
            "/health",
            tags=["Main"],
            responses={
                status.HTTP_200_OK: {"description": "Success"},
            },
        )
        async def health():
            """Health check endpoint."""
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"status": "healthy"}
            )
    
    def run(self) -> None:
        """Run the FastAPI application with Uvicorn."""
        # Import here to avoid circular imports
        import jira_telegram_bot.frameworks.api.entry_point as entry_point
        
        # Make sure entry_point.app is updated with our instance
        entry_point.app = self.rest_application
        
        uvicorn.run(
            "jira_telegram_bot.frameworks.api.entry_point:app",
            host="0.0.0.0",
            port=self.config.port,
            log_level="info",
        )
    
    def start_app(self, main_process: bool = False) -> None:
        """Start the FastAPI application.
        
        Args:
            main_process: Whether to run in the main process or a separate one
        """
        self.logger.info("Starting API Endpoint...")
        if main_process:
            self.run()
        else:
            self.rest_api_process = multiprocessing.Process(target=self.run).start()
