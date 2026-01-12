# Customer Segments API Reference
## BMAsia CRM - Quick Reference Guide

**Base URL:** `https://bmasia-crm.onrender.com/api/v1/segments/`
**Authentication:** JWT Bearer Token required for all endpoints

---

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/segments/` | List all segments |
| POST | `/segments/` | Create new segment |
| GET | `/segments/{id}/` | Get segment details |
| PUT | `/segments/{id}/` | Update segment |
| DELETE | `/segments/{id}/` | Delete segment |
| GET | `/segments/{id}/members/` | Get segment members |
| POST | `/segments/{id}/recalculate/` | Recalculate member count |
| POST | `/segments/{id}/duplicate/` | Duplicate segment |
| POST | `/segments/{id}/enroll_in_sequence/` | Enroll in email sequence |
| POST | `/segments/validate_filters/` | Validate filter criteria |

---

## Request/Response Examples

### 1. List Segments

```http
GET /api/v1/segments/
Authorization: Bearer {your_jwt_token}
```

**Query Parameters:**
- `status` - Filter by status (active, paused, archived)
- `segment_type` - Filter by type (dynamic, static)
- `created_by` - Filter by creator UUID
- `search` - Search in name, description, tags
- `ordering` - Sort by field (e.g., `-created_at`, `name`, `member_count`)

**Response 200:**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "name": "High-Value Hotels",
      "description": "Hotels with >50 zones",
      "segment_type": "dynamic",
      "status": "active",
      "filter_criteria": {...},
      "member_count": 42,
      "last_calculated_at": "2025-11-19T06:55:47Z",
      "created_by": "uuid",
      "created_by_name": "John Doe",
      "tags": "hotels, premium",
      "last_used_at": "2025-11-18T10:30:00Z",
      "times_used": 3,
      "member_preview": [...],
      "can_edit": true,
      "created_at": "2025-11-01T12:00:00Z",
      "updated_at": "2025-11-19T06:55:47Z"
    }
  ]
}
```

---

### 2. Create Dynamic Segment

```http
POST /api/v1/segments/
Authorization: Bearer {your_jwt_token}
Content-Type: application/json

{
  "name": "Premium Hotels Thailand",
  "description": "High-value hotel clients in Thailand",
  "segment_type": "dynamic",
  "status": "active",
  "filter_criteria": {
    "entity": "company",
    "match_type": "all",
    "rules": [
      {
        "field": "industry",
        "operator": "equals",
        "value": "Hotels"
      },
      {
        "field": "country",
        "operator": "equals",
        "value": "Thailand"
      },
      {
        "field": "music_zone_count",
        "operator": "greater_than",
        "value": 10
      }
    ]
  },
  "tags": "hotels, thailand, premium"
}
```

**Response 201:**
```json
{
  "id": "new-uuid",
  "name": "Premium Hotels Thailand",
  "description": "High-value hotel clients in Thailand",
  "segment_type": "dynamic",
  "status": "active",
  "filter_criteria": {...},
  "member_count": 15,
  "last_calculated_at": "2025-11-19T07:00:00Z",
  "created_by": "your-user-uuid",
  "created_by_name": "Your Name",
  "tags": "hotels, thailand, premium",
  "last_used_at": null,
  "times_used": 0,
  "member_preview": [...],
  "can_edit": true,
  "created_at": "2025-11-19T07:00:00Z",
  "updated_at": "2025-11-19T07:00:00Z"
}
```

---

### 3. Get Segment Members

```http
GET /api/v1/segments/{segment_id}/members/?limit=50&offset=0
Authorization: Bearer {your_jwt_token}
```

**Query Parameters:**
- `limit` (optional, default: 100) - Max results per page
- `offset` (optional, default: 0) - Pagination offset

