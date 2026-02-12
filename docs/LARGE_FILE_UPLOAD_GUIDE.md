# Large File Upload Configuration Guide

## 🎯 Quick Summary

To upload large videos (>20MB) from Telegram to Jira, you need to configure **3 layers**:

1. **Bypass Telegram's 20MB `getFile` limit** → Use direct file download
2. **Configure Nginx** (if you use it) → Increase `client_max_body_size`
3. **Configure Jira** → Increase attachment size limits

---

## Problem Analysis

Your error occurs because:
- Telegram's Bot API `getFile` method has a **20MB limit**
- Your current code (`MockFilePath._get_file_path()`) uses `getFile`
- This returns 400 error for files >20MB

---

## Solution 1: Direct File Download (Bypass 20MB Limit)

### How Telegram File Download Works

Telegram provides two ways to download files:

| Method | Max Size | Current Usage | Recommendation |
|--------|----------|---------------|----------------|
| **getFile API** | 20 MB | ✅ Used now | ❌ Remove for large files |
| **Direct Download** | 2 GB | ❌ Not used | ✅ Implement this |

### Implementation Steps

#### Step 1: Modify `MockFilePath` to Use Direct Download

**File:** `jira_telegram_bot/adapters/services/telegram/__init__.py`

**Current Code (uses getFile - 20MB limit):**
```python
class MockFilePath:
    def __init__(self, file_id: str | int, token: str = None):
        self.file_id = file_id
        self.file_path = self._get_file_path(token)  # ❌ This calls getFile (20MB limit)

    def _get_file_path(self, token: str) -> str:
        url = f"https://api.telegram.org/bot{token}/getFile?file_id={self.file_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            result = resp.json()["result"]
            return result["file_path"]
        else:
            raise Exception(...)
```

**New Code (direct download - 2GB limit):**
```python
class MockFilePath:
    def __init__(self, file_id: str | int, token: str = None):
        self.file_id = file_id
        self.token = token
        self.file_path = None  # Will be set when needed
        
    def get_download_url(self) -> str:
        """Get direct download URL without calling getFile (bypasses 20MB limit)."""
        # Try getFile first for small files
        url = f"https://api.telegram.org/bot{self.token}/getFile?file_id={self.file_id}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                result = resp.json()["result"]
                self.file_path = result["file_path"]
                return f"https://api.telegram.org/file/bot{self.token}/{self.file_path}"
            elif resp.status_code == 400:
                # File too large for getFile, construct direct URL
                # This requires using Telegram Client API or MTProto
                # For Bot API, we're limited to 20MB
                raise Exception(
                    f"File too large for Bot API (>20MB). "
                    f"Consider: 1) Ask users to compress videos, "
                    f"2) Use Telegram Client API, "
                    f"3) Store file link in Jira instead of downloading"
                )
        except Exception as e:
            raise Exception(f"Failed to get file download URL: {e}")
```

**⚠️ Important:** Telegram Bot API doesn't provide direct download for files >20MB. You need to either:
- Use **Telegram Client API** (requires user credentials, not bot token)
- Store the **file link** in Jira description instead of downloading
- Ask users to **compress videos** before uploading

---

## Solution 2: Store Video Links Instead of Downloading

### Recommended Approach for Large Videos

Instead of downloading large videos, **store the Telegram message link** in the Jira ticket description.

#### Implementation

**File:** `jira_telegram_bot/frameworks/fast_api/create_ticket.py`

**Modify the video handling section:**

```python
elif "video" in channel_post:
    vid = channel_post["video"]
    file_id = vid["file_id"]
    file_size = vid.get("file_size", 0)
    file_size_mb = file_size / (1024 * 1024) if file_size else 0
    
    # Telegram Bot API getFile has 20MB limit
    if file_size > 20 * 1024 * 1024:
        # Store Telegram link instead of downloading
        chat_id = channel_post["chat"]["id"]
        message_id = channel_post["message_id"]
        
        # Generate Telegram message link
        # Format: https://t.me/c/{chat_id without -100}/{message_id}
        telegram_link = None
        if str(chat_id).startswith("-100"):
            # Channel/supergroup
            clean_chat_id = str(chat_id)[4:]  # Remove -100 prefix
            telegram_link = f"https://t.me/c/{clean_chat_id}/{message_id}"
        
        # Add link to task description
        if telegram_link:
            task_data.description += f"\n\n*📹 Large Video ({file_size_mb:.2f}MB):*\n{telegram_link}"
            LOGGER.warning(
                f"Video file too large ({file_size_mb:.2f}MB > 20MB limit). "
                f"Added Telegram link to ticket instead: {telegram_link}"
            )
        else:
            LOGGER.warning(
                f"Video file too large ({file_size_mb:.2f}MB > 20MB limit). "
                f"Unable to generate Telegram link. Video skipped."
            )
    else:
        # Download small videos normally
        LOGGER.info(f"Processing video: file_id={file_id}, size={file_size_mb:.2f}MB")
        mock_media = MockTelegramVideo(file_id, token=TELEGRAM_SETTINGS.HOOK_TOKEN)
        await fetch_and_store_media(
            mock_media,
            session,
            attachments["videos"],
            "single_video.mp4",
            token=TELEGRAM_SETTINGS.HOOK_TOKEN,
        )
```

