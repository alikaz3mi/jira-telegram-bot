from __future__ import annotations

import requests



class MockTelegramPhoto:
    def __init__(self, file_id, token: str = None):
        self.file_id = file_id
        self.token = token

    async def get_file(self):
        return MockFilePath(self.file_id, self.token)


class MockTelegramDocument(MockTelegramPhoto):
    pass


class MockTelegramVideo(MockTelegramPhoto):
    pass


class MockTelegramAudio(MockTelegramPhoto):
    pass


class MockFilePath:
    def __init__(self, file_id: str | int, token: str = None):
        self.file_id = file_id
        self.file_path = self._get_file_path(token)

    def _get_file_path(self, token: str) -> str:
        url = f"https://api.telegram.org/bot{token}/getFile?file_id={self.file_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            result = resp.json()["result"]
            return result["file_path"]
        else:
            error_msg = f"Failed to get file path for file_id={self.file_id}, status={resp.status_code}"
            try:
                error_detail = resp.json()
                if "description" in error_detail:
                    error_msg += f", description: {error_detail['description']}"
                    # Common Telegram errors:
                    # - "Bad Request: file is too big" (>20MB for getFile)
                    # - "Bad Request: wrong file_id" (expired or invalid)
                    # - "Unauthorized" (invalid bot token)
            except Exception:
                error_msg += f", response: {resp.text[:200]}"
            raise Exception(error_msg)
