# Support Ticket System API - Quick Reference Guide

## Base URL
```
https://bmasia-crm.onrender.com/api/v1/
```

---

## Authentication
All endpoints require JWT token authentication:
```http
Authorization: Bearer <your-jwt-token>
```

---

## Ticket Endpoints

### List All Tickets
```http
GET /api/v1/tickets/
```

**Query Parameters:**
- `status` - Filter by status (new, assigned, in_progress, pending, resolved, closed)
- `priority` - Filter by priority (low, medium, high, urgent)
- `category` - Filter by category (technical, billing, zone_config, account, feature_request, general)
- `company` - Filter by company UUID
- `assigned_to` - Filter by assigned user UUID
- `assigned_team` - Filter by team (Sales, Tech, Finance, Music, Admin)
- `my_tickets` - Set to 'true' to see only your tickets
- `unassigned` - Set to 'true' to see only unassigned tickets
- `open` - Set to 'true' to exclude resolved/closed tickets
- `search` - Search ticket_number, subject, description, or company name
- `ordering` - Sort by field (e.g., -created_at, priority, status, due_date)

**Examples:**
```bash
# Get all urgent tickets
GET /api/v1/tickets/?priority=urgent

# Get my open tickets
GET /api/v1/tickets/?my_tickets=true&open=true

# Search for ticket
GET /api/v1/tickets/?search=T-20251119

# Get unassigned technical issues
GET /api/v1/tickets/?unassigned=true&category=technical
```

### Create Ticket
```http
POST /api/v1/tickets/
Content-Type: application/json

{
  "subject": "Zone offline",
  "description": "Zone has been offline for 2 hours",
  "priority": "high",
  "category": "technical",
  "company": "uuid",
  "contact": "uuid",  // optional
  "due_date": "2025-11-20T17:00:00Z"  // optional
}
```

### Get Ticket Detail
```http
GET /api/v1/tickets/{ticket-id}/
```
Returns ticket with all comments and attachments.

### Update Ticket
```http
PATCH /api/v1/tickets/{ticket-id}/
Content-Type: application/json

{
  "status": "in_progress",
  "priority": "urgent"
}
```

### Delete Ticket
```http
DELETE /api/v1/tickets/{ticket-id}/
```

---

## Custom Ticket Actions

### Add Comment to Ticket
```http
POST /api/v1/tickets/{ticket-id}/add_comment/
Content-Type: application/json

{
  "text": "I've restarted the zone device",
  "is_internal": false
}
```
- `is_internal=false` - Public comment visible to customer
- `is_internal=true` - Internal note (only visible to staff)

### Assign Ticket
```http
POST /api/v1/tickets/{ticket-id}/assign/
Content-Type: application/json

{
  "user_id": "uuid-of-user"
}
```

**Unassign ticket:**
```json
{
  "user_id": null
}
```

### Get Ticket Statistics
```http
GET /api/v1/tickets/stats/
```

**Response:**
```json
{
  "total": 145,
  "by_status": {
    "new": 12,
    "assigned": 25,
    "in_progress": 38,
    "pending": 15,
    "resolved": 45,
    "closed": 10
  },
  "by_priority": {
    "low": 30,
    "medium": 65,
    "high": 40,
    "urgent": 10
  },
  "my_open_tickets": 8,
  "unassigned": 12,
  "overdue": 5
}
```

---

## Comment Endpoints

### List Comments
```http
GET /api/v1/ticket-comments/
```

**Filter by ticket:**
```http
GET /api/v1/ticket-comments/?ticket={ticket-uuid}
```

### Create Comment
```http
POST /api/v1/ticket-comments/
Content-Type: application/json

{
  "ticket": "ticket-uuid",
  "text": "Comment text",
  "is_internal": false
}
```

### Update Comment
```http
PATCH /api/v1/ticket-comments/{comment-id}/
Content-Type: application/json

{
  "text": "Updated comment text"
}
```

### Delete Comment
```http
DELETE /api/v1/ticket-comments/{comment-id}/
```

---

## Attachment Endpoints

### Upload Attachment
```http
POST /api/v1/ticket-attachments/
Content-Type: multipart/form-data

ticket: {ticket-uuid}
file: [binary file data]
```

**cURL Example:**
```bash
curl -X POST \
  https://bmasia-crm.onrender.com/api/v1/ticket-attachments/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "ticket=uuid-here" \
  -F "file=@/path/to/file.png"
```

### Delete Attachment
```http
DELETE /api/v1/ticket-attachments/{attachment-id}/
```

---

## Response Formats