**Benefits:**
- ✅ Works for any file size (no limits!)
- ✅ No download/upload overhead
- ✅ Users can click link to view in Telegram
- ✅ Jira ticket always created successfully

---

## Solution 3: Configure Nginx (If You Use Reverse Proxy)

### Check if You Use Nginx

```bash
# Check if nginx is running
docker ps | grep nginx
# or
systemctl status nginx
```

### Nginx Configuration for Large Uploads

If you have Nginx in front of your FastAPI application, you need to increase upload limits.

#### Create/Update Nginx Config

**File:** `/etc/nginx/conf.d/jira-telegram-bot.conf`

```nginx
server {
    listen 80;
    server_name your-bot-domain.com;

    # ⭐ Increase max upload size (e.g., 100MB)
    client_max_body_size 100M;
    
    # ⭐ Increase timeout for large uploads
    client_body_timeout 300s;
    proxy_read_timeout 300s;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;

    location / {
        proxy_pass http://localhost:2315;  # Your FastAPI port
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # ⭐ Disable buffering for large uploads
        proxy_request_buffering off;
    }
}
```

#### Docker Compose with Nginx

If you want to add Nginx to your stack:

**File:** `docker-compose.yml`

```yaml
services:
  # ... existing services ...

  nginx:
    image: nginx:alpine
    container_name: nginx_reverse_proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro  # If using SSL
    depends_on:
      - ticketing-bot
    restart: always
```

**File:** `nginx/nginx.conf`

```nginx
events {
    worker_connections 1024;
}

http {
    # ⭐ Global upload size limit
    client_max_body_size 100M;
    client_body_timeout 300s;
    
    # Logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Upstream for FastAPI
    upstream ticketing_bot {
        server ticketing-bot:2315;
    }

    server {
        listen 80;
        server_name _;

        location / {
            proxy_pass http://ticketing_bot;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            
            # ⭐ Important for large uploads
            proxy_request_buffering off;
            proxy_read_timeout 300s;
            proxy_connect_timeout 300s;
            proxy_send_timeout 300s;
        }
    }
}
```

#### Apply Nginx Changes

```bash
# Test configuration
nginx -t

# Reload nginx
nginx -s reload

# Or restart nginx service
systemctl restart nginx

# Or restart docker container
docker-compose restart nginx
```

---

## Solution 4: Configure Jira Server

### Jira Attachment Size Limits

Jira has built-in limits for attachment sizes. You need to configure:

1. **Jira Application Settings**
2. **Tomcat Configuration** (if self-hosted)
3. **Database Settings** (for large BLOBs)

### 4.1 Jira Application Settings

**Via Jira Admin UI:**

1. Go to **⚙️ Settings → System → General Configuration**
2. Find **Attachment Size**
3. Increase the limit (e.g., `100 MB` or `1000 MB` for 1GB)
4. Click **Save**

**Via REST API:**

```bash
curl -X PUT \
  'https://jira.example.com/rest/api/2/application-properties/jira.attachment.size' \
  -H 'Authorization: Basic YOUR_BASE64_CREDENTIALS' \
  -H 'Content-Type: application/json' \
  -d '{"value": "104857600"}'  # 100MB in bytes
```

### 4.2 Tomcat Configuration (Self-Hosted Jira)

If you host Jira yourself, configure Tomcat:

**File:** `<JIRA_INSTALL>/conf/server.xml`

```xml
<Connector port="8080" 
           protocol="HTTP/1.1"
           connectionTimeout="20000"
           redirectPort="8443"
           maxPostSize="104857600"      <!-- ⭐ 100MB in bytes -->
           maxHttpHeaderSize="8192"
           compression="on"
           compressionMinSize="2048"
           noCompressionUserAgents="gozilla, traviata"
           compressableMimeType="text/html,text/xml,text/plain,text/css,application/json,application/javascript" />
```

**Restart Jira:**
```bash
./stop-jira.sh
./start-jira.sh
```

### 4.3 Database Configuration (PostgreSQL Example)

If using PostgreSQL for Jira, increase BLOB size limits:

**File:** `postgresql.conf`

