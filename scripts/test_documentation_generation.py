#!/usr/bin/env python3
"""مثال برای تست تولید مستندات feature در SynthPM."""

from __future__ import annotations

import asyncio
import sys

from jira_telegram_bot import LOGGER
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.synth_pm.pm_board_features import SynthPMFeatureEntity
from jira_telegram_bot.use_cases.synth_pm_usecase import SynthPMUseCase


async def test_documentation_generation():
    """تست تولید مستندات برای یک feature نمونه."""
    try:
        # Setup container and dependencies
        container = get_container()
        synth_pm_use_case = container[SynthPMUseCase]

        # Create a sample feature
        sample_feature = SynthPMFeatureEntity(
            row_number=999,
            sheet_row_number=999,
            task_title="پیاده‌سازی ورود کاربران با احراز هویت دو مرحله‌ای",
            description="یک سیستم ورود امن برای کاربران که شامل احراز هویت دو مرحله‌ای (2FA) است",
            epic="احراز هویت و امنیت",
            departments="Backend,Frontend,UI/UX",
            status="۵",  # آماده پیاده سازی فنی
            priority="بالا",
            necessity="ضروری",
        )

        # Get project info
        project_info = {
            "description": "سامانه چندکاناله پارس‌چت",
            "keywords": ["AI-Chatbot", "NLP", "Omnichannel-Support", "Security"],
        }

        print("🚀 شروع تولید مستندات...")
        print(f"📝 Feature: {sample_feature.task_title}")
        print(f"🏗️ Epic: {sample_feature.epic}")
        print(f"👥 Departments: {sample_feature.departments}")
        print()

        # Generate documentation
        result = await synth_pm_use_case.generate_feature_documentation(
            sample_feature,
            project_info,
        )

        if result["status"] == "success":
            print("✅ مستندات با موفقیت تولید شد!")
            print("\n" + "="*80)
            print("📋 مستندات تولید شده:")
            print("="*80)
            print(result["documentation"])
            print("="*80)
            print()
            
            # Show metadata
            print("📊 اطلاعات اضافی:")
            print(f"🔤 یوزر استوری: {len(result['user_story'])} کاراکتر")
            print(f"✅ معیارهای پذیرش: {len(result['acceptance_criteria'])} مورد")
            print(f"🔧 مراحل تحویل: {len(result['delivery_process'])} مرحله")
            print(f"🧪 تست‌ها: {len(result['test_scenarios'])} سناریو")

        else:
            print(f"❌ خطا در تولید مستندات: {result.get('message')}")
            return False

        return True

    except Exception as e:
        LOGGER.error(f"Error in documentation generation test: {e}")
        print(f"❌ خطا: {e}")
        return False


async def main():
    """Main function."""
    print("🧪 تست تولید مستندات SynthPM")
    print("=" * 50)
    
    success = await test_documentation_generation()
    
    if success:
        print("\n🎉 تست با موفقیت انجام شد!")
        sys.exit(0)
    else:
        print("\n💥 تست با شکست مواجه شد!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
