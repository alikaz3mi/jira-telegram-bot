from __future__ import annotations

from typing import Any
from typing import Dict


def get_username_from_post(message: Dict[str, Any]) -> str:
    return message.get("from", {}).get("username", "UnknownUser")


def get_text_from_message(message: Dict[str, Any]) -> str:
    return message.get("text") or message.get("caption") or ""
