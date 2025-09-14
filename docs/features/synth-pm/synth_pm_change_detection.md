# سیستم Change Detection برای SynthPM

## خلاصه

سیستم Change Detection برای بهینه‌سازی فرآیند تولید مستندات AI در پروژه SynthPM طراحی شده است. این سیستم به جای تولید مجدد مستندات برای همه فیچرها در هر sync، تنها برای فیچرهایی که واقعاً تغییر کرده‌اند و محتوای مناسب دارند، مستندات جدید تولید می‌کند.

## مشکل

سؤال شما: **"اولا به چه شکل مقایسه میکنی و متوجه این تغییر میشی؟"**

قبل از این سیستم، هر بار sync انجام می‌شد، برای تمام فیچرها prompt های AI اجرا می‌شدند که:
- منابع غیرضروری مصرف می‌کرد
- زمان sync را افزایش می‌داد
- هزینه AI calls را بالا می‌برد
- برای فیچرهای خالی از محتوا نیز اجرا می‌شد

## راه‌حل

### 1. شرط تولید مستندات

مستندات تنها در صورتی تولید می‌شود که فیچر حداقل یکی از این فیلدها را داشته باشد:
- `description` (توضیحات)
- `acceptance_criteria` (معیارهای پذیرش)
- `test_cases` (تست‌ها)

```python
# بررسی محتوای فیچر
has_description = bool(feature.description and feature.description.strip())
has_acceptance_criteria = bool(feature.acceptance_criteria and feature.acceptance_criteria.strip())
has_test_cases = bool(feature.test_cases and feature.test_cases.strip())

if not (has_description or has_acceptance_criteria or has_test_cases):
    return {"status": "skipped", "message": "No content available for documentation generation"}
```

### 2. ایجاد Snapshot از محتوای فیچرها

```python
class FeatureSnapshot(BaseModel):
    sheet_row_number: int
    content_hash: str  # SHA-256 hash از فیلدهای Google Sheet
    last_updated: datetime
    last_documentation_generated: Optional[datetime]
    jira_issue_key: Optional[str]
```

### 3. محاسبه Hash برای تشخیص تغییرات Google Sheet

```python
@classmethod
def from_feature(cls, feature: SynthPMFeatureEntity) -> "FeatureSnapshot":
    # فیلدهای Google Sheet که توسط PO/PM آپدیت می‌شوند
    relevant_fields = {
        "task_title": feature.task_title or "",
        "description": feature.description or "",
        "acceptance_criteria": feature.acceptance_criteria or "",
        "test_cases": feature.test_cases or "",
        "epic": feature.epic or "",
        "departments": feature.departments or "",
        "priority": feature.priority or "",
        "necessity": feature.necessity or "",
    }

    # ایجاد hash منحصر به فرد از تغییرات Google Sheet
    content_str = "|".join(f"{k}:{v}" for k, v in sorted(relevant_fields.items()))
    content_hash = hashlib.sha256(content_str.encode()).hexdigest()
```

### 4. الگوریتم تشخیص تغییرات

```python
def detect_changes(self, current_features: List[SynthPMFeatureEntity]) -> Dict[str, List]:
    """
    دسته‌بندی فیچرها بر اساس وضعیت تغییرات Google Sheet:
    - new: فیچرهای جدید (نیاز به Jira ticket + مستندات)
    - modified: فیچرهای تغییر یافته در Google Sheet (آپدیت Jira + مستندات)
    - unchanged: فیچرهای بدون تغییر
    - needs_docs: فیچرهایی که نیاز به تولید مستندات دارند
    """
```

### 5. بهینه‌سازی فرآیند Sync

```python
async def sync_developer_board_features(self) -> Dict[str, Any]:
    # دریافت فیچرهای فعلی از Google Sheets
    features = await self.repository.get_developer_board_features()

    # تشخیص تغییرات Google Sheet
    changes = await self.repository.detect_feature_changes(features)

    # پردازش هوشمند
    for feature in changes["new"]:
        # ایجاد Jira ticket + تولید مستندات (اگر محتوا داشته باشد)

    for feature in changes["modified"]:
        # آپدیت Jira ticket فقط

    for feature in changes["needs_docs"]:
        # تولید مستندات فقط (اگر محتوا داشته باشد)
```

