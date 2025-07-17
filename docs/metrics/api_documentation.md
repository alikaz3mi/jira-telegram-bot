# API Documentation

## Overview

The Metrics Tracking System provides RESTful API endpoints for webhook ingestion and system monitoring. All endpoints follow REST conventions and return standardized JSON responses.

## Base Configuration

**Base URL**: `https://your-domain.com/metrics`
**Content-Type**: `application/json`
**Authentication**: Optional webhook secret tokens

## Webhook Endpoints

### POST /metrics/jira

Processes Jira webhook events for metrics tracking.

#### Request

**Headers:**
```http
Content-Type: application/json
X-Webhook-Secret: your_jira_webhook_secret (optional)
User-Agent: Jira/1.0
```

**Body:**
Standard Jira webhook payload. The system processes various event types:

- **Issue Created:**
```json
{
  "timestamp": 1638360000000,
  "webhookEvent": "jira:issue_created",
  "issue": {
    "id": "10001",
    "key": "PROJ-123",
    "fields": {
      "summary": "New task summary",
      "assignee": {
        "emailAddress": "john.doe@company.com",
        "displayName": "John Doe"
      },
      "project": {
        "key": "PROJ"
      },
      "issuetype": {
        "name": "Task"
      },
      "created": "2023-12-01T10:00:00.000+0000",
      "sprint": {
        "id": 1,
        "name": "Sprint 1"
      }
    }
  }
}
```

- **Issue Updated:**
```json
{
  "timestamp": 1638360000000,
  "webhookEvent": "jira:issue_updated", 
  "issue": {
    "id": "10001",
    "key": "PROJ-123",
    "fields": {
      "summary": "Updated task summary",
      "assignee": {
        "emailAddress": "john.doe@company.com"
      },
      "resolution": {
        "name": "Done"
      },
      "resolutiondate": "2023-12-01T15:00:00.000+0000"
    }
  },
  "changelog": {
    "items": [
      {
        "field": "status",
        "fromString": "In Progress", 
        "toString": "Done"
      }
    ]
  }
}
```

- **Worklog Created:**
```json
{
  "timestamp": 1638360000000,
  "webhookEvent": "worklog_created",
  "worklog": {
    "timeSpent": "2h 30m",
    "timeSpentSeconds": 9000,
    "author": {
      "emailAddress": "john.doe@company.com"
    },
    "created": "2023-12-01T12:00:00.000+0000"
  },
  "issue": {
    "key": "PROJ-123",
    "fields": {
      "project": {
        "key": "PROJ"
      }
    }
  }
}
```

#### Response

**Success (200 OK):**
```json
{
  "status": "success",
  "message": "Webhook processed successfully",
  "event_id": "jira_10001_1638360000",
  "metrics_updated": [
    "daily_scoreboard",
    "sprint_matrix"
  ],
  "processing_time_ms": 150
}
```

**Error (400 Bad Request):**
```json
{
  "status": "error", 
  "message": "Invalid webhook payload",
  "error_code": "INVALID_PAYLOAD",
  "details": {
    "missing_fields": ["issue.key"],
    "invalid_fields": []
  }
}
```

**Error (401 Unauthorized):**
```json
{
  "status": "error",
  "message": "Invalid webhook secret",
  "error_code": "UNAUTHORIZED"
}
```

**Error (500 Internal Server Error):**
```json
{
  "status": "error",
  "message": "Internal processing error", 
  "error_code": "PROCESSING_ERROR",
  "request_id": "req_123abc456def"
}
```

### POST /metrics/gitlab

Processes GitLab webhook events for metrics tracking.

#### Request

**Headers:**
```http
Content-Type: application/json
X-Gitlab-Token: your_gitlab_webhook_secret (optional)
X-Gitlab-Event: Push Hook | Merge Request Hook
User-Agent: GitLab/1.0
```

**Body:**

- **Push Event:**
```json
{
  "object_kind": "push",
  "event_name": "push",
  "before": "95790bf891e76fee5e1747ab589903a6a1f80f22",
  "after": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
  "ref": "refs/heads/main",
  "project": {
    "id": 15,
    "name": "Project Name",
    "path_with_namespace": "group/project"
  },
  "commits": [
    {
      "id": "da1560886d4f094c3e6c9ef40349f7d38b5d27d7",
      "message": "Fix critical bug in authentication",
      "timestamp": "2023-12-01T10:00:00+00:00",
      "author": {
        "name": "John Doe",
        "email": "john.doe@company.com"
      },
      "added": ["src/auth.py"],
      "modified": ["src/main.py"],
      "removed": []
    }
  ]
}
```

