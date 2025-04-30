from __future__ import annotations

import requests

from jira_telegram_bot.settings import TELEGRAM_SETTINGS


class MockTelegramPhoto:
    def __init__(self, file_id):
        self.file_id = file_id

    async def get_file(self):
        return MockFilePath(self.file_id)


class MockTelegramDocument(MockTelegramPhoto):
    pass


class MockTelegramVideo(MockTelegramPhoto):
    pass


class MockTelegramAudio(MockTelegramPhoto):
    pass


class MockFilePath:
    def __init__(self, file_id):
        self.file_id = file_id
        self.file_path = self._get_file_path()

    def _get_file_path(self) -> str:
        url = f"https://api.telegram.org/bot{TELEGRAM_SETTINGS.HOOK_TOKEN}/getFile?file_id={self.file_id}"
        resp = requests.get(url)
        if resp.status_code == 200:
            result = resp.json()["result"]
            return result["file_path"]
        else:
            raise Exception(
                f"Failed to get file path for file_id={self.file_id}, status={resp.status_code}",
            )