### 6. عدم آپدیت Google Sheets پس از تولید مستندات

مستندات تولید شده تنها در Jira قرار می‌گیرد و Google Sheets آپدیت نمی‌شود:

```python
# فقط Jira آپدیت می‌شود
await self.repository.update_jira_task_description(
    feature.developer_board_issue_key,
    documentation,
)

# Google Sheets آپدیت نمی‌شود - PO/PM خودشان محتوا اضافه می‌کنند
```

## مزایا

### 1. **شرایط هوشمند تولید مستندات**
- فقط فیچرهای با محتوا پردازش می‌شوند
- عدم هدر رفت منابع برای فیچرهای خالی

### 2. **تمرکز بر تغییرات Google Sheet**
- تشخیص تغییرات بر اساس ورودی PO/PM
- عدم وابستگی به تغییرات سیستمی

### 3. **کارایی بالا**
- تنها فیچرهای تغییر یافته پردازش می‌شوند
- کاهش چشمگیر تعداد AI calls

### 4. **صرفه‌جویی در منابع**
- کاهش مصرف CPU و Memory
- کاهش هزینه API calls

### 5. **سرعت بیشتر**
- زمان sync کمتر
- پاسخ‌دهی بهتر سیستم

## نحوه استفاده

### 1. Sync عادی (هوشمند)
```bash
python scripts/run_synth_pm.py --sync-once
```

### 2. اجبار به تولید مجدد مستندات
```python
await synth_pm_usecase.force_documentation_regeneration([10, 11, 12])
```

### 3. مشاهده وضعیت تغییرات
```python
changes = await repository.detect_feature_changes(current_features)
print(f"جدید: {len(changes['new'])}")
print(f"تغییر یافته: {len(changes['modified'])}")
print(f"نیاز به مستندات: {len(changes['needs_docs'])}")
```

## فلوی کاری جدید

### PO/PM Workflow:
1. **محتوا در Google Sheets اضافه می‌کند** (description, acceptance_criteria, test_cases)
2. **سیستم تغییرات را تشخیص می‌دهد**
3. **مستندات AI تولید شده در Jira قرار می‌گیرد**
4. **Google Sheets دست نخورده باقی می‌ماند**

### Development Team Workflow:
1. **مستندات کامل را در Jira مشاهده می‌کند**
2. **بر اساس User Stories و Acceptance Criteria کد می‌نویسد**
3. **Test Scenarios را در تست‌ها پیاده‌سازی می‌کند**

## فایل‌های مرتبط

- `entities/synth_pm/change_tracker.py` - مدل‌های اصلی
- `adapters/repositories/synth_pm_repository.py` - متدهای repository
- `use_cases/synth_pm_usecase.py` - منطق business
- `data/storage/synth_pm_change_tracker.json` - ذخیره snapshots
- `tests/unit_tests/use_cases/test_synth_pm_documentation_conditions.py` - تست‌های شرایط

## تنظیمات

مسیر فایل change tracker در repository تنظیم می‌شود:
```python
self.change_tracker_file = Path(data_folder) / "synth_pm_change_tracker.json"
```

## نتیجه‌گیری

این سیستم به سؤال شما **"به چه شکل مقایسه میکنی و متوجه این تغییر میشی؟"** پاسخ کامل می‌دهد:

1. **مقایسه**: از طریق Hash محتوای فیلدهای Google Sheet
2. **تشخیص تغییر**: مقایسه hash فعلی با snapshot قبلی
3. **شرط تولید**: فقط اگر فیچر محتوا داشته باشد (description/acceptance_criteria/test_cases)
4. **تصمیم‌گیری هوشمند**: تولید مستندات فقط در صورت نیاز
5. **ذخیره وضعیت**: نگهداری history برای sync های آینده
6. **عدم آپدیت Google Sheets**: محتوا توسط PO/PM مدیریت می‌شود

سیستم حالا **هوشمندتر، کارآمدتر و مناسب workflow واقعی** عمل می‌کند! 🚀