- **Merge Request Event:**
```json
{
  "object_kind": "merge_request",
  "event_type": "merge_request",
  "project": {
    "id": 15,
    "name": "Project Name"
  },
  "object_attributes": {
    "id": 99,
    "iid": 1,
    "title": "Feature: Add user authentication",
    "state": "opened",
    "merge_status": "can_be_merged",
    "created_at": "2023-12-01T10:00:00.000Z",
    "updated_at": "2023-12-01T10:30:00.000Z",
    "author_id": 1,
    "assignee_id": 2,
    "source_branch": "feature/auth",
    "target_branch": "main",
    "action": "open"
  },
  "user": {
    "id": 1,
    "name": "John Doe",
    "email": "john.doe@company.com"
  }
}
```

#### Response

Same response format as Jira webhook endpoint.

### GET /metrics/health

Health check endpoint for monitoring system status.

#### Request

**Headers:**
```http
Accept: application/json
```

#### Response

**Success (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2023-12-01T10:00:00Z",
  "version": "1.0.0",
  "services": {
    "google_sheets": {
      "status": "healthy",
      "last_check": "2023-12-01T09:59:30Z",
      "response_time_ms": 250
    },
    "configuration": {
      "status": "healthy", 
      "developers_count": 5,
      "projects_count": 2,
      "sheets_configured": 2
    },
    "cache": {
      "status": "healthy",
      "idempotency_entries": 150,
      "hit_rate_percent": 85.2
    }
  },
  "metrics": {
    "webhooks_processed_today": 45,
    "sheet_updates_today": 38,
    "errors_today": 2,
    "avg_processing_time_ms": 180
  }
}
```

**Service Degraded (200 OK):**
```json
{
  "status": "degraded",
  "timestamp": "2023-12-01T10:00:00Z",
  "version": "1.0.0", 
  "services": {
    "google_sheets": {
      "status": "slow",
      "last_check": "2023-12-01T09:59:30Z",
      "response_time_ms": 5000,
      "warning": "High response times detected"
    }
  }
}
```

**Service Unhealthy (503 Service Unavailable):**
```json
{
  "status": "unhealthy",
  "timestamp": "2023-12-01T10:00:00Z",
  "services": {
    "google_sheets": {
      "status": "error",
      "last_check": "2023-12-01T09:55:00Z", 
      "error": "Authentication failed"
    }
  }
}
```

## Monitoring Endpoints

### GET /metrics/stats

Returns detailed metrics and statistics.

#### Request

**Headers:**
```http
Accept: application/json
Authorization: Bearer your_api_token (optional)
```

**Query Parameters:**
- `period` (optional): `today`, `week`, `month`, `all` (default: `today`)
- `developer` (optional): Filter by developer email
- `project` (optional): Filter by project key

#### Response

```json
{
  "period": "today",
  "date_range": {
    "start": "2023-12-01T00:00:00Z",
    "end": "2023-12-01T23:59:59Z"
  },
  "totals": {
    "webhooks_received": 120,
    "webhooks_processed": 118,
    "webhooks_failed": 2,
    "sheet_updates": 95,
    "developers_active": 8
  },
  "by_event_type": {
    "task_created": 15,
    "task_updated": 45,
    "task_resolved": 12,
    "time_logged": 25,
    "commit_made": 30,
    "merge_request_opened": 8,
    "merge_request_merged": 5
  },
  "by_developer": {
    "john.doe@company.com": {
      "name": "John Doe",
      "events": 25,
      "tasks_resolved": 3,
      "time_logged": 6.5,
      "commits": 8
    }
  },
  "by_project": {
    "PROJ": {
      "name": "Main Project",
      "events": 85,
      "active_developers": 6
    }
  },
  "performance": {
    "avg_processing_time_ms": 180,
    "max_processing_time_ms": 1200,
    "min_processing_time_ms": 45,
    "success_rate_percent": 98.3
  }
}
```

### GET /metrics/errors

Returns recent errors and processing failures.

#### Request

**Headers:**
```http
Accept: application/json
Authorization: Bearer your_api_token (optional)
```

**Query Parameters:**
- `limit` (optional): Number of errors to return (default: 50, max: 200)
- `since` (optional): ISO timestamp to filter errors since

#### Response

```json
{
  "total_errors": 5,
  "errors": [
    {
      "id": "err_123abc",
      "timestamp": "2023-12-01T10:15:30Z",
      "event_type": "jira_webhook",
      "error_type": "ValidationError",
      "message": "Missing required field: issue.assignee",
      "payload_id": "webhook_456def", 
      "developer": "unknown",
      "project": "PROJ",
      "retry_count": 0,
      "resolved": false
    },
    {
      "id": "err_789ghi",
      "timestamp": "2023-12-01T09:30:15Z",
      "event_type": "sheet_update",
      "error_type": "TransientGoogleError",
      "message": "Rate limit exceeded",
      "payload_id": "event_321jkl",
      "developer": "jane.smith@company.com",
      "project": "PROJ",
      "retry_count": 3,
      "resolved": true,
      "resolved_at": "2023-12-01T09:35:20Z"
    }
  ]
}
```

## Configuration Endpoints

### GET /metrics/config

Returns current system configuration (sensitive data masked).

#### Request

**Headers:**
```http
Accept: application/json
Authorization: Bearer your_admin_token
```

#### Response

```json
{
  "sheets": {
    "daily_scoreboard": {
      "sheet_id": "1Bxi***masked***upms",
      "configured": true,
      "accessible": true,
      "last_updated": "2023-12-01T09:00:00Z"
    },
    "developer_metrics_matrix": {
      "sheet_id": "1Bxi***masked***upms", 
      "configured": true,
      "accessible": true,
      "last_updated": "2023-12-01T08:30:00Z"
    }
  },
  "developers": {
    "total": 8,
    "active": 6,
    "teams": ["Backend", "Frontend", "DevOps"]
  },
  "projects": {
    "total": 3,
    "tracking_enabled": 2,
    "keys": ["PROJ", "SUPPORT", "TEST"]
  },
  "settings": {
    "timezone": "Asia/Tehran",
    "persian_calendar": true,
    "auto_create_sheets": true,
    "retry_attempts": 5,
    "cache_ttl_hours": 24
  }
}
```

## Error Handling

### Error Response Format

All error responses follow this standard format:

```json
{
  "status": "error",
  "message": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "timestamp": "2023-12-01T10:00:00Z",
  "request_id": "req_123abc456def",
  "details": {
    // Additional error-specific details
  }
}
```

### Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `INVALID_PAYLOAD` | Webhook payload is malformed or missing required fields | 400 |
| `UNAUTHORIZED` | Invalid or missing webhook secret | 401 |
| `DEVELOPER_NOT_FOUND` | Developer mapping not found for webhook user | 422 |
| `PROJECT_NOT_CONFIGURED` | Project not configured for metrics tracking | 422 |
| `SHEET_ACCESS_ERROR` | Cannot access Google Sheets | 502 |
| `PROCESSING_ERROR` | Internal processing error | 500 |
| `RATE_LIMIT_EXCEEDED` | Too many requests | 429 |
| `CONFIGURATION_ERROR` | System configuration issue | 500 |

### Retry Logic

The system implements automatic retry for transient errors:

- **Retryable Errors**: Network timeouts, rate limits, temporary Google Sheets errors
- **Retry Strategy**: Exponential backoff (2s, 4s, 8s, 16s, 32s)
- **Max Attempts**: 5 retries
- **Non-Retryable Errors**: Authentication failures, malformed payloads, configuration errors

## Rate Limiting

### Default Limits

- **Webhook Endpoints**: 1000 requests per minute per IP
- **Monitoring Endpoints**: 100 requests per minute per API token
- **Configuration Endpoints**: 10 requests per minute per API token

### Rate Limit Headers

All responses include rate limiting information:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1638360060
X-RateLimit-Window: 60
```

