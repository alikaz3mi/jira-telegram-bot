# Video Upload Error Fix - Telegram 20MB Limit

## Problem

Users were experiencing errors when posting videos to Telegram channels:

```
Error processing Telegram update: Failed to get file path for file_id=BAACAgQ..., status=400
Exception: Failed to get file path for file_id=BAACAgQ..., status=400
```

**Root Cause:** Telegram Bot API has a **20MB limit** for the `getFile` method. Videos larger than this cannot be downloaded via the Bot API.

---

## Solution Implemented

### 1. Enhanced Error Messages (`__init__.py`)

**File:** `jira_telegram_bot/adapters/services/telegram/__init__.py`

**Changes:**
- Added timeout to Telegram API requests (10 seconds)
- Enhanced error messages to include Telegram's error description
- Added comments explaining common error scenarios

```python
def _get_file_path(self, token: str) -> str:
    url = f"https://api.telegram.org/bot{token}/getFile?file_id={self.file_id}"
    resp = requests.get(url, timeout=10)
    if resp.status_code == 200:
        result = resp.json()["result"]
        return result["file_path"]
    else:
        error_msg = f"Failed to get file path for file_id={self.file_id}, status={resp.status_code}"
        try:
            error_detail = resp.json()
            if "description" in error_detail:
                error_msg += f", description: {error_detail['description']}"
                # Common Telegram errors:
                # - "Bad Request: file is too big" (>20MB for getFile)
                # - "Bad Request: wrong file_id" (expired or invalid)
                # - "Unauthorized" (invalid bot token)
        except Exception:
            error_msg += f", response: {resp.text[:200]}"
        raise Exception(error_msg)
```

### 2. Graceful Error Handling (`telegram_gateway.py`)

**File:** `jira_telegram_bot/adapters/services/telegram/telegram_gateway.py`

**Changes:**
- Wrapped media download in try-except block
- Added 30-second timeout for downloads
- Logs errors but continues with ticket creation (without attachment)

```python
async def fetch_and_store_media(
    media: Any,
    session: aiohttp.ClientSession,
    storage_list: List,
    filename: str,
    token: str = None,
):
    """Fetch media from Telegram and store it in the provided storage list.
    
    Gracefully handles errors by logging and skipping files that cannot be downloaded.
    Common reasons for failure:
    - File too large (>20MB for Bot API getFile)
    - Expired file_id
    - Network issues
    """
    try:
        media_file = await media.get_file()
        file_url = f"https://api.telegram.org/file/bot{token}/{media_file.file_path}"
        async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                buffer = BytesIO(await response.read())
                storage_list.append((filename, buffer))
                LOGGER.info(f"Successfully fetched media: {filename}")
            else:
                LOGGER.error(
                    f"Failed to fetch media: {media_file.file_path} (status {response.status})",
                )
    except Exception as e:
        LOGGER.error(
            f"Error fetching media {filename}: {str(e)}. Skipping attachment.",
        )
        # Don't re-raise - we want to continue creating the ticket even if media fails
```

### 3. Pre-Download File Size Check (`create_ticket.py`)

**File:** `jira_telegram_bot/frameworks/fast_api/create_ticket.py`

**Changes:**
- Check video file size before attempting download
- Skip videos > 20MB with informative warning
- Log file size for debugging

#### For Media Groups (lines ~95-120):

```python
elif "video" in msg:
    vid = msg["video"]
    file_id = vid["file_id"]
    file_size = vid.get("file_size", 0)
    file_size_mb = file_size / (1024 * 1024) if file_size else 0
    
    # Telegram Bot API getFile has 20MB limit
    if file_size > 20 * 1024 * 1024:
        LOGGER.warning(
            f"Video file too large ({file_size_mb:.2f}MB > 20MB limit). "
            f"Skipping attachment. Consider using direct download or file hosting."
        )
        continue
    
    LOGGER.info(f"Processing video: file_id={file_id}, size={file_size_mb:.2f}MB")
    mock_media = MockTelegramVideo(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
    await fetch_and_store_media(...)
```

#### For Single Videos (lines ~195-220):

```python
elif "video" in channel_post:
    vid = channel_post["video"]
    file_id = vid["file_id"]
    file_size = vid.get("file_size", 0)
    file_size_mb = file_size / (1024 * 1024) if file_size else 0
    
    # Telegram Bot API getFile has 20MB limit
    if file_size > 20 * 1024 * 1024:
        LOGGER.warning(
            f"Video file too large ({file_size_mb:.2f}MB > 20MB limit). "
            f"Ticket will be created without video attachment. "
            f"File ID: {file_id}"
        )
    else:
        LOGGER.info(f"Processing video: file_id={file_id}, size={file_size_mb:.2f}MB")
        mock_media = MockTelegramVideo(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
        await fetch_and_store_media(...)
```

