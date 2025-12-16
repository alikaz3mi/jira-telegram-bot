#!/bin/bash
# Test script for sprint closed webhook

ENDPOINT="http://localhost:2318/api/v1/webhook/jira/"

# Sprint closed webhook payload
PAYLOAD='{
  "timestamp": 1734163200000,
  "webhookEvent": "sprint_closed",
  "sprint": {
    "id": 123,
    "self": "https://jira.example.com/rest/agile/1.0/sprint/123",
    "state": "closed",
    "name": "Sprint 45",
    "startDate": "2024-12-01T00:00:00.000Z",
    "endDate": "2024-12-14T23:59:59.000Z",
    "completeDate": "2024-12-14T23:59:59.000Z",
    "originBoardId": 1
  }
}'

echo "Testing sprint closed webhook endpoint..."
echo "Endpoint: $ENDPOINT"
echo ""
echo "Payload:"
echo "$PAYLOAD" | python3 -m json.tool
echo ""
echo "Sending request..."
echo ""

curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -v

echo ""
echo "Test completed!"