**Response 200:**
```json
{
  "count": 127,
  "results": [
    {
      "id": "contact-uuid",
      "name": "Jane Smith",
      "email": "jane@hotel.com",
      "company": "uuid",
      "company_name": "Grand Hotel Bangkok",
      "contact_type": "Decision Maker",
      "is_primary": true,
      ...
    }
  ],
  "segment_name": "Premium Hotels Thailand",
  "segment_type": "dynamic"
}
```

---

### 4. Recalculate Member Count

```http
POST /api/v1/segments/{segment_id}/recalculate/
Authorization: Bearer {your_jwt_token}
```

**Use Case:** After bulk data imports or updates

**Response 200:**
```json
{
  "message": "Segment recalculated successfully",
  "member_count": 142,
  "last_calculated_at": "2025-11-19T07:15:00Z"
}
```

---

### 5. Enroll Segment in Email Sequence

```http
POST /api/v1/segments/{segment_id}/enroll_in_sequence/
Authorization: Bearer {your_jwt_token}
Content-Type: application/json

{
  "sequence_id": "email-sequence-uuid",
  "notes": "Q4 2025 renewal campaign for premium hotels"
}
```

**Response 200:**
```json
{
  "message": "Enrolled 35 contacts in sequence",
  "enrolled_count": 35,
  "skipped_count": 5,
  "total_members": 40,
  "errors": [
    "contact@example.com: Already enrolled in sequence"
  ],
  "sequence_name": "Renewal Campaign",
  "segment_name": "Premium Hotels Thailand"
}
```

**Notes:**
- Automatically skips contacts already enrolled
- Marks segment as used (increments `times_used`, updates `last_used_at`)
- Returns detailed statistics

---

### 6. Duplicate Segment

```http
POST /api/v1/segments/{segment_id}/duplicate/
Authorization: Bearer {your_jwt_token}
Content-Type: application/json

{
  "name": "Premium Hotels Thailand (Q1 2026)"
}
```

**Response 201:**
```json
{
  "id": "new-uuid",
  "name": "Premium Hotels Thailand (Q1 2026)",
  "description": "Cloned from: Premium Hotels Thailand",
  "segment_type": "dynamic",
  "status": "active",
  "filter_criteria": {...},
  "member_count": 15,
  "created_by": "your-user-uuid",
  ...
}
```

**Notes:**
- Copies all filter criteria
- For static segments: Copies all member relationships
- Sets `created_by` to current user
- Auto-calculates member count

---

### 7. Validate Filters (Preview)

```http
POST /api/v1/segments/validate_filters/
Authorization: Bearer {your_jwt_token}
Content-Type: application/json

{
  "filter_criteria": {
    "entity": "contact",
    "match_type": "all",
    "rules": [
      {
        "field": "contact_type",
        "operator": "equals",
        "value": "Decision Maker"
      },
      {
        "field": "company.industry",
        "operator": "equals",
        "value": "Hotels"
      }
    ]
  }
}
```

**Response 200 (Valid):**
```json
{
  "valid": true,
  "estimated_count": 127,
  "preview": [
    {
      "id": "contact-uuid",
      "name": "Jane Smith",
      "email": "jane@hotel.com",
      ...
    }
  ]
}
```

**Response 400 (Invalid):**
```json
{
  "valid": false,
  "error": "Invalid operator: xyz"
}
```

---

## Filter Criteria Structure

### Basic Structure
```json
{
  "entity": "company" | "contact",
  "match_type": "all" | "any",
  "rules": [
    {
      "field": "field_name",
      "operator": "operator_name",
      "value": "value"
    }
  ]
}
```

### Available Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `equals` | Exact match (case-insensitive) | `"industry": "Hotels"` |
| `not_equals` | Not equal to | `"status": "inactive"` |
| `contains` | Contains substring | `"name": "Hotel"` |
| `not_contains` | Does not contain | `"name": "Test"` |
| `starts_with` | Starts with | `"email": "@gmail"` |
| `ends_with` | Ends with | `"email": ".com"` |
| `greater_than` | Greater than (numeric) | `"music_zone_count": 10` |
| `greater_than_or_equal` | Greater than or equal | `"music_zone_count": 10` |
| `less_than` | Less than | `"music_zone_count": 5` |
| `less_than_or_equal` | Less than or equal | `"music_zone_count": 5` |
| `between` | Between range | `"music_zone_count": [5, 20]` |
| `in_list` | In list of values | `"country": ["Thailand", "Vietnam"]` |
| `is_empty` | Field is null or empty | `"notes": null` |
| `is_not_empty` | Field has value | `"notes": null` |