---

## Behavior After Fix

### ✅ Videos ≤ 20MB
- Video is downloaded and attached to Jira ticket
- Log: `Processing video: file_id=XXX, size=15.23MB`
- Log: `Successfully fetched media: single_video.mp4`

### ⚠️ Videos > 20MB
- Video is **skipped** (not downloaded)
- Jira ticket is **still created** with text/other attachments
- Log: `Video file too large (29.19MB > 20MB limit). Ticket will be created without video attachment.`

### ❌ Other Errors (expired file_id, network issues)
- Error is caught and logged
- Jira ticket is **still created** without the problematic attachment
- Log: `Error fetching media single_video.mp4: [error details]. Skipping attachment.`

---

## Example Log Output

### Success Case (Small Video):
```
[INFO] Processing video: file_id=BAACAgQAAyEFAA..., size=4.14MB
[INFO] Successfully fetched media: single_video.mp4
[INFO] Task created (single) successfully! Link: https://jira.../browse/PCT-1084
```

### Large Video Case:
```
[WARNING] Video file too large (29.19MB > 20MB limit). Ticket will be created without video attachment. File ID: BAACAgQAAyEFAA...
[INFO] Task created (single) successfully! Link: https://jira.../browse/PCT-1085
```

### Error Case:
```
[INFO] Processing video: file_id=BAACAgQAAyEFAA..., size=18.50MB
[ERROR] Failed to get file path for file_id=BAACAgQAAyEFAA..., status=400, description: Bad Request: file is too big
[ERROR] Error fetching media single_video.mp4: Failed to get file path for file_id=BAACAgQAAyEFAA..., status=400, description: Bad Request: file is too big. Skipping attachment.
[INFO] Task created (single) successfully! Link: https://jira.../browse/PCT-1086
```

---

## Telegram API Limits

### getFile Method
- **Maximum file size:** 20 MB
- **Applies to:** Bot API `getFile` endpoint
- **Workaround:** Use direct file download links (requires different approach)

### File Download Methods

| Method | Max Size | Requires | Use Case |
|--------|----------|----------|----------|
| **Bot API getFile** | 20 MB | Bot Token | ✅ Current implementation |
| **Direct Download** | 2 GB | File URL | ⚠️ Not implemented |
| **Telegram Client API** | No limit | User credentials | ❌ Not applicable for bots |

---

## Workarounds for Large Videos

### Option 1: Ask Users to Compress Videos
- Request users to compress videos before posting
- Tools: Handbrake, FFmpeg, Telegram's built-in compression

### Option 2: Implement Direct Download (Future)
- Use Telegram's file download links directly
- Requires different API approach
- No 20MB limit

### Option 3: Store Video Links in Jira
- Instead of downloading, store Telegram file link in Jira description
- Users can click link to view in Telegram
- **Recommended short-term solution**

---

## Testing

### Test with Different File Sizes

1. **Small video (<20MB):** Should download and attach ✅
2. **Large video (>20MB):** Should skip with warning ✅
3. **Expired file_id:** Should log error and continue ✅
4. **Network timeout:** Should handle gracefully ✅

### Run Tests
```bash
pytest tests/unit_tests/frameworks/test_create_ticket.py -k video -v
pytest tests/integration/test_create_ticket_integration.py -k media -v
pytest tests/e2e/test_create_ticket_e2e.py -k video -v
```

---

## Related Files Modified

1. ✅ `jira_telegram_bot/adapters/services/telegram/__init__.py`
   - Enhanced error messages
   - Added timeout

2. ✅ `jira_telegram_bot/adapters/services/telegram/telegram_gateway.py`
   - Graceful error handling
   - Added download timeout

3. ✅ `jira_telegram_bot/frameworks/fast_api/create_ticket.py`
   - Pre-download file size check
   - Skip large videos

---

## Conclusion

The fix ensures that:
- ✅ **Videos ≤20MB** are downloaded and attached
- ✅ **Videos >20MB** are skipped with clear warning
- ✅ **Jira tickets are always created** (even if video fails)
- ✅ **Error messages are informative** for debugging
- ✅ **No crashes** due to video download failures

Users will see tickets created successfully with helpful logs explaining why large videos were skipped.