### Rate Limit Exceeded Response

```json
{
  "status": "error",
  "message": "Rate limit exceeded",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "retry_after_seconds": 60,
  "details": {
    "limit": 1000,
    "window_seconds": 60,
    "reset_at": "2023-12-01T10:01:00Z"
  }
}
```

## Authentication

### Webhook Authentication

Webhooks can be secured using secret tokens:

**Jira Webhooks:**
```http
X-Webhook-Secret: your_jira_webhook_secret
```

**GitLab Webhooks:**
```http
X-Gitlab-Token: your_gitlab_webhook_secret
```

### API Token Authentication

Monitoring and configuration endpoints support Bearer token authentication:

```http
Authorization: Bearer your_api_token
```

### Verification Example

Server-side webhook verification:

```python
import hmac
import hashlib
from typing import Optional

def verify_webhook_signature(
    payload: str, 
    signature: str, 
    secret: str,
    algorithm: str = 'sha256'
) -> bool:
    """Verify webhook signature."""
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        getattr(hashlib, algorithm)
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)

def extract_signature(header_value: str) -> Optional[str]:
    """Extract signature from header value."""
    # GitHub/GitLab format: "sha256=signature"
    if '=' in header_value:
        return header_value.split('=', 1)[1]
    # Direct signature
    return header_value
```

