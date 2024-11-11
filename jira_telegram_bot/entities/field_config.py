from __future__ import annotations

from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class FieldConfig(BaseModel):
    set_field: bool = Field(default=False)  # Whether to prompt the user for this field
    values: Optional[List[str]] = None  # Predefined values if set_field is True
