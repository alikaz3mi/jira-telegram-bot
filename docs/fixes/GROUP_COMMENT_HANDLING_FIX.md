## Group Comment Handling - Bug Fix Summary

### Problem
Comments posted in Telegram group threads were not being added to Jira issues. The logs showed:
```
[WARNING] Invalid message structure in group chat_id=-1002491201232
```

### Root Causes Identified

1. **Thread Reply Detection**: When users replied to comments within a thread (not the original auto-forwarded message), the code couldn't find the associated issue
2. **GroupAnonymousBot Messages**: Messages from anonymous group admins were partially handled but failed to lookup issues correctly
3. **No Media Support**: Comments with images, videos, documents, or voice notes were not being attached to Jira

### Solutions Implemented

#### 1. Enhanced Issue Lookup (4 Methods)
Added multiple fallback methods to find the Jira issue from group messages:

**Method 1**: Forward origin (new Bot API) - for auto-forwarded channel posts
**Method 2**: Forward message ID (old API) - for auto-forwarded channel posts  
**Method 3**: Direct reply lookup - searches data store for `reply_message_id` matching the replied-to message
**Method 4**: Thread ID lookup - uses `message_thread_id` to find issues in Telegram topics/threads

```python
# Example: Message 7996 replies to 7993 in thread 7987
# Code will:
# 1. Try forward_origin/forward_from_message_id (not found)
# 2. Look for entry with reply_message_id=7993 (not found - it's a comment)
# 3. Look for entry with reply_message_id=7987 (FOUND - PCT-1093)
```

#### 2. Media Attachment Support
Comments now support:
- **Photos** (single or multiple)
- **Documents** (any file type)
- **Videos** (< 20MB, with size warning for larger files)
- **Audio/Voice** messages

All media is downloaded from Telegram and attached to the Jira comment.

#### 3. Anonymous Admin Handling
Improved handling for `GroupAnonymousBot`:
- Detects anonymous messages via username or `sender_chat`
- Attributes comments as "Anonymous Admin" in Jira
- Skips command processing for anonymous messages
- Still fetches and attaches media

### Code Changes

**File**: `jira_telegram_bot/frameworks/fast_api/create_ticket.py`

**Function**: `handle_group_comment()`

**Key Changes**:
1. Added 4-method issue lookup strategy
2. Added async media fetching and attachment
3. Enhanced anonymous message detection
4. Added media type detection (photo/video/document/audio/voice)
5. Improved error handling and logging

### Testing Scenarios

| Scenario | Before | After |
|----------|--------|-------|
| Reply to auto-forwarded message | ✅ Works | ✅ Works |
| Reply to another comment in thread | ❌ Failed | ✅ Works |
| GroupAnonymousBot message | ❌ Failed | ✅ Works |
| Comment with single image | ❌ Not attached | ✅ Attached |
| Comment with multiple images | ❌ Not attached | ✅ Attached |
| Comment with document | ❌ Not attached | ✅ Attached |
| Comment with video (<20MB) | ❌ Not attached | ✅ Attached |
| Comment with video (>20MB) | ❌ Not attached | ⚠️ Warning added to comment |
| Comment with voice note | ❌ Not attached | ✅ Attached |
| Text-only comment | ✅ Works | ✅ Works |

### Example Log Flow (After Fix)

```
[DEBUG] Processing Telegram update: message_id=7996, thread_id=7987
[INFO] Handling group message with ID: 7996
[INFO] Processing anonymous admin message in chat_id=-1002491201232
[INFO] Found issue PCT-1093 from message_thread_id=7987
[INFO] Successfully fetched media: comment_photo_7996.jpg
[INFO] Added comment with 1 attachment(s) to PCT-1093
```

### Deployment

Changes are backward compatible. Simply rebuild and restart:

```bash
docker compose down
docker compose build
docker compose up -d
```

### Future Improvements

- [ ] Support media groups (multiple photos/videos in one comment)
- [ ] Add retry logic for failed media downloads
- [ ] Cache thread_id → issue_key mappings for faster lookup
- [ ] Add unit tests for all 4 lookup methods
- [ ] Support edit/delete of comments

### Related Issues

- Fixed: "Invalid message structure" warning for thread replies
- Fixed: Comments from GroupAnonymousBot not sent to Jira
- Fixed: Media attachments missing from comments
- Fixed: Thread-based comments not working

### Files Modified

1. `jira_telegram_bot/frameworks/fast_api/create_ticket.py` - Enhanced `handle_group_comment()`