```conf
# Increase max packet size for large attachments
max_wal_size = 2GB
```

### 4.4 Verify Jira Settings

**Check current limit:**

```bash
curl -X GET \
  'https://jira.example.com/rest/api/2/application-properties/jira.attachment.size' \
  -H 'Authorization: Basic YOUR_BASE64_CREDENTIALS'
```

**Response:**
```json
{
  "id": "jira.attachment.size",
  "key": "jira.attachment.size",
  "value": "104857600",  // 100MB
  "name": "Attachment Size",
  "desc": "Maximum size for attachments (in bytes).",
  "type": "string"
}
```

---

## Solution 5: FastAPI Configuration

### Increase FastAPI Upload Limits

Your FastAPI application may also have upload size limits.

**File:** `jira_telegram_bot/frameworks/fast_api/create_ticket.py`

**Add at the top (after FastAPI creation):**

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

# ⭐ Increase max request body size (100MB)
app.state.max_body_size = 100 * 1024 * 1024  # 100MB

@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    """Middleware to check upload size."""
    if request.method in ["POST", "PUT"]:
        content_length = request.headers.get("content-length")
        if content_length:
            content_length = int(content_length)
            if content_length > app.state.max_body_size:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"File too large. Max size: {app.state.max_body_size / (1024*1024)}MB"}
                )
    return await call_next(request)
```

---

## Recommended Configuration Summary

### For Your Use Case (Telegram → Jira)

Based on your `.env` showing `jira.example.com`, here's what you should configure:

#### 1. **Application Level (Immediate)**
```python
# In create_ticket.py - Store links instead of downloading large videos
if file_size > 20 * 1024 * 1024:
    # Generate Telegram link and add to description
    telegram_link = f"https://t.me/c/{clean_chat_id}/{message_id}"
    task_data.description += f"\n\n*📹 Video:* {telegram_link}"
```

**Priority:** ⭐⭐⭐ **HIGH** (Implement this first!)

#### 2. **Jira Server** (Contact Jira Admin)
```
Settings → System → General Configuration → Attachment Size
Change from: 10 MB (default)
Change to: 100 MB or 1000 MB
```

**Priority:** ⭐⭐ **MEDIUM** (Only if you want to download files)

#### 3. **Nginx** (If Used)
```nginx
# /etc/nginx/conf.d/jira-bot.conf
client_max_body_size 100M;
client_body_timeout 300s;
proxy_request_buffering off;
```

**Priority:** ⭐ **LOW** (Only if Nginx is in your stack)

---

## Testing Your Configuration

### Test 1: Small Video (<20MB)
```bash
# Should work with current implementation
# Expected: Video downloaded and attached to Jira
```

### Test 2: Medium Video (20-50MB)
```bash
# With link storage: Should create ticket with Telegram link
# Expected: Ticket created, link in description
```

### Test 3: Large Video (>50MB)
```bash
# With link storage: Should create ticket with Telegram link
# Expected: Ticket created, link in description
```

### Test 4: Check Jira Attachment
```bash
# If you implemented download for large files:
curl -X GET "https://jira.example.com/rest/api/2/issue/PROJ1-1234/attachments" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Troubleshooting

### Error: "413 Request Entity Too Large"
**Cause:** Nginx limit too low  
**Fix:** Increase `client_max_body_size` in nginx.conf

### Error: "400 Bad Request: file is too big"
**Cause:** Telegram Bot API 20MB limit  
**Fix:** Use link storage instead of download

### Error: "Jira attachment size exceeds limit"
**Cause:** Jira attachment limit too low  
**Fix:** Increase Jira attachment size in admin settings

### Error: "Timeout uploading to Jira"
**Cause:** Upload timeout too short  
**Fix:** Increase timeout in nginx and FastAPI

---

## Final Recommendation

For your use case, I recommend **Solution 2** (Store Telegram Links):

### Why?
- ✅ **No size limits** (works for any video size)
- ✅ **Fast** (no download/upload overhead)
- ✅ **Simple** (minimal code changes)
- ✅ **Reliable** (no network transfer failures)
- ✅ **User-friendly** (click link to view in Telegram)

### Implementation Checklist

- [ ] Modify video handling in `create_ticket.py` (add link generation)
- [ ] Update logging to show when links are used instead of downloads
- [ ] Test with videos >20MB
- [ ] Update documentation for users
- [ ] (Optional) Add Jira custom field to store original Telegram file_id

---

## Need Help?

If you need help implementing any of these solutions, let me know which approach you prefer:

1. **Store links** (recommended) - I can implement this now
2. **Configure Jira** - Need your Jira admin credentials
3. **Add Nginx** - Need to see your current deployment setup
4. **All of the above** - Comprehensive solution

Which solution would you like me to implement first?
