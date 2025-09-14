"""Filter criteria entity for SynthPM synchronization operations."""
from __future__ import annotations

from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class SynthPMSyncFilterCriteria(BaseModel):
    """Entity representing filter criteria for SynthPM synchronization."""

    sprints: Optional[List[str]] = Field(
        default=None,
        description="List of sprint names to filter by. If None, all sprints are included",
    )
    release_versions: Optional[List[str]] = Field(
        default=None,
        description="List of release versions to filter by. If None, all releases are included",
    )
    releases: Optional[List[str]] = Field(
        default=None,
        description="List of release names to filter by. If None, all releases are included",
    )
    include_empty_sprint: bool = Field(
        default=True,
        description="Whether to include features with empty/null sprint field",
    )
    include_empty_release: bool = Field(
        default=True,
        description="Whether to include features with empty/null release fields",
    )

    class Config:
        """Pydantic configuration."""

        frozen = True

    def should_include_feature(
        self,
        feature_sprint: Optional[str],
        feature_release: Optional[str],
        feature_version: Optional[str],
    ) -> bool:
        """Check if a feature matches the filter criteria.

        Args:
            feature_sprint: Sprint value from the feature
            feature_release: Release value from the feature
            feature_version: Version value from the feature

        Returns:
            True if feature should be included, False otherwise
        """
        # Check sprint filtering
        if self.sprints is not None:
            sprint_match = (
                feature_sprint in self.sprints
                if feature_sprint
                else self.include_empty_sprint
            )
            if not sprint_match:
                return False

        # Check release filtering (both release and version fields)
        if self.releases is not None or self.release_versions is not None:
            release_match = False

            # Check against release field
            if self.releases is not None:
                release_match = (
                    feature_release in self.releases
                    if feature_release
                    else self.include_empty_release
                )

            # Check against version field
            if self.release_versions is not None and not release_match:
                release_match = (
                    feature_version in self.release_versions
                    if feature_version
                    else self.include_empty_release
                )

            # If neither release nor version filters are set, include all
            if self.releases is None and self.release_versions is None:
                release_match = True

            if not release_match:
                return False

        return True

    @classmethod
    def create_sprint_filter(
        cls,
        sprints: List[str],
        include_empty: bool = False,
    ) -> SynthPMSyncFilterCriteria:
        """Create a filter that only includes specific sprints.

        Args:
            sprints: List of sprint names to include
            include_empty: Whether to include features with empty sprint

        Returns:
            Filter criteria instance
        """
        return cls(
            sprints=sprints,
            include_empty_sprint=include_empty,
        )

    @classmethod
    def create_release_filter(
        cls,
        releases: Optional[List[str]] = None,
        versions: Optional[List[str]] = None,
        include_empty: bool = False,
    ) -> SynthPMSyncFilterCriteria:
        """Create a filter that only includes specific releases or versions.

        Args:
            releases: List of release names to include
            versions: List of version numbers to include
            include_empty: Whether to include features with empty release fields

        Returns:
            Filter criteria instance
        """
        return cls(
            releases=releases,
            release_versions=versions,
            include_empty_release=include_empty,
        )

    @classmethod
    def create_combined_filter(
        cls,
        sprints: Optional[List[str]] = None,
        releases: Optional[List[str]] = None,
        versions: Optional[List[str]] = None,
        include_empty_sprint: bool = False,
        include_empty_release: bool = False,
    ) -> SynthPMSyncFilterCriteria:
        """Create a filter with both sprint and release criteria.

        Args:
            sprints: List of sprint names to include
            releases: List of release names to include
            versions: List of version numbers to include
            include_empty_sprint: Whether to include features with empty sprint
            include_empty_release: Whether to include features with empty release fields

        Returns:
            Filter criteria instance
        """
        return cls(
            sprints=sprints,
            releases=releases,
            release_versions=versions,
            include_empty_sprint=include_empty_sprint,
            include_empty_release=include_empty_release,
        )
