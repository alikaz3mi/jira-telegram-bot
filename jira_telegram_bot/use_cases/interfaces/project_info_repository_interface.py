from __future__ import annotations

from typing import Dict, Any, Optional


class ProjectInfoRepositoryInterface:
    """Interface for accessing and retrieving project information."""

    async def get_project_info(self, project_key: str) -> Dict[str, Any]:
        """Retrieve project information by project key.

        Args:
            project_key: The project key to retrieve information for.

        Returns:
            Dictionary containing project information.

        Raises:
            ValueError: If no project information is found for the given project key.
        """
        pass