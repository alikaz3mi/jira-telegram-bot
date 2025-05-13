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