.PHONY: integration-tests clean-reports unit-tests

# Path to Python interpreter
PYTHON = python3

# Project name
PROJECT = jira_telegram_bot

# Test directories
TEST_DIR = tests
REPORTS_DIR = reports

# Integration tests
integration-tests: create-reports-dir
	$(PYTHON) -m pytest $(TEST_DIR)/integration -v --cov=$(PROJECT) \
	--cov-report=xml:$(REPORTS_DIR)/coverage.xml \
	--cov-report=html:$(REPORTS_DIR)/coverage_html \
	--junitxml=$(REPORTS_DIR)/junit.xml

# Run integration tests for Jira Server Repository specifically
integration-tests-jira: create-reports-dir
	$(PYTHON) -m pytest $(TEST_DIR)/integration/adapters/repositories/jira -v --cov=$(PROJECT).adapters.repositories.jira \
	--cov-report=xml:$(REPORTS_DIR)/jira_coverage.xml \
	--cov-report=html:$(REPORTS_DIR)/jira_coverage_html \
	--junitxml=$(REPORTS_DIR)/jira_junit.xml

# Unit tests
unit-tests: create-reports-dir
	$(PYTHON) -m pytest $(TEST_DIR)/unit_tests -v --cov=$(PROJECT) \
	--cov-report=xml:$(REPORTS_DIR)/unit_coverage.xml \
	--cov-report=html:$(REPORTS_DIR)/unit_coverage_html \
	--junitxml=$(REPORTS_DIR)/unit_junit.xml

# Create reports directory
create-reports-dir:
	mkdir -p $(REPORTS_DIR)

# Clean reports
clean-reports:
	rm -rf $(REPORTS_DIR)

# Jira Report System Tests
jira-report-unit-tests: create-reports-dir
	$(PYTHON) -m unittest discover -s tests/unit_tests/entities -p test_jira_report.py -v
	$(PYTHON) -m unittest discover -s tests/unit_tests/use_cases -p test_generate_jira_report_use_case.py -v
	$(PYTHON) -m unittest discover -s tests/unit_tests/use_cases -p test_scheduled_report_use_case.py -v
	$(PYTHON) -m unittest discover -s tests/unit_tests/adapters -p test_jira_data_service.py -v
	$(PYTHON) -m unittest discover -s tests/unit_tests/adapters -p test_jira_report_repository.py -v
	$(PYTHON) -m unittest discover -s tests/unit_tests/frameworks -p test_ap_scheduler_service.py -v

jira-report-integration-tests: create-reports-dir
	$(PYTHON) -m unittest tests.integration.test_jira_report_system_integration -v

jira-report-tests: jira-report-unit-tests jira-report-integration-tests

jira-report-coverage: create-reports-dir
	$(PYTHON) -m coverage run --source=jira_telegram_bot -m unittest discover -s tests -p test_*.py
	$(PYTHON) -m coverage report --show-missing
	$(PYTHON) -m coverage html -d $(REPORTS_DIR)/jira_report_coverage
	$(PYTHON) -m coverage xml -o $(REPORTS_DIR)/jira_report_coverage.xml

# Run all Jira report tests with coverage
test-jira-reports: create-reports-dir
	$(PYTHON) scripts/run_tests.py --all

# Jira Project Sync Commands
sync-check:
	$(PYTHON) scripts/sync/check_sync_status.py

sync-last-month:
	$(PYTHON) scripts/sync/sync_all_projects_last_month.py

sync-custom:
	@echo "Usage: make sync-custom ARGS='--days 7' or ARGS='--projects PROJ1 PROJ2 --since 2025-12-01'"
	@echo "Run with ARGS variable set, e.g.: make sync-custom ARGS='--days 7'"
	$(PYTHON) scripts/sync/sync_projects_date_range.py $(ARGS)