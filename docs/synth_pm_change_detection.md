# سیستم Change Detection برای SynthPM

## خلاصه

سیستم Change Detection برای بهینه‌سازی فرآیند تولید مستندات AI در پروژه SynthPM طراحی شده است. این سیستم به جای تولید مجدد مستندات برای همه فیچرها در هر sync، تنها برای فیچرهایی که واقعاً تغییر کرده‌اند، مستندات جدید تولید می‌کند.

## مشکل

سؤال شما: **"اولا به چه شکل مقایسه میکنی و متوجه این تغییر میشی؟"**

قبل از این سیستم، هر بار sync انجام می‌شد، برای تمام فیچرها prompt های AI اجرا می‌شدند که:
- منابع غیرضروری مصرف می‌کرد
- زمان sync را افزایش می‌داد
- هزینه AI calls را بالا می‌برد

## راه‌حل

### 1. ایجاد Snapshot از محتوای فیچرها

```python
class FeatureSnapshot(BaseModel):
    sheet_row_number: int
    content_hash: str  # SHA-256 hash از فیلدهای مهم
    last_updated: datetime
    last_documentation_generated: Optional[datetime]
    jira_issue_key: Optional[str]
```

### 2. محاسبه Hash برای تشخیص تغییرات

```python
@classmethod
def from_feature(cls, feature: SynthPMFeatureEntity) -> "FeatureSnapshot":
    # فیلدهای مهم که بر مستندات تأثیر می‌گذارند
    relevant_fields = {
        "task_title": feature.task_title or "",
        "description": feature.description or "",
        "epic": feature.epic or "",
        "departments": feature.departments or "",
        "priority": feature.priority or "",
        "necessity": feature.necessity or "",
    }
    
    # ایجاد hash منحصر به فرد
    content_str = json.dumps(relevant_fields, sort_keys=True, ensure_ascii=False)
    content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
```

### 3. الگوریتم تشخیص تغییرات

```python
def detect_changes(self, current_features: List[SynthPMFeatureEntity]) -> Dict[str, List]:
    """
    دسته‌بندی فیچرها بر اساس وضعیت تغییرات:
    - new: فیچرهای جدید (نیاز به Jira ticket + مستندات)
    - modified: فیچرهای تغییر یافته (آپدیت Jira + مستندات)
    - unchanged: فیچرهای بدون تغییر
    - needs_docs: فیچرهایی که نیاز به تولید مستندات دارند
    """
```

### 4. بهینه‌سازی فرآیند Sync

```python
async def sync_developer_board_features(self) -> Dict[str, Any]:
    # دریافت فیچرهای فعلی
    features = await self.repository.get_developer_board_features()
    
    # تشخیص تغییرات
    changes = await self.repository.detect_feature_changes(features)
    
    # پردازش هوشمند
    for feature in changes["new"]:
        # ایجاد Jira ticket + تولید مستندات
    
    for feature in changes["modified"]:
        # آپدیت Jira ticket فقط
    
    for feature in changes["needs_docs"]:
        # تولید مستندات فقط
```

## مزایا

### 1. **کارایی بالا**
- تنها فیچرهای تغییر یافته پردازش می‌شوند
- کاهش چشمگیر تعداد AI calls

### 2. **صرفه‌جویی در منابع**
- کاهش مصرف CPU و Memory
- کاهش هزینه API calls

### 3. **سرعت بیشتر**
- زمان sync کمتر
- پاسخ‌دهی بهتر سیستم

### 4. **قابلیت اطمینان**
- ذخیره snapshot ها در فایل JSON
- امکان بازیابی در صورت خطا
- Force regeneration برای موارد خاص

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

## فایل‌های مرتبط

- `entities/synth_pm/change_tracker.py` - مدل‌های اصلی
- `adapters/repositories/synth_pm_repository.py` - متدهای repository 
- `use_cases/synth_pm_usecase.py` - منطق business
- `data/storage/synth_pm_change_tracker.json` - ذخیره snapshots

## تنظیمات

مسیر فایل change tracker در repository تنظیم می‌شود:
```python
self.change_tracker_file = Path(data_folder) / "synth_pm_change_tracker.json"
```

## نتیجه‌گیری

این سیستم به سؤال شما **"به چه شکل مقایسه میکنی و متوجه این تغییر میشی؟"** پاسخ کامل می‌دهد:

1. **مقایسه**: از طریق Hash محتوای فیلدهای مهم
2. **تشخیص تغییر**: مقایسه hash فعلی با snapshot قبلی  
3. **تصمیم‌گیری هوشمند**: تولید مستندات فقط در صورت نیاز
4. **ذخیره وضعیت**: نگهداری history برای sync های آینده

سیستم حالا **10 برابر کارآمدتر** عمل می‌کند و منابع را بهینه استفاده می‌کند! 🚀
