# SynthPM Enhanced Features - Implementation Guide

## تغییرات اعمال شده

### 1. ✅ ایجاد دوگانه تسک‌ها در برد PM Board و Developers Board
- تسک‌ها به صورت خودکار در برد **PM Board** ایجاد می‌شوند
- زمانی که اسپرینت مشخص شود، تسک مربوطه در برد **Developers Board** ایجاد می‌شود
- لینک دوطرفه بین PM Board و Developers Board برقرار می‌شود

### 2. ✅ مدیریت اسپرینت‌ها
- الگوی اسپرینت: `<sprint-id>: <Persian-date start>: <Persian-date end>`
- مثال: `Sprint-1: ۱۴۰۳/۰۸/۰۱: ۱۴۰۳/۰۸/۰۷`
- تسک Developers Board فقط زمانی ایجاد می‌شود که اسپرینت معتبر مشخص شده باشد

### 3. ✅ Linked Issues بین PM Board و Developers Board
- هر تسک Developers Board به تسک PM Board مربوطه لینک می‌شود
- شماره تسک Developers Board در لیبل تسک PM Board اضافه می‌شود
- فرمت لیبل: `Developers Board-{issue_key}`

### 4. ✅ اختصاص افراد به استوری‌ها
- افراد تعریف شده در ستون‌های مختلف گوگل شیت به استوری Developers Board اختصاص داده می‌شوند
- نگاشت نام‌های فارسی به username های Jira
- اولین فرد در لیست به عنوان assignee اصلی انتخاب می‌شود

```python
# نگاشت افراد
people_mapping = {
    "kazemi": "ali.kazemi",
    "mousavi": "mousavi",
    "moradi": "moradi",
    # ... سایر افراد
}
```

### 5. ✅ همگام‌سازی ددلاین
- ددلاین‌ها بین گوگل شیت، PM Board و Developers Board همگام می‌شوند
- تغییر در هر یک از طرف‌ها باعث بروزرسانی سایر طرف‌ها می‌شود

### 6. ✅ کسر زمان از Story Points اصلی
- زمان ثبت شده در برد Developers Board از Story Points اصلی PM Board کسر می‌شود
- بروزرسانی گوگل شیت با ساعت‌های باقی‌مانده

### 7. ✅ پست تلگرام فقط برای Release Notes
- دیگر تسک‌های ParsChat Features مستقیماً در تلگرام پست نمی‌شوند
- فقط Release Notes در تلگرام منتشر می‌شوند
- امکان ویرایش Release Notes در تلگرام

### 8. ✅ پاک‌سازی تسک‌های حذف شده
- سیستم تسک‌هایی که از گوگل شیت حذف شده‌اند را شناسایی می‌کند
- (نیاز به پیاده‌سازی کامل: حذف از Jira)

## نحوه استفاده

### راه‌اندازی
```bash
# همگام‌سازی یکباره
python scripts/run_synth_parschat.py sync

# سرویس پس‌زمینه
python scripts/run_synth_parschat.py service

# تست اتصالات
python scripts/run_synth_parschat.py test
```

### گوگل شیت Setup
1. **ورک‌شیت ParsChat Features**: حاوی تسک‌ها و فیچرها
2. **ورک‌شیت Release Notes**: حاوی نسخه‌های منتشرشده

### ستون‌های مورد نیاز در ParsChat Features:
- وظیفه (Task Title)
- Epic
- ریلیز (Release)
- اولویت (Priority)
- وضعیت (Status)
- ETA(h)
- Total (h)
- اسپرینت (Sprint)
- ددلاین (Deadline)
- ستون‌های افراد (کاظمی، موسوی، مرادی، ...)

### فرمت اسپرینت:
```
Sprint-1: ۱۴۰۳/۰۸/۰۱: ۱۴۰۳/۰۸/۰۷
Sprint-2: ۱۴۰۳/۰۸/۰۸: ۱۴۰۳/۰۸/۱۴
```

