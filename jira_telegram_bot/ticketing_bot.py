# run.py
from __future__ import annotations

import uvicorn

from jira_telegram_bot.frameworks.fast_api.create_ticket_controller import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=2315,
        reload=True,
    )