### Company Fields

**Available for `entity: "company"`:**
- `name`
- `legal_entity_name`
- `country`
- `industry`
- `location_count`
- `music_zone_count`
- `is_active`
- `billing_entity`
- `city`
- `state`

### Contact Fields

**Available for `entity: "contact"`:**
- `name`
- `email`
- `phone`
- `title`
- `department`
- `contact_type` (Decision Maker, Billing, Primary, Technical, Other)
- `is_primary`
- `is_active`
- `company.{company_field}` (e.g., `company.industry`)
- `company.contracts.{contract_field}` (e.g., `company.contracts.status`)

### Example: Complex Filter
```json
{
  "entity": "contact",
  "match_type": "all",
  "rules": [
    {
      "field": "contact_type",
      "operator": "equals",
      "value": "Decision Maker"
    },
    {
      "field": "company.industry",
      "operator": "equals",
      "value": "Hotels"
    },
    {
      "field": "company.country",
      "operator": "in_list",
      "value": ["Thailand", "Vietnam", "Indonesia"]
    },
    {
      "field": "company.music_zone_count",
      "operator": "greater_than",
      "value": 10
    },
    {
      "field": "is_active",
      "operator": "equals",
      "value": true
    }
  ]
}
```

This will find all Decision Makers at Hotels in Thailand/Vietnam/Indonesia with more than 10 music zones.

---

## Error Codes

| Status | Description |
|--------|-------------|
| 200 | Success |
| 201 | Created successfully |
| 400 | Bad request (validation error) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Segment not found |
| 500 | Server error |

---

## Permissions

**Role-Based Access:**
- **Admin**: Full access to all segments
- **Non-Admin**:
  - Can see: Own segments + active public segments
  - Can edit: Only own segments
  - Can delete: Only own segments

**Permission Check:**
The `can_edit` field in responses indicates if current user can edit the segment.

---

## Best Practices

1. **Use validate_filters before saving** - Preview member count before creating
2. **Recalculate after bulk changes** - Keep member_count accurate
3. **Check enrollment before enrolling** - API automatically skips duplicates
4. **Use pagination for large segments** - Limit members endpoint results
5. **Use specific filter operators** - More precise = better performance
6. **Tag segments consistently** - Makes searching easier

---

## Integration Example (JavaScript)

```javascript
// Create segment
const createSegment = async (segmentData) => {
  const response = await fetch('https://bmasia-crm.onrender.com/api/v1/segments/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(segmentData)
  });

  if (!response.ok) {
    throw new Error('Failed to create segment');
  }

  return response.json();
};

// Get members
const getSegmentMembers = async (segmentId, limit = 100, offset = 0) => {
  const response = await fetch(
    `https://bmasia-crm.onrender.com/api/v1/segments/${segmentId}/members/?limit=${limit}&offset=${offset}`,
    {
      headers: {
        'Authorization': `Bearer ${jwtToken}`
      }
    }
  );

  return response.json();
};

// Enroll in sequence
const enrollInSequence = async (segmentId, sequenceId, notes = '') => {
  const response = await fetch(
    `https://bmasia-crm.onrender.com/api/v1/segments/${segmentId}/enroll_in_sequence/`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ sequence_id: sequenceId, notes })
    }
  );

  return response.json();
};
```

---

## Support

For issues or questions:
- Check Phase 2 Implementation Report
- Review test_segments_api.py for usage examples
- Contact: Development Team

**Last Updated:** November 19, 2025
**Version:** Phase 2 Complete
