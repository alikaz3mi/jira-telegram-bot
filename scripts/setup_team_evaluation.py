#!/usr/bin/env python3
"""Setup script for team evaluation feature."""

import os
import sys
from pathlib import Path

def setup_team_evaluation():
    """Set up the team evaluation feature."""
    
    print("🚀 Setting up Team Evaluation feature...")
    
    # Check required directories
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data" / "storage"
    config_dir = project_root / "config"
    
    # Create directories if they don't exist
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"✅ Created directories: {data_dir}, {config_dir}")
    
    # Check for example files
    calendar_example = data_dir / "2024.json.example"
    config_example = config_dir / "team_evaluation.env.example"
    
    if calendar_example.exists():
        print(f"📅 Calendar example available: {calendar_example}")
        print("   Copy to 2024.json and customize for your holidays")
    
    if config_example.exists():
        print(f"⚙️  Config example available: {config_example}")
        print("   Copy settings to your .env file")
    
    # Check environment variables
    required_env_vars = [
        "TEAM_EVALUATION_SHEET_ID"
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️  Missing required environment variables: {', '.join(missing_vars)}")
        print("   Please set these in your .env file")
    else:
        print("✅ All required environment variables are set")
    
    # Try to import the main components
    try:
        sys.path.insert(0, str(project_root))
        from jira_telegram_bot.config_dependency_injection import configure_container
        from jira_telegram_bot.use_cases.team_evaluation import SprintClosedTeamEvaluationUseCase
        
        container = configure_container()
        use_case = container[SprintClosedTeamEvaluationUseCase]
        print("✅ Team evaluation components loaded successfully")
        
    except Exception as e:
        print(f"❌ Error loading team evaluation components: {e}")
        return False
    
    print("\n🎉 Team Evaluation setup complete!")
    print("\nNext steps:")
    print("1. Configure your Google Sheets ID in TEAM_EVALUATION_SHEET_ID")
    print("2. Set up calendar data in data/storage/YYYY.json")
    print("3. Configure Jira webhooks to send sprint events")
    print("4. Test with: python scripts/test_team_evaluation.py")
    
    return True

if __name__ == "__main__":
    success = setup_team_evaluation()
    sys.exit(0 if success else 1)
