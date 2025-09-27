"""Change detection entity for tracking SynthPM feature modifications."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Dict
from typing import Optional

from pydantic import BaseModel
from pydantic import Field

from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity


class FeatureSnapshot(BaseModel):
    """Snapshot of a feature for change detection."""
    
    sheet_row_number: int = Field(description="Row number in Google Sheet")
    content_hash: str = Field(description="Hash of relevant content for change detection")
    last_updated: datetime = Field(description="When this snapshot was taken")
    last_documentation_generated: Optional[datetime] = Field(
        default=None,
        description="When documentation was last generated for this feature"
    )
    jira_issue_key: Optional[str] = Field(
        default=None,
        description="Associated Jira issue key"
    )
    
    @classmethod
    def from_feature(cls, feature: SynthPMFeatureEntity) -> "FeatureSnapshot":
        """Create a snapshot from a SynthPM feature.
        
        Args:
            feature: SynthPM feature entity
            
        Returns:
            FeatureSnapshot instance
        """
        # Create hash from Google Sheet fields that affect documentation
        # These are the fields that PO/PM will update in Google Sheets
        relevant_fields = {
            "task_title": feature.task_title or "",
            "description": feature.description or "",
            "acceptance_criteria": feature.acceptance_criteria or "",
            "test_cases": feature.test_cases or "",
            "epic": feature.epic or "",
            "departments": feature.departments or "",
            "priority": feature.priority or "",
            "necessity": feature.necessity or "",
        }
        
        content_string = "|".join(f"{k}:{v}" for k, v in sorted(relevant_fields.items()))
        content_hash = hashlib.sha256(content_string.encode()).hexdigest()
        
        return cls(
            sheet_row_number=feature.sheet_row_number,
            content_hash=content_hash,
            last_updated=datetime.now(),
            jira_issue_key=feature.developer_board_issue_key,
        )
    
    def needs_documentation_update(self, current_feature: SynthPMFeatureEntity) -> bool:
        """Check if feature needs documentation update.
        
        Args:
            current_feature: Current feature state
            
        Returns:
            True if documentation should be regenerated
        """
        current_snapshot = self.from_feature(current_feature)
        
        # Check if content has changed
        if self.content_hash != current_snapshot.content_hash:
            return True
            
        # Check if documentation was never generated
        if self.last_documentation_generated is None:
            return True
            
        return False


class SynthPMChangeTracker(BaseModel):
    """Tracks changes to SynthPM features for efficient updates."""
    
    snapshots: Dict[int, FeatureSnapshot] = Field(
        default_factory=dict,
        description="Dictionary mapping sheet_row_number to FeatureSnapshot"
    )
    last_sync: datetime = Field(
        default_factory=datetime.now,
        description="When the last sync was performed"
    )
    
    def detect_changes(
        self,
        current_features: list[SynthPMFeatureEntity],
    ) -> Dict[str, list[SynthPMFeatureEntity]]:
        """Detect what features have changed since last sync.
        
        Args:
            current_features: Current list of features from Google Sheets
            
        Returns:
            Dictionary categorizing features by change type
        """
        changes = {
            "new": [],           # Features that don't exist in snapshots
            "modified": [],      # Features with content changes
            "unchanged": [],     # Features with no changes
            "needs_docs": [],    # Features that need documentation generation
        }
        
        current_row_numbers = {f.sheet_row_number for f in current_features}
        tracked_row_numbers = set(self.snapshots.keys())
        
        for feature in current_features:
            row_num = feature.sheet_row_number
            
            if row_num not in self.snapshots:
                # New feature
                changes["new"].append(feature)
                changes["needs_docs"].append(feature)
            else:
                # Existing feature - check for changes
                snapshot = self.snapshots[row_num]
                current_snapshot = FeatureSnapshot.from_feature(feature)
                
                # Check if content actually changed
                content_changed = snapshot.content_hash != current_snapshot.content_hash
                needs_docs = snapshot.needs_documentation_update(feature)
                
                if content_changed:
                    changes["modified"].append(feature)
                    changes["needs_docs"].append(feature)
                elif needs_docs:
                    # Content unchanged but needs documentation
                    changes["unchanged"].append(feature)
                    changes["needs_docs"].append(feature)
                else:
                    changes["unchanged"].append(feature)
        
        # Features that were deleted (exist in snapshots but not in current)
        deleted_rows = tracked_row_numbers - current_row_numbers
        for row_num in deleted_rows:
            # Handle deletion - could be logged or cleaned up
            pass
            
        return changes
    
    def update_snapshots(
        self,
        features: list[SynthPMFeatureEntity],
        generated_docs_for: Optional[list[int]] = None,
    ) -> None:
        """Update snapshots after processing features.
        
        Args:
            features: List of processed features
            generated_docs_for: List of sheet_row_numbers that got documentation generated
        """
        generated_rows = set(generated_docs_for or [])
        
        for feature in features:
            snapshot = FeatureSnapshot.from_feature(feature)
            
            # If documentation was generated for this feature, mark it
            if feature.sheet_row_number in generated_rows:
                snapshot.last_documentation_generated = datetime.now()
                
            self.snapshots[feature.sheet_row_number] = snapshot
            
        self.last_sync = datetime.now()
    
    def force_documentation_regeneration(self, sheet_row_numbers: list[int]) -> None:
        """Force documentation regeneration for specific features.
        
        Args:
            sheet_row_numbers: List of row numbers to force regeneration for
        """
        for row_num in sheet_row_numbers:
            if row_num in self.snapshots:
                self.snapshots[row_num].last_documentation_generated = None
