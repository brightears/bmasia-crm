# Email Templates Bulk Operations API Documentation

## Overview
The Email Templates API now supports bulk activate and deactivate operations in addition to existing bulk delete and export functionality.

## Endpoint
```
POST /api/v1/email-templates/bulk_operations/
```

## Authentication
Requires JWT authentication token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

## Request Format

### Bulk Activate
Activates multiple email templates (sets `is_active=True`)

```json
{
  "action": "activate",
  "ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ]
}
```

### Bulk Deactivate
Deactivates multiple email templates (sets `is_active=False`)

```json
{
  "action": "deactivate",
  "ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ]
}
```

### Bulk Delete
Deletes multiple email templates (existing functionality)

```json
{
  "action": "delete",
  "ids": [
    "550e8400-e29b-41d4-a716-446655440001"
  ]
}
```

### Bulk Export
Exports multiple email templates to CSV (existing functionality)

```json
{
  "action": "export",
  "ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ]
}
```

## Response Format

### Success Response - Activate/Deactivate
```json
{
  "message": "2 templates activated",
  "count": 2
}
```

**Status Code:** `200 OK`

### Error Response - Validation Failed
```json
{
  "action": ["This field is required."],
  "ids": ["This field is required."]
}
```

**Status Code:** `400 Bad Request`

### Error Response - Invalid Action
```json
{
  "action": ["\"invalid_action\" is not a valid choice."]
}
```

**Status Code:** `400 Bad Request`

### Error Response - No IDs Provided
```json
{
  "ids": ["This list may not be empty."]
}
```

**Status Code:** `400 Bad Request`

## Supported Actions

| Action | Description | Status Field Updated |
|--------|-------------|---------------------|
| `activate` | Sets is_active=True on selected templates | Yes |
| `deactivate` | Sets is_active=False on selected templates | Yes |
| `delete` | Permanently deletes templates | N/A |
| `export` | Exports templates to CSV | N/A |

## Frontend Integration Examples

### Using Axios

```typescript
import api from './services/api';

// Bulk activate templates
const activateTemplates = async (templateIds: string[]) => {
  try {
    const response = await api.post('/api/v1/email-templates/bulk_operations/', {
      action: 'activate',
      ids: templateIds
    });
    console.log(response.data.message); // "2 templates activated"
    return response.data;
  } catch (error) {
    console.error('Failed to activate templates:', error);
    throw error;
  }
};

// Bulk deactivate templates
const deactivateTemplates = async (templateIds: string[]) => {
  try {
    const response = await api.post('/api/v1/email-templates/bulk_operations/', {
      action: 'deactivate',
      ids: templateIds
    });
    console.log(response.data.message); // "2 templates deactivated"
    return response.data;
  } catch (error) {
    console.error('Failed to deactivate templates:', error);
    throw error;
  }
};
```

### Using Fetch API

```javascript
// Bulk activate
fetch('https://bmasia-crm.onrender.com/api/v1/email-templates/bulk_operations/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    action: 'activate',
    ids: ['uuid1', 'uuid2']
  })
})
.then(response => response.json())
.then(data => console.log(data.message))
.catch(error => console.error('Error:', error));
```

## Testing with cURL

### Activate Templates
```bash
curl -X POST https://bmasia-crm.onrender.com/api/v1/email-templates/bulk_operations/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "activate",
    "ids": ["550e8400-e29b-41d4-a716-446655440001", "550e8400-e29b-41d4-a716-446655440002"]
  }'
```

### Deactivate Templates
```bash
curl -X POST https://bmasia-crm.onrender.com/api/v1/email-templates/bulk_operations/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "deactivate",
    "ids": ["550e8400-e29b-41d4-a716-446655440001"]
  }'
```

## Important Notes

1. **UUID Format**: All IDs must be valid UUIDs in the format `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

2. **Minimum IDs**: At least one ID must be provided in the `ids` array

3. **Non-existent IDs**: If an ID doesn't exist in the database, it will be silently ignored. The count in the response reflects only templates that were actually updated.

4. **Permission Requirements**: User must be authenticated with a valid JWT token

5. **Idempotent Operations**: Running activate on already active templates (or deactivate on inactive ones) is safe and will include them in the count

6. **No Rollback**: Operations are permanent. If 5 templates are activated, all 5 will be activated. There's no automatic rollback on partial failure.

## Database Changes

The operations perform direct database updates using Django's `queryset.update()`:

- **activate**: `EmailTemplate.objects.filter(id__in=ids).update(is_active=True)`
- **deactivate**: `EmailTemplate.objects.filter(id__in=ids).update(is_active=False)`

These operations are atomic at the database level and are significantly more efficient than updating templates individually.

## Performance Considerations

- Bulk operations use Django's `update()` which generates a single SQL UPDATE statement
- No individual model save() methods are called, so pre_save/post_save signals won't fire
- Audit logging is NOT performed for activate/deactivate (unlike delete operations)
- Recommended maximum: 100 templates per bulk operation for optimal performance

## Error Handling Best Practices

```typescript
const handleBulkActivate = async (ids: string[]) => {
  if (ids.length === 0) {
    alert('Please select at least one template');
    return;
  }

  try {
    const response = await api.post('/api/v1/email-templates/bulk_operations/', {
      action: 'activate',
      ids
    });

    // Success notification
    alert(`${response.data.count} template(s) activated successfully`);

    // Refresh the list
    fetchTemplates();

  } catch (error: any) {
    if (error.response?.status === 400) {
      // Validation error
      const errors = error.response.data;
      alert(`Validation error: ${JSON.stringify(errors)}`);
    } else if (error.response?.status === 401) {
      // Authentication error
      alert('Session expired. Please log in again.');
      // Redirect to login
    } else {
      // Server error
      alert('Failed to activate templates. Please try again.');
    }
  }
};
```

## Version History

- **v1.0** (2025-01-18): Initial implementation with activate/deactivate actions
- Added to existing bulk operations framework (delete, export, update_status, assign)

## Related Endpoints

- `GET /api/v1/email-templates/` - List all email templates
- `GET /api/v1/email-templates/{id}/` - Get single email template
- `POST /api/v1/email-templates/` - Create email template
- `PUT /api/v1/email-templates/{id}/` - Update email template
- `DELETE /api/v1/email-templates/{id}/` - Delete single email template
- `GET /api/v1/email-templates/{id}/preview/` - Preview template with sample data
