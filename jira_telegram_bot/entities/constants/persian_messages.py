"""Persian messages for daily task tracking."""

# Task status questions
TASK_NOT_STARTED = "چرا این تسک را شروع نکرده‌اید؟"
HOURS_TODAY = "چند ساعت امروز روی این تسک کار کرده‌اید؟"
WORKLOG_MISSING = "این تسک تکمیل شده است. چند ساعت روی آن کار کرده‌اید؟"
STATUS_REGRESSED = "⚠️ تسک شما از Review به Backlog برگشت"

# Task header
TASK_HEADER = """
📋 تسک: {issue_key}
� لینک: {issue_url}
📝 عنوان: {summary}
📊 وضعیت: {status}
📅 اسپرینت: {sprint_name}
"""

TASK_HEADER_WITH_DATES = """
📋 تسک: {issue_key}
🔗 لینک: {issue_url}
📝 عنوان: {summary}
📊 وضعیت: {status}
📅 اسپرینت: {sprint_name}
🎯 شروع هدف: {target_start}
🏁 پایان هدف: {target_end}
"""

TASK_DESCRIPTION = """
📄 توضیحات: {description}
"""

# Delay reasons (buttons)
DELAY_WAITING_APPROVAL = "منتظر تایید"
DELAY_TECHNICAL_BLOCKER = "مشکل فنی"
DELAY_OTHER_PRIORITIES = "اولویت دیگر"
DELAY_MISSING_REQUIREMENTS = "نیازمندی ناقص"
DELAY_DEPENDENCY_NOT_READY = "وابستگی آماده نیست"
DELAY_OTHER = "سایر"

# Hours buttons
HOURS_1 = "۱ ساعت"
HOURS_2 = "۲ ساعت"
HOURS_3 = "۳ ساعت"
HOURS_4 = "۴ ساعت"
HOURS_6 = "۶ ساعت"
HOURS_8 = "۸ ساعت"
HOURS_CUSTOM = "سایر"

# Actions
REQUEST_SUBTASKS = "درخواست زیرتسک"
SKIP_TASK = "رد کردن"

# Confirmations
WORKLOG_RECORDED = "✅ ثبت شد: {} ساعت"
DELAY_RECORDED = "✅ دلیل تاخیر ثبت شد"
HOURS_RECORDED = "✅ زمان ثبت شد: {} ساعت"
SUBTASK_REQUEST_SENT = "✅ درخواست زیرتسک به مدیر محصول ارسال شد"
TASK_SKIPPED = "رد شد"

# Custom input prompts
ENTER_CUSTOM_HOURS = "لطفاً تعداد ساعات را وارد کنید (عدد):"
ENTER_CUSTOM_DELAY_REASON = "لطفاً دلیل تاخیر را بنویسید:"

# Status regression notification
STATUS_REGRESSION_MESSAGE = """
⚠️ تسک شما به Backlog برگشت

📋 تسک: {issue_key}
📝 عنوان: {summary}
📊 از {from_status} به {to_status}
👤 توسط: {changed_by}
🕐 زمان: {changed_at}
{reason_text}
"""

REASON_TEXT = "📝 دلیل: {reason}"

# PO notification
PO_SUBTASK_REQUEST = """
📋 درخواست ایجاد زیرتسک

👤 از طرف: {assignee}
📋 برای تسک: {issue_key}
📝 عنوان: {summary}

لطفاً زیرتسک‌های لازم را ایجاد کنید.
"""

# Daily summary
DAILY_SUMMARY_HEADER = "📊 گزارش روزانه تسک‌ها"
NO_TASKS_TODAY = "✅ همه تسک‌ها وضعیت مناسبی دارند!"
TASKS_NEEDING_ATTENTION = "⚠️ تسک‌های نیازمند توجه:"

# Error messages
ERROR_RECORDING_WORKLOG = "❌ خطا در ثبت worklog"
ERROR_INVALID_HOURS = "❌ عدد وارد شده معتبر نیست"
ERROR_FETCHING_TASKS = "❌ خطا در دریافت تسک‌ها"

# Welcome message
DAILY_CHECK_START = """
سلام! 👋
زمان بررسی روزانه تسک‌های شماست.
لطفاً به سوالات زیر پاسخ دهید:
"""

DAILY_CHECK_COMPLETE = """
✅ بررسی روزانه تکمیل شد!
از همکاری شما متشکریم.
"""

# Generic messages
DAILY_TASK_CHECK_TITLE = "بررسی روزانه تسک‌ها"
THANK_YOU = "متشکریم!"
ERROR_MESSAGE = "❌ خطا رخ داد"

# ── free-text worklog reporting ──────────────────────
WORKLOG_PARSING = "⏳ در حال بررسی گزارش شما..."
WORKLOG_NO_TASKS = "❌ تسک بازی برای شما پیدا نشد."
WORKLOG_NOT_UNDERSTOOD = (
    "متوجه نشدم چقدر و روی چه کاری وقت گذاشتید.\n"
    "مثال: «امروز ۳ ساعت روی رفع باگ ورود کار کردم»"
)
WORKLOG_CONFIRM_HEADER = "📝 این موارد را ثبت کنم؟"
WORKLOG_CONFIRM_LINE = "• {hours} ساعت — {issue_key}: {summary}"
WORKLOG_CONFIRM_BUTTON = "✅ ثبت کن"
WORKLOG_CANCEL_BUTTON = "❌ لغو"
WORKLOG_CANCELLED = "لغو شد. چیزی ثبت نشد."
WORKLOG_SAVED_HEADER = "✅ ثبت شد:"
WORKLOG_SAVED_LINE = "• {hours} ساعت روی {issue_key}"
WORKLOG_SAVE_FAILED_LINE = "• ❌ {issue_key} ثبت نشد"
WORKLOG_OTHER_TASK_BUTTON = "🔍 تسک دیگر"
WORKLOG_SKIP_SPLIT_BUTTON = "⏭ رد کن"
WORKLOG_SPLIT_SKIPPED = "این مورد ثبت نشد."
QUESTION_THINKING = "🤔 در حال بررسی تسک‌های شما..."
QUESTION_NO_ANSWER = "نتوانستم پاسخی پیدا کنم."
FREE_TEXT_HELP = (
    "سلام! 👋\n"
    "می‌توانید زمان کارتان را بگویید — مثلاً «امروز ۳ ساعت روی رفع باگ ورود کار کردم» —\n"
    "یا درباره تسک‌هایتان بپرسید، مثلاً «این هفته چه تسک‌هایی دارم؟»"
)
WORKLOG_NEEDS_DETAIL = (
    "باشه! بگویید چند ساعت و روی چه کاری.\n"
    "مثلاً: «۳ ساعت روی رفع باگ ورود» یا «۲ ساعت پارسچت، ۱ ساعت مستندات»"
)
