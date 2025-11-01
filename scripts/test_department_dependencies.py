#!/usr/bin/env python
"""Test department dependencies parsing and calculation with actual data."""
import asyncio
from datetime import datetime
from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.adapters.repositories.synth_pm_repository import SynthPMRepository
from jira_telegram_bot.entities.synth_pm.department_dependency_calculator import DepartmentDependencyCalculator

async def test_dept_deps():
    """Test department dependencies feature with real data."""
    print("\n" + "="*80)
    print("DEPARTMENT DEPENDENCIES FEATURE TEST")
    print("="*80 + "\n")
    
    try:
        # Get repository
        container = get_container()
        repo = container[SynthPMRepository]
        
        # Get all features
        features = await repo.get_developer_board_features()
        print(f"✅ Loaded {len(features)} features from Google Sheets\n")
        
        # Filter features with dependencies
        features_with_deps = [f for f in features if f.department_deps and f.department_deps.strip()]
        print(f"📊 Features with department dependencies: {len(features_with_deps)}\n")
        
        if not features_with_deps:
            print("⚠️  No features found with department dependencies!")
            print("\n💡 To test this feature, add a 'Department Deps' value in your sheet:")
            print("   Example: 'UI/UX blocks Frontend'")
            print("   OR:      'Backend blocks AI'\n")
            return
        
        # Test parsing and calculations
        print("="*80)
        print("TESTING DEPENDENCY PARSING AND DATE CALCULATIONS")
        print("="*80 + "\n")
        
        for i, feature in enumerate(features_with_deps[:5], 1):
            print(f"\n{'─'*80}")
            print(f"Feature {i}: {feature.task_title}")
            print(f"{'─'*80}")
            print(f"📍 Row: {feature.sheet_row_number}")
            print(f"📝 Department Deps: '{feature.department_deps}'")
            
            # Parse dependencies
            parsed_deps = DepartmentDependencyCalculator.parse_department_deps(feature.department_deps)
            print(f"\n✅ Parsed Dependencies:")
            if parsed_deps:
                for blocked, blockers in parsed_deps.items():
                    blocker_list = ", ".join(blockers)
                    print(f"   • {blocker_list} → blocks → {blocked}")
            else:
                print("   ⚠️  No valid dependencies parsed")
            
            # Show department hours
            print(f"\n⏱️  Department Hours:")
            dept_hours = {}
            if feature.ai and feature.ai > 0:
                dept_hours["AI"] = feature.ai
                print(f"   • AI: {feature.ai}h")
            if feature.backend and feature.backend > 0:
                dept_hours["Backend"] = feature.backend
                print(f"   • Backend: {feature.backend}h")
            if feature.frontend and feature.frontend > 0:
                dept_hours["Frontend"] = feature.frontend
                print(f"   • Frontend: {feature.frontend}h")
            if feature.ui_ux and feature.ui_ux > 0:
                dept_hours["UI/UX"] = feature.ui_ux
                print(f"   • UI/UX: {feature.ui_ux}h")
            if feature.devops and feature.devops > 0:
                dept_hours["DevOps"] = feature.devops
                print(f"   • DevOps: {feature.devops}h")
            
            if not dept_hours:
                print("   ⚠️  No department hours specified")
            
            # Calculate dates if deadline exists
            if feature.deadline and dept_hours:
                print(f"\n📅 Deadline: {feature.deadline.strftime('%Y-%m-%d')}")
                
                try:
                    # Get holidays
                    from jira_telegram_bot.adapters.repositories.calendar.json_calendar_repository import JsonCalendarRepository
                    calendar_repo = JsonCalendarRepository()
                    current_year = datetime.now().year
                    holidays = await calendar_repo.get_holidays(current_year)
                    holidays.update(await calendar_repo.get_holidays(current_year + 1))
                except:
                    holidays = set()
                
                # Calculate department deadlines
                dept_deadlines = DepartmentDependencyCalculator.calculate_department_deadlines(
                    feature.deadline,
                    parsed_deps,
                    dept_hours,
                    holidays,
                )
                
                if dept_deadlines:
                    print(f"\n📊 Calculated Department Schedules:")
                    print(f"   {'Department':<15} {'Start Date':<12} {'End Date':<12} {'Duration'}")
                    print(f"   {'-'*15} {'-'*12} {'-'*12} {'-'*8}")
                    
                    for dept, dates in sorted(dept_deadlines.items()):
                        start = dates['start'].strftime('%Y-%m-%d')
                        end = dates['end'].strftime('%Y-%m-%d')
                        duration_days = (dates['end'] - dates['start']).days + 1
                        print(f"   {dept:<15} {start:<12} {end:<12} {duration_days} days")
                    
                    # Show dependency flow
                    if parsed_deps:
                        print(f"\n🔗 Dependency Flow:")
                        for blocked, blockers in parsed_deps.items():
                            for blocker in blockers:
                                if blocker in dept_deadlines and blocked in dept_deadlines:
                                    blocker_end = dept_deadlines[blocker]['end'].strftime('%m/%d')
                                    blocked_start = dept_deadlines[blocked]['start'].strftime('%m/%d')
                                    print(f"   {blocker} (ends {blocker_end}) → {blocked} (starts {blocked_start})")
                else:
                    print("\n⚠️  Could not calculate department deadlines")
            else:
                if not feature.deadline:
                    print(f"\n⚠️  No deadline specified")
                if not dept_hours:
                    print(f"\n⚠️  No department hours specified")
            
            # Show Jira issues
            print(f"\n🎫 Jira Issues:")
            print(f"   • PM Board: {feature.jira_issue_key or 'Not created'}")
            print(f"   • Developer Board: {feature.developer_board_issue_key or 'Not created'}")
        
        print(f"\n{'='*80}")
        print("✅ TEST COMPLETED SUCCESSFULLY!")
        print("="*80 + "\n")
        
        # Summary
        features_with_issues = [f for f in features_with_deps if f.developer_board_issue_key]
        print(f"📈 Summary:")
        print(f"   • Total features with dependencies: {len(features_with_deps)}")
        print(f"   • Features with Jira tasks created: {len(features_with_issues)}")
        print(f"   • Features pending creation: {len(features_with_deps) - len(features_with_issues)}")
        
        if len(features_with_deps) > len(features_with_issues):
            print(f"\n💡 Tip: Run 'python scripts/run_synth_pm.py sync' to create missing Jira tasks")
        
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_dept_deps())
    exit(0 if success else 1)
