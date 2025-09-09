#!/usr/bin/env python3
"""Test script to verify Jira formatting works correctly."""

from jira_telegram_bot.entities.ai_agent_models.generate_acceptance_criteria import (
    GenerateAcceptanceCriteriaResult,
)
from jira_telegram_bot.entities.ai_agent_models.generate_test_scenarios import (
    GenerateTestScenariosResult,
    TestScenario,
)
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase

# Mock objects since we only need to test formatting
class MockRepository:
    pass

class MockGateway:
    pass

class MockSettings:
    pass

def test_jira_formatting():
    """Test that the formatting produces proper Jira markup."""
    
    # Create mock SynthPM use case (just for accessing the formatting method)
    use_case = SynthPMUseCase(
        repository=MockRepository(),
        notification_gateway=MockGateway(),
        settings=MockSettings(),
        generate_acceptance_criteria_use_case=None,
        generate_test_scenarios_use_case=None,
    )
    
    # Create test data
    acceptance_result = GenerateAcceptanceCriteriaResult(
        user_story="به‌عنوان یک کاربر که در سایت با ووکامرس سفارش داده‌ام، می‌خواهم با وارد کردن شماره موبایل خودم، وضعیت آخرین سفارش‌هایم را ببینم.",
        acceptance_criteria=[
            "کاربر باید بتواند اطلاعات حساب اینستاگرام خود را در صفحه اتصال وارد کند",
            "کاربران باید بتوانند اطلاعات حساب اینستاگرام خود را بررسی اطلاعات وارد کنند",
            "اتصال به سرویس اینستاگرام باید در تمام پیمان‌ها و نسخه فردی تریاقل بدون مشکل انجام شود",
        ],
        delivery_process=[
            "طراحی Schema و Migration",
            "برای دریافت و پردازش اطلاعات اینستاگرام Backend پیاده‌سازی منطق",
            "تست یکپارچگی و کارایی اینستاگرام به سرویس اینستاگرام",
            "تست کارایی برای اطمینان از جینه کارایی مناسب",
            "انتشار و تحویل صفحه اینستاگرام به محیط تولید",
        ],
        metadata={}
    )
    
    test_result = GenerateTestScenariosResult(
        test_scenarios=[
            TestScenario(
                test_number="TC-01",
                description="بررسی نمایش صحیح صفحه اتصال به سرویس‌های پارس‌چت",
                status="تعیین",
                responsible="تستر"
            ),
            TestScenario(
                test_number="TC-02",
                description="وارد کردن اطلاعات حساب اینستاگرام (نام کاربری و رمز عبور) و بررسی اینکه اطلاعات به درستی ذخیره می‌شوند",
                status="تعیین", 
                responsible="تستر"
            ),
            TestScenario(
                test_number="TC-03",
                description="اتصال به سرویس اینستاگرام با اطلاعات صحیح و بررسی دریافت پیام تأیید اتصال",
                status="تعیین",
                responsible="تستر"
            ),
            TestScenario(
                test_number="TC-04",
                description="اتصال به سرویس اینستاگرام با اطلاعات نادرست و بررسی دریافت پیام خطای مناسب",
                status="تعیین",
                responsible="تستر"
            )
        ],
        metadata={}
    )
    
    # Test the formatting
    formatted_output = use_case._format_feature_documentation(
        acceptance_result, 
        test_result
    )
    
    print("=== FORMATTED JIRA OUTPUT ===")
    print(formatted_output)
    print("\n=== KEY FORMATTING CHECKS ===")
    
    # Check for proper Jira formatting
    checks = [
        ("h2. headers", "h2." in formatted_output),
        ("Separators ----", "----" in formatted_output),
        ("Bullet points with spaces", " * " in formatted_output),
        ("Table headers ||", "||" in formatted_output),
        ("Table rows |", formatted_output.count("|TC-") >= 4),
        ("Persian content", "یوزر استوری" in formatted_output),
        ("Checkbox symbols", "⬜" in formatted_output),
    ]
    
    for check_name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    return all(check[1] for check in checks)

if __name__ == "__main__":
    success = test_jira_formatting()
    if success:
        print("\n🎉 All formatting checks passed!")
    else:
        print("\n❌ Some formatting checks failed!")
