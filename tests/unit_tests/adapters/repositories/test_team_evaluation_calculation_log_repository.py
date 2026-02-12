"""Unit tests for PostgreSQLTeamEvaluationCalculationLogRepository."""
import unittest
from datetime import datetime
from unittest.mock import Mock, MagicMock, call, patch

from jira_telegram_bot.adapters.repositories.postgres.team_evaluation_calculation_log_repository import (
    PostgreSQLTeamEvaluationCalculationLogRepository,
    TeamEvaluationCalculationLogModel,
)
from jira_telegram_bot.entities.team_evaluation_calculation_log import (
    TeamEvaluationCalculationLog,
)


class TestPostgreSQLTeamEvaluationCalculationLogRepository(unittest.TestCase):
    """Test cases for PostgreSQLTeamEvaluationCalculationLogRepository."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db_connection = Mock()
        self.mock_session = Mock()
        self.mock_db_connection.get_session.return_value = self.mock_session
        
        self.repository = PostgreSQLTeamEvaluationCalculationLogRepository(
            db_connection=self.mock_db_connection
        )
        
        self.sample_log = TeamEvaluationCalculationLog(
            sprint_id=123,
            sprint_name="MYPROJECT SPRINT 50",
            developer_name="کاظمی",
            department="DevOps",
            project="MYPROJECT",
            calculation_type="score_component",
            metric_name="deadline_score",
            metric_value=85.5,
            calculation_formula="max(0, 100 - penalty)",
            calculation_details="Started with 100, penalty: 14.5",
            weight=0.3,
            contribution_to_total=25.65,
            timestamp=datetime(2025, 12, 15, 10, 0, 0)
        )

    def test_save_log_success(self):
        """Test successfully saving a single calculation log."""
        self.repository.save_log(self.sample_log)
        
        # Verify session.add was called
        self.mock_session.add.assert_called_once()
        
        # Verify session.commit was called
        self.mock_session.commit.assert_called_once()
        
        # Verify the model was created correctly
        added_model = self.mock_session.add.call_args[0][0]
        self.assertIsInstance(added_model, TeamEvaluationCalculationLogModel)
        self.assertEqual(added_model.sprint_id, 123)
        self.assertEqual(added_model.developer_name, "کاظمی")
        self.assertEqual(added_model.metric_value, 85.5)

    def test_save_log_with_exception_rolls_back(self):
        """Test that save_log rolls back on exception."""
        self.mock_session.commit.side_effect = Exception("Database error")
        
        with self.assertRaises(Exception) as context:
            self.repository.save_log(self.sample_log)
        
        self.assertIn("Database error", str(context.exception))
        self.mock_session.rollback.assert_called_once()

    def test_save_logs_batch_success(self):
        """Test successfully saving multiple calculation logs in batch."""
        logs = [
            self.sample_log,
            TeamEvaluationCalculationLog(
                sprint_id=123,
                sprint_name="MYPROJECT SPRINT 50",
                developer_name="کاظمی",
                department="DevOps",
                project="MYPROJECT",
                calculation_type="metric",
                metric_name="worklog_score",
                metric_value=95.0,
                calculation_formula="ratio * 100",
                calculation_details="Worklog ratio calculation",
                timestamp=datetime(2025, 12, 15, 10, 0, 0)
            ),
            TeamEvaluationCalculationLog(
                sprint_id=123,
                sprint_name="MYPROJECT SPRINT 50",
                developer_name="کاظمی",
                department="DevOps",
                project="MYPROJECT",
                calculation_type="final_score",
                metric_name="quality_score_total",
                metric_value=78.0,
                calculation_formula="weighted_sum",
                calculation_details="Final composite score",
                timestamp=datetime(2025, 12, 15, 10, 0, 0)
            )
        ]
        
        self.repository.save_logs_batch(logs)
        
        # Verify session.add_all was called with list of models
        self.mock_session.add_all.assert_called_once()
        added_models = self.mock_session.add_all.call_args[0][0]
        self.assertEqual(len(added_models), 3)
        
        # Verify session.commit was called
        self.mock_session.commit.assert_called_once()

    def test_save_logs_batch_with_exception_rolls_back(self):
        """Test that save_logs_batch rolls back on exception."""
        logs = [self.sample_log]
        self.mock_session.commit.side_effect = Exception("Batch error")
        
        with self.assertRaises(Exception) as context:
            self.repository.save_logs_batch(logs)
        
        self.assertIn("Batch error", str(context.exception))
        self.mock_session.rollback.assert_called_once()

    def test_get_logs_by_sprint_and_developer(self):
        """Test retrieving logs by sprint ID and developer name."""
        # Create mock models
        mock_model_1 = Mock(spec=TeamEvaluationCalculationLogModel)
        mock_model_1.sprint_id = 123
        mock_model_1.sprint_name = "MYPROJECT SPRINT 50"
        mock_model_1.developer_name = "کاظمی"
        mock_model_1.department = "DevOps"
        mock_model_1.project = "MYPROJECT"
        mock_model_1.calculation_type = "metric"
        mock_model_1.metric_name = "test_metric"
        mock_model_1.metric_value = 100.0
        mock_model_1.calculation_formula = "test"
        mock_model_1.calculation_details = "test details"
        mock_model_1.weight = None
        mock_model_1.contribution_to_total = None
        mock_model_1.id = 1
        mock_model_1.timestamp = datetime(2025, 12, 15, 10, 0, 0)
        
        # Setup mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_order_by = Mock()
        
        self.mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.all.return_value = [mock_model_1]
        
        # Execute
        results = self.repository.get_logs_by_sprint_and_developer(123, "کاظمی")
        
        # Verify
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], TeamEvaluationCalculationLog)
        self.assertEqual(results[0].sprint_id, 123)
        self.assertEqual(results[0].developer_name, "کاظمی")

    def test_get_logs_by_evaluation_id(self):
        """Test retrieving logs by evaluation ID."""
        # Create mock model
        mock_model = Mock(spec=TeamEvaluationCalculationLogModel)
        mock_model.sprint_id = 123
        mock_model.sprint_name = "MYPROJECT SPRINT 50"
        mock_model.developer_name = "کاظمی"
        mock_model.department = "DevOps"
        mock_model.project = "MYPROJECT"
        mock_model.calculation_type = "final_score"
        mock_model.metric_name = "quality_score_total"
        mock_model.metric_value = 75.0
        mock_model.calculation_formula = "weighted_sum"
        mock_model.calculation_details = "Final score"
        mock_model.weight = None
        mock_model.contribution_to_total = None
        mock_model.id = 1
        mock_model.timestamp = datetime(2025, 12, 15, 10, 0, 0)
        
        # Setup mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_order_by = Mock()
        
        self.mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.all.return_value = [mock_model]
        
        # Execute
        results = self.repository.get_logs_by_evaluation_id(456)
        
        # Verify
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], TeamEvaluationCalculationLog)
        self.assertEqual(results[0].metric_name, "quality_score_total")

    def test_to_model_conversion(self):
        """Test entity to model conversion."""
        model = self.repository._to_model(self.sample_log)
        
        self.assertIsInstance(model, TeamEvaluationCalculationLogModel)
        self.assertEqual(model.sprint_id, self.sample_log.sprint_id)
        self.assertEqual(model.sprint_name, self.sample_log.sprint_name)
        self.assertEqual(model.developer_name, self.sample_log.developer_name)
        self.assertEqual(model.department, self.sample_log.department)
        self.assertEqual(model.project, self.sample_log.project)
        self.assertEqual(model.calculation_type, self.sample_log.calculation_type)
        self.assertEqual(model.metric_name, self.sample_log.metric_name)
        self.assertEqual(model.metric_value, self.sample_log.metric_value)
        self.assertEqual(model.weight, self.sample_log.weight)
        self.assertEqual(model.contribution_to_total, self.sample_log.contribution_to_total)

    def test_to_entity_conversion(self):
        """Test model to entity conversion."""
        # Create a mock model
        mock_model = Mock(spec=TeamEvaluationCalculationLogModel)
        mock_model.sprint_id = 123
        mock_model.sprint_name = "MYPROJECT SPRINT 50"
        mock_model.developer_name = "کاظمی"
        mock_model.department = "DevOps"
        mock_model.project = "MYPROJECT"
        mock_model.calculation_type = "score_component"
        mock_model.metric_name = "deadline_score"
        mock_model.metric_value = 85.5
        mock_model.calculation_formula = "max(0, 100 - penalty)"
        mock_model.calculation_details = "Test details"
        mock_model.weight = 0.3
        mock_model.contribution_to_total = 25.65
        mock_model.id = 456
        mock_model.timestamp = datetime(2025, 12, 15, 10, 0, 0)
        
        entity = self.repository._to_entity(mock_model)
        
        self.assertIsInstance(entity, TeamEvaluationCalculationLog)
        self.assertEqual(entity.sprint_id, mock_model.sprint_id)
        self.assertEqual(entity.developer_name, mock_model.developer_name)
        self.assertEqual(entity.metric_value, mock_model.metric_value)
        self.assertEqual(entity.evaluation_id, mock_model.id)


if __name__ == "__main__":
    unittest.main()
