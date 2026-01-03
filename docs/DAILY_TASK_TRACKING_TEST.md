# Daily Task Tracking - Testing Guide

## What Was Fixed

1. **Bot instance** is now initialized once in `__init__` instead of being created every time
2. **Queue management** - removed duplicate `move_to_next()` call that was skipping tasks
3. **Task flow** - handler calls `task_sender` which moves to next task BEFORE sending
4. **Logging** added to trace the flow

## Expected Behavior

### Initial Send
When you run the daily task tracker:
1. You should receive a summary message like: "📋 شما 5 تسک دارید که نیاز به بررسی دارند"
2. Then you get a progress indicator: "━━━━━━━━━━━━━━━━━━\n📌 تسک 1 از 5\n━━━━━━━━━━━━━━━━━━"
3. Finally, the **first task** appears with inline keyboard buttons

### Task Status Types

Depending on the task status, you'll see different keyboards:

#### 1. Task Not Started (`SHOULD_BE_STARTED`)
**Message**: "⏱ این تسک هنوز شروع نشده..."

**Buttons** (delay reasons):
- در انتظار تایید
- مشکل فنی
- اولویت‌های دیگر
- نیازمندی‌های ناقص
- وابستگی آماده نیست
- دلیل دیگر
- درخواست ساب‌تسک
- رد شدن

#### 2. Task In Progress (`IN_PROGRESS`)
**Message**: "⏳ چند ساعت امروز روی این تسک کار کردی؟"

**Buttons** (hours):
- 1 ساعت
- 2 ساعت
- 3 ساعت
- 4 ساعت
- 6 ساعت
- 8 ساعت
- مقدار دلقه
- رد شدن

#### 3. Needs Worklog (`NEEDS_WORKLOG`)
**Message**: "📝 لطفا worklog ثبت کن"

**Buttons** (same as hours):
- Same buttons as IN_PROGRESS

## How to Test

### Step 1: Check if Keyboard Appears
1. Run the daily task tracker
2. Open Telegram on your phone or desktop
3. **Look for buttons below the message**
4. If you see buttons → ✅ keyboard works
5. If you don't see buttons → ❌ problem with keyboard

### Step 2: Test Clicking Buttons
1. Click any button (e.g., "2 ساعت")
2. **Expected behavior**:
   - Button should respond (loading indicator)
   - Message should edit to show confirmation
   - **Next task should appear automatically**
3. If nothing happens → callbacks not working

### Step 3: Check Logs
While testing, watch the logs for:

```bash
# In one terminal, run the bot
python jira_telegram_bot/__main__.py

# In another terminal, watch logs
tail -f logs/bot.log | grep -E "Callback|task_sender|Sending task"
```

When you click a button, you should see:
```
Callback received: data='hours_2', chat_id=100375147
Processing hours callback
_send_next_task_for_user called for chat_id 100375147
Calling task_sender for chat_id 100375147
_send_task_or_complete called for chat_id 100375147
After move_to_next: has_next=True
Sending next task in queue
Sending task PARSCHAT-4808 to chat_id 100375147 (index 1)
```

## Troubleshooting

### Issue: No Buttons Appear
**Possible causes**:
1. Telegram client doesn't support inline keyboards (very old version)
2. Keyboard not being sent with message

**Check**:
- Look for `reply_markup=` in logs when message is sent
- Try on different Telegram client (phone vs desktop)

### Issue: Buttons Don't Respond
**Possible causes**:
1. Polling bot not running (`__main__.py`)
2. Callback handler not registered
3. Pattern doesn't match callback_data

**Fix**:
1. Make sure the main bot is running: `python jira_telegram_bot/__main__.py`
2. Check logs for "Callback received"
3. If no "Callback received" → callback handler not triggering

### Issue: Tasks Come All at Once
**Should be fixed now**, but if it still happens:
- Check if `move_to_next()` is being called twice
- Check logs for "Sending task" - should only appear once per user response

### Issue: Tasks Being Skipped
**Should be fixed now**, but if it still happens:
- Check `current_index` in logs
- Should increment: 0, 1, 2, 3... (not 0, 2, 4, 6...)

## What Each Component Does

### DailyTaskQueueManager (Singleton)
- Holds one queue per user (keyed by chat_id)
- Each queue has: tasks list, current_index, total_tasks
- `move_to_next()` increments index and returns True if more tasks exist

### SendDailyTaskRemindersUseCase
- Creates queue for each user
- Sends **first** task only
- Sets `handler.task_sender = self._send_task_or_complete`

### DailyTaskTrackingHandler
- Receives callback when user clicks button
- Processes the button click (records delay/hours/worklog)
- Calls `self.task_sender(chat_id)` to send next task

### _send_task_or_complete (task_sender)
- Called by handler after user response
- Calls `move_to_next()` to advance queue
- If more tasks → sends next one
- If no more tasks → sends completion message

## Quick Test Command

```bash
# Run once and check output
python scripts/run_daily_task_tracker.py --once 2>&1 | grep -E "Sending task|Message sent|task_sender"
```

Expected output:
```
Message sent successfully to chat 100375147  # Summary
Sending task PARSCHAT-4807 to chat_id 100375147 (index 0)  # First task
Message sent successfully to chat 100375147  # Progress
Message sent successfully to chat 100375147  # Task message with keyboard
```

You should receive:
- 1 summary message
- 1 progress indicator
- 1 task with buttons

**Then wait for user to click a button before next task is sent.**
