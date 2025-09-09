"""Tests for SynthPM Change Tracker."""
import pytest
from datetime import datetime
from jira_telegram_bot.entities.synth_pm.change_tracker import FeatureSnapshot, SynthPMChangeTracker
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity


class TestFeatureSnapshot:
    """Test FeatureSnapshot entity."""

    def test_initialization(self):
        """Test FeatureSnapshot initialization."""
        snapshot = FeatureSnapshot(
            sheet_row_number=10,
            content_hash="abc123",
            last_updated=datetime.now(),
            last_documentation_generated=datetime.now(),
        )

        assert snapshot.sheet_row_number == 10
        assert snapshot.content_hash == "abc123"
        assert snapshot.last_documentation_generated is not None

    def test_from_feature(self):
        """Test creating snapshot from feature."""
        feature = SynthPMFeatureEntity(
            sheet_row_number=5,
            task_title="Test Feature",
            task_description="Test Description",
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Test Epic",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["test"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="High",
            risk_assessment="Low",
            acceptance_criteria="Must work",
            test_cases="Unit tests",
            dependencies="None",
            row_number=5,
        )

        snapshot = FeatureSnapshot.from_feature(feature)
        
        assert snapshot.sheet_row_number == 5
        assert snapshot.content_hash is not None
        assert len(snapshot.content_hash) > 0
        assert snapshot.last_documentation_generated is None

    def test_has_documentation_generated(self):
        """Test documentation generation check."""
        feature = SynthPMFeatureEntity(
            sheet_row_number=5,
            task_title="Test Feature",
            task_description="Test Description",
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Test Epic",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["test"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="High",
            risk_assessment="Low",
            acceptance_criteria="Must work",
            test_cases="Unit tests",
            dependencies="None",
            row_number=5,
        )

        snapshot = FeatureSnapshot.from_feature(feature)
        
        # Initially no documentation
        assert snapshot.last_documentation_generated is None
        
        # After setting documentation time
        snapshot.last_documentation_generated = datetime.now()
        assert snapshot.last_documentation_generated is not None

    def test_needs_documentation_update(self):
        """Test change detection logic."""
        feature = SynthPMFeatureEntity(
            sheet_row_number=5,
            task_title="Test Feature",
            task_description="Test Description",
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Test Epic",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["test"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="High",
            risk_assessment="Low",
            acceptance_criteria="Must work",
            test_cases="Unit tests",
            dependencies="None",
            row_number=5,
        )

        snapshot = FeatureSnapshot.from_feature(feature)
        
        # Feature with no documentation generated needs update
        assert snapshot.needs_documentation_update(feature)
        
        # Mark documentation as generated
        snapshot.last_documentation_generated = datetime.now()
        
        # Same feature should not need update now
        assert not snapshot.needs_documentation_update(feature)
        
        # Create modified feature (new instance with different title)
        modified_feature = SynthPMFeatureEntity(
            sheet_row_number=5,
            task_title="Changed Feature",  # Different title
            task_description="Test Description",
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Test Epic",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["test"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="High",
            risk_assessment="Low",
            acceptance_criteria="Must work",
            test_cases="Unit tests",
            dependencies="None",
            row_number=5,
        )
        
        assert snapshot.needs_documentation_update(modified_feature)


class TestSynthPMChangeTracker:
    """Test SynthPMChangeTracker entity."""

    def test_initialization(self):
        """Test tracker initialization."""
        tracker = SynthPMChangeTracker()
        
        assert len(tracker.snapshots) == 0
        assert tracker.last_sync is not None  # Has default

    def test_detect_changes_new_features(self):
        """Test detecting new features."""
        tracker = SynthPMChangeTracker()
        
        feature = SynthPMFeatureEntity(
            sheet_row_number=1,
            task_title="New Feature",
            task_description="Description",
            task_type="feature",
            task_priority="High",
            assignee="Ali",
            components=["web"],
            epic="Epic 1",
            sprint="Sprint 1",
            status="To Do",
            story_points=5,
            labels=["new"],
            fixversion="1.0.0",
            product_area="Frontend",
            customer_feedback="Requested",
            business_value="High",
            risk_assessment="Medium",
            acceptance_criteria="Clear",
            test_cases="Automated",
            dependencies="API",
            row_number=1,
        )

        changes = tracker.detect_changes([feature])
        
        assert len(changes["new"]) == 1
        assert len(changes["modified"]) == 0
        assert len(changes["unchanged"]) == 0
        assert len(changes["needs_docs"]) == 1
        assert changes["new"][0] == feature

    def test_detect_changes_modified_features(self):
        """Test detecting modified features."""
        tracker = SynthPMChangeTracker()
        
        feature = SynthPMFeatureEntity(
            sheet_row_number=1,
            task_title="Feature",
            task_description="Description",
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Epic 1",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["feature"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="Medium",
            risk_assessment="Low",
            acceptance_criteria="Defined",
            test_cases="Manual",
            dependencies="Database",
            row_number=1,
        )

        # Create initial snapshot
        tracker.update_snapshots([feature])
        
        # Create modified feature (new instance)
        modified_feature = SynthPMFeatureEntity(
            sheet_row_number=1,
            task_title="Modified Feature",
            task_description="Description",
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Epic 1",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["feature"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="Medium",
            risk_assessment="Low",
            acceptance_criteria="Defined",
            test_cases="Manual",
            dependencies="Database",
            row_number=1,
        )
        
        changes = tracker.detect_changes([modified_feature])
        
        assert len(changes["new"]) == 0
        assert len(changes["modified"]) == 1
        assert len(changes["unchanged"]) == 0
        assert len(changes["needs_docs"]) == 1
        assert changes["modified"][0] == modified_feature

    def test_update_snapshots(self):
        """Test updating snapshots."""
        tracker = SynthPMChangeTracker()
        
        feature = SynthPMFeatureEntity(
            sheet_row_number=1,
            task_title="Feature",
            task_description="Description",
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Epic 1",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["feature"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="Medium",
            risk_assessment="Low",
            acceptance_criteria="Defined",
            test_cases="Manual",
            dependencies="Database",
            row_number=1,
        )

        tracker.update_snapshots([feature], generated_docs_for=[1])
        
        assert len(tracker.snapshots) == 1
        assert tracker.snapshots[1].last_documentation_generated is not None
        assert tracker.last_sync is not None

    def test_force_documentation_regeneration(self):
        """Test forcing documentation regeneration."""
        tracker = SynthPMChangeTracker()
        
        feature = SynthPMFeatureEntity(
            sheet_row_number=1,
            task_title="Feature",
            task_description="Description",
            task_type="feature",
            task_priority="Medium",
            assignee="Ali",
            components=["backend"],
            epic="Epic 1",
            sprint="Sprint 1",
            status="In Progress",
            story_points=3,
            labels=["feature"],
            fixversion="1.0.0",
            product_area="Core",
            customer_feedback="Good",
            business_value="Medium",
            risk_assessment="Low",
            acceptance_criteria="Defined",
            test_cases="Manual",
            dependencies="Database",
            row_number=1,
        )

        # Create snapshot with docs generated
        tracker.update_snapshots([feature], generated_docs_for=[1])
        assert tracker.snapshots[1].last_documentation_generated is not None
        
        # Force regeneration
        tracker.force_documentation_regeneration([1])
        assert tracker.snapshots[1].last_documentation_generated is None