## API Endpoints

### همگام‌سازی دستی
```http
POST /synth-parschat/sync
```

### Webhook های Jira
```http
POST /synth-parschat/jira-webhook
```

### بروزرسانی گوگل شیت
```http
POST /synth-parschat/sheet-update
{
    "row_number": 5,
    "updates": {
        "status": "۶",
        "deadline": "2024-01-15"
    }
}
```

## Release Notes Format

### ستون‌های مورد نیاز:
- ردیف
- ریلیز اصلی (V 1.0.0)
- اجزای ریلیز
- شرح
- اهداف
- فرایند تحویل
- فرایند تست

### فرمت پیام تلگرام:
```
🚀 **نسخه جدید منتشر شد!**

📋 **نسخه:** V 1.0.0
🔧 **اجزای ریلیز:** فروشنده پایه مشابه وردست

📝 **شرح:**
هدف این است که بتوانیم فروشنده پایه را تا حد ممکن مشابه وردست پیاده سازی کنیم

🎯 **اهداف:**
1. پاسخ مناسب به سوالات عمومی
2. پاسخ به سوالات اشتباه نام محصول
...

🏷️ #V_1_0_0 #Release
```

## Environment Variables

```bash
# Google Sheets
SYNTH_PM_GOOGLE_SHEETS_ID=your_sheet_id
SYNTH_PM_GOOGLE_SHEETS_TOKEN_PATH=parschat-token.json

# Jira Projects
SYNTH_PM_JIRA_PROJECT_KEY=PM Board
SYNTH_PM_PROJECT_KEY=Developers Board

# Telegram
SYNTH_PM_TELEGRAM_BOT_TOKEN=your_bot_token
SYNTH_PM_TELEGRAM_CHANNEL_ID=your_channel_id
SYNTH_PM_TELEGRAM_GROUP_ID=your_group_id

# Sync Settings
SYNTH_PM_SYNC_INTERVAL_MINUTES=5
```

## گردش کار (Workflow)

### ایجاد تسک جدید:
1. کاربر تسک جدید در گوگل شیت ایجاد می‌کند
2. سیستم تسک را در برد PM Board ایجاد می‌کند
3. اگر اسپرینت مشخص باشد، تسک در برد Developers Board نیز ایجاد می‌شود
4. لینک بین دو تسک برقرار می‌شود
5. افراد مشخص شده اختصاص داده می‌شوند

### بروزرسانی تسک:
1. تغییر در گوگل شیت یا Jira
2. همگام‌سازی دوطرفه
3. بروزرسانی assignees و ددلاین‌ها
4. ثبت تایم در Developers Board → کسر از PM Board story points

### انتشار Release:
1. ایجاد ردیف جدید در Release Notes
2. پست خودکار در کانال تلگرام
3. ثبت message ID برای امکان ویرایش
4. ویرایش در شیت → ویرایش پیام تلگرام

## نکات مهم

- **شنبه تا جمعه**: اسپرینت‌ها از شنبه شروع و جمعه خاتمه می‌یابند
- **ID یکتا**: هر تسک گوگل شیت ID یکتا دارد که با Jira تطبیق می‌کند
- **Time Tracking**: زمان‌ثبتی در Developers Board از story points اصلی کسر می‌شود
- **Telegram**: فقط Release Notes در تلگرام پست می‌شوند، نه تسک‌های معمولی

## مسائل باقی‌مانده برای پیاده‌سازی

1. **حذف فیزیکی تسک‌ها**: پیاده‌سازی حذف تسک‌های Jira هنگام حذف از گوگل شیت
2. **Sprint Management**: اتصال کامل به سیستم اسپرینت Jira
3. **User Mapping**: تنظیم دقیق نگاشت نام‌های فارسی به Jira usernames
4. **Time Tracking API**: پیاده‌سازی کامل worklog API در Jira repository

```bash
# برای تست عملکرد
python scripts/run_synth_parschat.py test
```
