from pydantic import BaseModel, Field
from typing import List


class JiraBoard(BaseModel):
    board_name: str = Field("name of the jira board")
    assignees: List[str] = Field("List of users of the Jira board")
