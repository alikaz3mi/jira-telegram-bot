# Telegram Message Editing Support

## Overview

When users edit their Telegram messages in group chats, the corresponding Jira comments are automatically updated to reflect the changes. This ensures consistency between Telegram and Jira.

## How It Works

### 1. Comment Creation Phase

When a user posts a comment in a Telegram group thread:

```
User posts: "This is my comment"
          ↓
Bot adds comment to Jira
          ↓
Bot stores mapping:
{
  telegram_message_id: 12345,
  chat_id: -1001234567890,
  jira_comment_id: "10001",
  issue_key: "PROJ1-123"
}
```

**Key:** The bot stores a precise mapping between the Telegram message ID and the Jira comment ID.

### 2. Message Edit Phase

When the user edits their message:

```
User edits: "This is my CORRECTED comment"
          ↓
Telegram webhook: edited_message event
          ↓
Bot looks up stored mapping
          ↓
Bot updates exact Jira comment 10001
```

**Result:** The specific Jira comment is updated with the new text, marked with "(edited)" label.

## Technical Implementation

### Data Store Schema

The mapping is stored in `data_store.json` with the following structure:

```json
{
  "-1001234567890_12345_comment": {
    "telegram_message_id": 12345,
    "chat_id": -1001234567890,
    "jira_comment_id": "10001",
    "issue_key": "PROJ1-123",
    "created_at": 1699876543,
    "type": "comment_mapping"
  }
}
```

**Key Format:** `{chat_id}_{telegram_message_id}_comment`

### Code Flow

#### 1. Storing Mapping (in `handle_group_comment`)

```python
# After adding comment to Jira
comment = jira_repository.add_comment(issue_key, formatted_comment)

# Store the mapping
telegram_post_data_store.store_comment_mapping(
    telegram_message_id=message.get("message_id"),
    chat_id=message["chat"]["id"],
    jira_comment_id=comment.id,
    issue_key=issue_key
)
```

#### 2. Retrieving and Updating (in `handle_edited_message`)

```python
# Look up the stored mapping
comment_mapping = telegram_post_data_store.find_comment_mapping(
    message_id, chat_id
)

# Get the exact Jira comment
comment = jira_repository.jira.comment(
    issue_key, jira_comment_id
)

# Update with edited text
comment.update(body=formatted_comment)
```

### Webhook Routing

The bot handles `edited_message` events in the webhook:

```python
@app.post("/webhook")
async def handle_webhook_update(data: Dict[str, Any]):
    if "edited_channel_post" in data:
        return {"status": "ignored", "reason": "Channel post edits not yet supported"}
    elif "edited_message" in data:
        return await handle_edited_message(data["edited_message"])
    elif "channel_post" in data:
        return await handle_channel_post(...)
    elif "message" in data:
        return await handle_group_message(...)
```

**Priority:** Edited messages are checked before new messages.

## Features

### ✅ Supported

- **Text edits:** Updates the Jira comment body
- **Caption edits:** Updates captions on media messages
- **Anonymous admin edits:** Supports GroupAnonymousBot messages
- **Multiple edits:** Users can edit the same message multiple times
- **Old message edits:** Works correctly even if user edits an old message (not their most recent)

### ⚠️ Limitations

- **Media changes:** Editing media attachments is not supported. The bot only updates text/caption.
- **Channel posts:** Editing channel posts is not yet implemented.
- **Deleted comments:** If the Jira comment was manually deleted, the edit will fail gracefully.

## Error Handling

### No Mapping Found

```
Status: ignored
Reason: "No stored comment mapping found"
```

**Cause:** The original message was posted before this feature was implemented, or the mapping was lost.

### Jira Comment Not Found

```
Status: error
Reason: "Comment not found in Jira"
```

**Cause:** The comment was deleted in Jira after being posted.

### Jira API Error

```
Status: error
Message: "Jira API error: [error details]"
```

**Cause:** Network issues, authentication problems, or Jira downtime.

## Examples

### Example 1: Simple Text Edit

**Initial message:**
```
User posts: "The bug is in line 42"
→ Jira comment: "Comment from [~john]: The bug is in line 42"
```

**After edit:**
```
User edits: "The bug is in line 43"
→ Jira comment: "Comment from [~john] (edited): The bug is in line 43"
```

### Example 2: Editing Old Message

**Timeline:**
```
10:00 - User posts comment A
10:05 - User posts comment B
10:10 - User posts comment C
10:15 - User edits comment A (not the most recent!)
```

**Result:** Comment A in Jira is correctly updated, not comment C.

**Why this works:** Each Telegram message ID is precisely mapped to a specific Jira comment ID.

### Example 3: Anonymous Admin Edit

**Initial message:**
```
Anonymous Admin: "Meeting at 3pm"
→ Jira: "Comment from Anonymous Admin: Meeting at 3pm"
```

**After edit:**
```
Anonymous Admin: "Meeting at 4pm"
→ Jira: "Comment from Anonymous Admin (edited): Meeting at 4pm"
```

## Testing

### Unit Tests

10 comprehensive tests cover:
- ✅ Comment creation stores mapping
- ✅ Edited message updates exact comment
- ✅ No mapping found scenario
- ✅ No text in edited message
- ✅ Jira API errors
- ✅ Anonymous admin edits
- ✅ Caption edits
- ✅ Data store methods (store/retrieve)

**Test file:** `tests/unit_tests/test_edited_message_handling.py`

**Run tests:**
```bash
python -m pytest tests/unit_tests/test_edited_message_handling.py -v
```

**Coverage:** All tests passing (10/10) ✓

## Configuration

No additional configuration needed. The feature is automatically enabled for all group chats.

## Deployment

After deploying the updated code:

1. **Rebuild Docker container:**
   ```bash
   docker-compose build ticketing_bot
   docker-compose up -d ticketing_bot
   ```

2. **Verify webhook registration:**
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
   ```

3. **Test by editing a message in any group thread**

## Troubleshooting

### Edits not working for old messages

**Problem:** Messages posted before this feature was deployed can't be edited.

**Reason:** No mapping was stored at creation time.

**Solution:** This is expected. Only messages posted after deployment will be editable.

### Edit appears as new comment

**Problem:** Edited message creates a new comment instead of updating existing one.

**Reason:** The mapping lookup failed.

**Check logs for:**
```
"No comment mapping found for message 12345 in chat -1001234567890"
```

**Solution:** Verify the data_store.json contains the expected mappings.

### Permission denied errors

**Problem:** Bot can't update the comment in Jira.

**Reason:** Insufficient permissions or comment author mismatch.

**Solution:** Ensure the bot's Jira account has permission to edit comments.

## Related Files

- **Main logic:** `jira_telegram_bot/frameworks/fast_api/create_ticket.py`
  - `handle_group_comment()` - stores mappings
  - `handle_edited_message()` - processes edits
  
- **Data store:** `jira_telegram_bot/adapters/repositories/file_storage/__init__.py`
  - `store_comment_mapping()` - saves telegram→jira mapping
  - `find_comment_mapping()` - retrieves mapping
  
- **Tests:** `tests/unit_tests/test_edited_message_handling.py`

- **Data file:** `data_store.json`

## Future Enhancements

1. **Media replacement:** Support updating attachments when media is changed
2. **Edit history:** Track edit history and show in Jira
3. **Channel post edits:** Support editing channel posts
4. **Bulk cleanup:** Periodically clean up old mappings
5. **Delete support:** Handle message deletions (remove Jira comments)

---

**Last Updated:** November 15, 2025
**Feature Status:** ✅ Production Ready
**Test Coverage:** 10/10 tests passing
