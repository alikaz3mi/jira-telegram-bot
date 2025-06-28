"""Test runner script for Jira report system tests."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_unit_tests():
    """Run unit tests for Jira report system."""
    print("🧪 Running unit tests...")
    
    test_modules = [
        "tests.unit_tests.entities.test_jira_report",
        "tests.unit_tests.use_cases.test_generate_jira_report_use_case",
        "tests.unit_tests.use_cases.test_scheduled_report_use_case",
        "tests.unit_tests.adapters.services.test_jira_data_service",
        "tests.unit_tests.adapters.repositories.test_jira_report_repository",
        "tests.unit_tests.frameworks.scheduler.test_ap_scheduler_service",
    ]
    
    for module in test_modules:
        print(f"  Running {module}...")
        result = subprocess.run([
            sys.executable, "-m", "unittest", module, "-v"
        ], capture_output=False)
        
        if result.returncode != 0:
            print(f"❌ Tests failed in {module}")
            return False
    
    print("✅ All unit tests passed!")
    return True


def run_integration_tests():
    """Run integration tests for Jira report system."""
    print("🔗 Running integration tests...")
    
    result = subprocess.run([
        sys.executable, "-m", "unittest", 
        "tests.integration.test_jira_report_system_integration", "-v"
    ], capture_output=False)
    
    if result.returncode != 0:
        print("❌ Integration tests failed")
        return False
    
    print("✅ Integration tests passed!")
    return True


def run_coverage_report():
    """Run tests with coverage report."""
    print("📊 Running tests with coverage...")
    
    try:
        # Install coverage if not available
        subprocess.run([sys.executable, "-m", "pip", "install", "coverage"], check=True)
        
        # Run tests with coverage
        result = subprocess.run([
            sys.executable, "-m", "coverage", "run", "--source=jira_telegram_bot", 
            "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"
        ], capture_output=False)
        
        if result.returncode != 0:
            print("❌ Coverage tests failed")
            return False
        
        # Generate coverage report
        subprocess.run([sys.executable, "-m", "coverage", "report", "--show-missing"])
        subprocess.run([sys.executable, "-m", "coverage", "html", "-d", "reports/coverage"])
        
        print("✅ Coverage report generated in reports/coverage/")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Coverage failed: {e}")
        return False


def main():
    """Main test runner."""
    print("🚀 Jira Report System Test Suite")
    print("=" * 50)
    
    # Ensure reports directory exists
    Path("reports").mkdir(exist_ok=True)
    
    success = True
    
    if "--unit" in sys.argv or "--all" in sys.argv:
        success &= run_unit_tests()
    
    if "--integration" in sys.argv or "--all" in sys.argv:
        success &= run_integration_tests()
    
    if "--coverage" in sys.argv or "--all" in sys.argv:
        success &= run_coverage_report()
    
    if not any(arg in sys.argv for arg in ["--unit", "--integration", "--coverage", "--all"]):
        print("Usage: python run_tests.py [--unit] [--integration] [--coverage] [--all]")
        return
    
    if success:
        print("\n🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
