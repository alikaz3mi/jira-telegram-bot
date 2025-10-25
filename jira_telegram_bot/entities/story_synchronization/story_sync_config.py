"""Configuration entities for story synchronization."""
from typing import List

from pydantic import BaseModel
from pydantic import Field
from pydantic import validator


class SheetBoardMapping(BaseModel):
    """Entity representing the mapping between a Google Sheet and a Jira board."""

    spreadsheet_id: str = Field(description="Google Sheets spreadsheet ID")
    sheet_name: str = Field(description="Name of the specific sheet/tab")
    board_key: str = Field(description="Jira board/project key")
    gid: int = Field(description="Google Sheet tab GID")

    class Config:
        frozen = True


class StorySyncConfig(BaseModel):
    """Entity representing the complete story sync configuration."""

    mappings: List[SheetBoardMapping] = Field(
        description="List of sheet-to-board mappings",
    )

    @validator("mappings")
    def validate_unique_boards(cls, mappings: List[SheetBoardMapping]):
        board_keys = [m.board_key for m in mappings]
        if len(board_keys) != len(set(board_keys)):
            raise ValueError("Duplicate board keys found in mappings")
        return mappings

    def get_mapping_by_board(self, board_key: str) -> SheetBoardMapping:
        """Get mapping configuration for a specific board.

        Args:
            board_key: Jira board/project key.

        Returns:
            SheetBoardMapping for the board.

        Raises:
            ValueError: If board key not found in mappings.
        """
        for mapping in self.mappings:
            if mapping.board_key == board_key:
                return mapping
        raise ValueError(f"No mapping found for board: {board_key}")

    def get_all_board_keys(self) -> List[str]:
        """Get all configured board keys.

        Returns:
            List of board keys.
        """
        return [m.board_key for m in self.mappings]

    class Config:
        frozen = False