### Ticket Response
```json
{
  "id": "uuid",
  "ticket_number": "T-20251119-0001",
  "subject": "Zone offline in Bangkok office",
  "description": "Zone has been offline for 2 hours",
  "status": "new",
  "priority": "high",
  "category": "technical",
  "company": "company-uuid",
  "company_name": "Hilton Pattaya",
  "contact": "contact-uuid",
  "contact_name": "John Smith",
  "assigned_to": "user-uuid",
  "assigned_to_name": "Keith Thompson",
  "assigned_team": "Tech",
  "created_by": "user-uuid",
  "created_by_name": "Norbert Platzer",
  "first_response_at": "2025-11-19T10:35:00Z",
  "resolved_at": null,
  "closed_at": null,
  "due_date": "2025-11-20T17:00:00Z",
  "first_response_time_hours": 0.08,
  "resolution_time_hours": null,
  "is_overdue": false,
  "tags": "urgent,zone-offline",
  "comments": [...],
  "attachments": [...],
  "comments_count": 5,
  "internal_notes_count": 2,
  "created_at": "2025-11-19T10:30:00Z",
  "updated_at": "2025-11-19T10:35:00Z"
}
```

### Comment Response
```json
{
  "id": "uuid",
  "ticket": "ticket-uuid",
  "author": "user-uuid",
  "author_name": "Tech Support",
  "author_role": "Tech",
  "text": "I've checked the zone status",
  "is_internal": false,
  "created_at": "2025-11-19T10:35:00Z",
  "updated_at": "2025-11-19T10:35:00Z"
}
```

### Attachment Response
```json
{
  "id": "uuid",
  "ticket": "ticket-uuid",
  "file": "/media/tickets/attachments/2025/11/screenshot.png",
  "name": "screenshot.png",
  "size": 245678,
  "uploaded_by": "user-uuid",
  "uploaded_by_name": "Norbert Platzer",
  "created_at": "2025-11-19T10:40:00Z"
}
```

---

## Status Codes

- `200 OK` - Successful GET/PATCH
- `201 Created` - Successful POST
- `204 No Content` - Successful DELETE
- `400 Bad Request` - Invalid data
- `401 Unauthorized` - Missing/invalid token
- `404 Not Found` - Resource not found

---

## Field Reference

### Ticket Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| subject | string | Yes | Ticket subject (max 200 chars) |
| description | text | Yes | Detailed description |
| status | choice | No | new, assigned, in_progress, pending, resolved, closed |
| priority | choice | No | low, medium, high, urgent |
| category | choice | No | technical, billing, zone_config, account, feature_request, general |
| company | uuid | Yes | Company ID |
| contact | uuid | No | Contact ID |
| assigned_to | uuid | No | Assigned user ID |
| due_date | datetime | No | When ticket should be resolved |
| tags | string | No | Comma-separated tags |

### Comment Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| ticket | uuid | Yes | Ticket ID |
| text | text | Yes | Comment text |
| is_internal | boolean | No | Internal note flag (default: false) |

---

## Testing with cURL

### Create Ticket
```bash
curl -X POST \
  https://bmasia-crm.onrender.com/api/v1/tickets/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Test ticket",
    "description": "This is a test",
    "priority": "medium",
    "category": "general",
    "company": "COMPANY_UUID"
  }'
```

### Add Comment
```bash
curl -X POST \
  https://bmasia-crm.onrender.com/api/v1/tickets/TICKET_ID/add_comment/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Working on this now",
    "is_internal": false
  }'
```

### Assign Ticket
```bash
curl -X POST \
  https://bmasia-crm.onrender.com/api/v1/tickets/TICKET_ID/assign/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_UUID"
  }'
```

### Get Statistics
```bash
curl -X GET \
  https://bmasia-crm.onrender.com/api/v1/tickets/stats/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Common Use Cases

### 1. Customer Support Dashboard
```javascript
// Get open tickets count
GET /api/v1/tickets/?open=true

// Get my assigned tickets
GET /api/v1/tickets/?my_tickets=true&open=true

// Get unassigned urgent tickets
GET /api/v1/tickets/?unassigned=true&priority=urgent

// Get statistics for dashboard
GET /api/v1/tickets/stats/
```

### 2. Ticket Detail Page
```javascript
// Get full ticket with comments and attachments
GET /api/v1/tickets/{id}/

// Add customer response
POST /api/v1/tickets/{id}/add_comment/
{
  "text": "...",
  "is_internal": false
}

// Add internal note
POST /api/v1/tickets/{id}/add_comment/
{
  "text": "...",
  "is_internal": true
}
```

### 3. Team Queue View
```javascript
// Get Tech team tickets
GET /api/v1/tickets/?assigned_team=Tech&open=true

// Get Finance team tickets
GET /api/v1/tickets/?assigned_team=Finance&status=pending
```

### 4. Company Support History
```javascript
// Get all tickets for a company
GET /api/v1/tickets/?company={uuid}

// Get open tickets for company
GET /api/v1/tickets/?company={uuid}&open=true
```

---

## Frontend Integration Tips

1. **Polling for Updates**: Use `setInterval` to refresh ticket lists every 30-60 seconds
2. **Real-time Comments**: Reload ticket detail after adding comments
3. **File Uploads**: Use FormData API for attachments
4. **Statistics Dashboard**: Cache stats for 5 minutes to reduce API calls
5. **Infinite Scroll**: Use pagination with `?limit=20&offset=0`

---

**Last Updated**: November 19, 2025
**API Version**: v1
