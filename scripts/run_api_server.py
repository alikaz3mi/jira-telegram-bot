#!/usr/bin/env python
"""Run the Jira Telegram Bot API server."""

import argparse
import os
import uvicorn

from jira_telegram_bot import LOGGER


def parse_arguments():
    """Parse command line arguments.
    
    Returns:
        Parsed command-line arguments
    """
    parser = argparse.ArgumentParser(description="Run Jira Telegram Bot API server")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind the server to"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind the server to"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--log-level", default="info", 
        choices=["debug", "info", "warning", "error", "critical"],
        help="Logging level"
    )
    
    return parser.parse_args()


def main():
    """Run the FastAPI server."""
    args = parse_arguments()
    
    LOGGER.info(f"Starting API server on {args.host}:{args.port}")
    
    uvicorn.run(
        "jira_telegram_bot.frameworks.api.entry_point:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