## SDK Examples

### Python SDK Usage

```python
import requests
import hmac
import hashlib
from typing import Dict, Any

class MetricsAPIClient:
    def __init__(self, base_url: str, api_token: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.session = requests.Session()
        
        if api_token:
            self.session.headers.update({
                'Authorization': f'Bearer {api_token}'
            })
    
    def send_webhook(self, endpoint: str, payload: Dict[str, Any], 
                    secret: str = None) -> Dict[str, Any]:
        """Send webhook payload to metrics API."""
        url = f"{self.base_url}/metrics/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if secret:
            # Calculate signature
            payload_str = json.dumps(payload, separators=(',', ':'))
            signature = hmac.new(
                secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if endpoint == 'jira':
                headers['X-Webhook-Secret'] = signature
            elif endpoint == 'gitlab':
                headers['X-Gitlab-Token'] = secret
        
        response = self.session.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def get_health(self) -> Dict[str, Any]:
        """Get system health status."""
        response = self.session.get(f"{self.base_url}/metrics/health")
        response.raise_for_status()
        return response.json()
    
    def get_stats(self, period: str = 'today', 
                  developer: str = None, project: str = None) -> Dict[str, Any]:
        """Get metrics statistics."""
        params = {'period': period}
        if developer:
            params['developer'] = developer
        if project:
            params['project'] = project
            
        response = self.session.get(
            f"{self.base_url}/metrics/stats", 
            params=params
        )
        response.raise_for_status()
        return response.json()

# Usage example
client = MetricsAPIClient('https://api.example.com', 'your_api_token')

# Send Jira webhook
jira_payload = {
    "webhookEvent": "jira:issue_created",
    "issue": {
        "key": "PROJ-123",
        # ... rest of payload
    }
}
result = client.send_webhook('jira', jira_payload, 'your_jira_secret')

# Check health
health = client.get_health()
print(f"System status: {health['status']}")

# Get today's stats
stats = client.get_stats('today')
print(f"Webhooks processed: {stats['totals']['webhooks_processed']}")
```

### JavaScript/Node.js SDK Usage

```javascript
const crypto = require('crypto');
const axios = require('axios');

class MetricsAPIClient {
    constructor(baseUrl, apiToken = null) {
        this.baseUrl = baseUrl.replace(/\/+$/, '');
        this.apiToken = apiToken;
        
        this.client = axios.create({
            baseURL: this.baseUrl,
            headers: apiToken ? {
                'Authorization': `Bearer ${apiToken}`
            } : {}
        });
    }
    
    async sendWebhook(endpoint, payload, secret = null) {
        const url = `/metrics/${endpoint}`;
        const headers = { 'Content-Type': 'application/json' };
        
        if (secret) {
            const payloadStr = JSON.stringify(payload);
            const signature = crypto
                .createHmac('sha256', secret)
                .update(payloadStr)
                .digest('hex');
            
            if (endpoint === 'jira') {
                headers['X-Webhook-Secret'] = signature;
            } else if (endpoint === 'gitlab') {
                headers['X-Gitlab-Token'] = secret;
            }
        }
        
        const response = await this.client.post(url, payload, { headers });
        return response.data;
    }
    
    async getHealth() {
        const response = await this.client.get('/metrics/health');
        return response.data;
    }
    
    async getStats(period = 'today', filters = {}) {
        const params = { period, ...filters };
        const response = await this.client.get('/metrics/stats', { params });
        return response.data;
    }
}

// Usage example
const client = new MetricsAPIClient('https://api.example.com', 'your_api_token');

// Send webhook
const payload = {
    webhookEvent: 'jira:issue_created',
    issue: {
        key: 'PROJ-123'
        // ... rest of payload
    }
};

client.sendWebhook('jira', payload, 'your_jira_secret')
    .then(result => console.log('Webhook sent:', result))
    .catch(error => console.error('Error:', error.response.data));
```

This API documentation provides comprehensive coverage of all endpoints, request/response formats, error handling, authentication, and practical usage examples for integrating with the Metrics Tracking System.
