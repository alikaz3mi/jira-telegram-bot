from __future__ import annotations

import multiprocessing
import os
from typing import List

import uvicorn
from chromatrace import FastAPIRequestIdMiddleware
from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.frameworks.api.configs.fastapi_doc import api_prefix
from jira_telegram_bot.frameworks.api.configs.fastapi_doc import fastapi_information
from jira_telegram_bot.frameworks.api.configs.fastapi_doc import fastapi_tags_metadata
from jira_telegram_bot.frameworks.api.base_endpoint import (
    ServiceAPIEndpointBluePrint,
)
from jira_telegram_bot.settings.fast_api_settings import FastAPISettings


class FastAPIConfig:
    information = fastapi_information
    tags_metadata = fastapi_tags_metadata
    has_socket = False
    version = fastapi_information["version"]
    API_VERSION = api_prefix

    def __init__(self):
        self.information = fastapi_information
        self.tags_metadata = fastapi_tags_metadata
        self.has_socket = False
        self.version = fastapi_information["version"]
        self.API_VERSION = api_prefix


class SocketServerConfig:
    def __init__(
        self,
    ):
        self.cors_allowed_origins = "*"
        self.socketio_path = "/socket.io"
        self.LOGGER = False
        self.always_connect = True
        self.engineio_logger = False
        self.server_workers = None


class SubServiceEndpoints:
    def __init__(self) -> None:
        self.services: List[ServiceAPIEndpointBluePrint] = []

    def register(self, service: ServiceAPIEndpointBluePrint) -> None:
        self.services.append(service)

    def get(self) -> List[ServiceAPIEndpointBluePrint]:
        return self.services


class APIEndpoint:
    def create_rest_api_app(self, information, tags_metadata) -> None:
        self.rest_api_app = FastAPI(**information, openapi_tags=tags_metadata)
        self.rest_api_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost", "http://192.168.200.3", "http://127.0.0.1", "http://192.168.100.10"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.rest_api_app.add_middleware(FastAPIRequestIdMiddleware)

    def __init__(
        self,
        configs: FastAPIConfig,
        fastapi_settings: FastAPISettings,
        sub_service_endpoints: SubServiceEndpoints,
    ) -> None:
        self.configs = configs
        self.fastapi_settings = fastapi_settings
        self.create_rest_api_app(self.configs.information, self.configs.tags_metadata)
        self.api_route = APIRouter()
        self.create_rest_api_route()
        self.sub_service_endpoints = sub_service_endpoints
        self.register_sub_service_endpoints()
        self.rest_application = self.rest_api_app


    def register_sub_service_endpoints(self):
        self.rest_api_app.include_router(self.api_route, prefix=self.configs.API_VERSION)
        for service in self.sub_service_endpoints.get():
            self.rest_api_app.include_router(service.api_route, prefix=self.configs.API_VERSION)
        os.makedirs(f"{DEFAULT_PATH}/media", exist_ok=True)
        self.rest_api_app.mount("/media", StaticFiles(directory=f"{DEFAULT_PATH}/media"), name="media")

    def start_rest_api_app(self, main_process: bool = False) -> None:
        LOGGER.info("Starting API Endpoint...")
        if main_process:
            uvicorn.run(
                self.rest_application,
                host=self.fastapi_settings.host,
                port=self.fastapi_settings.port,
            )
        else:
            multiprocessing.Process(
                target=uvicorn.run,
                kwargs={
                    "app": self.rest_application,
                    "host": self.fastapi_settings.host,
                    "port": self.fastapi_settings.port,
                },
            ).start()

    def socket_call_backs(self):
        @self.sio.on("connect")
        async def connect(sid, environ, auth):
            LOGGER.info(f"Socket connected with ID: {sid}")
            LOGGER.info("No Auth")
            self.sio.disconnect(sid)
            await self.sio.emit("connected", room=sid)

        @self.sio.on("disconnect")
        def disconnect(sid):
            LOGGER.info(f"Socket disconnected with ID: {sid}")

        @self.sio.on("message")
        async def message(sid, data: dict):
            LOGGER.info(f"Message from {sid}")
            try:
                pass
            except Exception as e:
                LOGGER.info(f"Error parsing messages from socket; {e}")
                await self.sio.emit("error", str(e), room=sid)

    def create_rest_api_route(self):
        @self.rest_api_app.get(
            "/",
            tags=["Main"],
            name="Root",
            responses={status.HTTP_200_OK: {"description": "Success"}},
        )
        async def root(request: Request):
            """Root of the Service."""
            return RedirectResponse(url="/docs")

        @self.rest_api_app.get(
            "/docs",
            tags=["Main"],
            responses={status.HTTP_200_OK: {"description": "Success"}},
        )
        async def docs(request: Request):
            """Playground of the Service."""
            return RedirectResponse(url=f"{self.configs.API_VERSION}/playground")

        @self.rest_api_app.get(
            "/redoc",
            tags=["Main"],
            responses={status.HTTP_200_OK: {"description": "Success"}},
        )
        async def redocs(request: Request):
            """Documentation of the Service."""
            return RedirectResponse(url=f"{self.configs.API_VERSION}/documentation")
