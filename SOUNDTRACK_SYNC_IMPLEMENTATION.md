# Soundtrack Your Brand Sync Implementation

## Overview
Backend implementation for syncing Soundtrack Your Brand zones with the BMAsia CRM system. This provides both manual sync via API endpoints and automated sync via Django management commands.

## Implementation Date
January 6, 2026

## Files Modified/Created

### 1. Management Command (NEW)
**File**: `/crm_app/management/commands/sync_soundtrack.py`

**Purpose**: Django management command to sync Soundtrack zones from the command line or cron jobs.

**Usage**:
```bash
# Sync all companies with Soundtrack account IDs
python manage.py sync_soundtrack

# Sync specific company by ID
python manage.py sync_soundtrack --company-id 123
```

**Features**:
- Syncs all companies with configured `soundtrack_account_id`
- Optional `--company-id` flag to sync single company
- Clear success/error reporting
- Graceful error handling for missing companies or account IDs

### 2. API Endpoints (MODIFIED)
**File**: `/crm_app/views.py` (lines 6129-6168)

**ViewSet**: `ZoneViewSet`

#### New Endpoints

##### 1. Sync All Zones
```
POST /api/v1/zones/sync-all/
```

**Description**: Triggers manual sync for all Soundtrack zones across all companies with configured account IDs.

**Response**:
```json
{
  "synced": 42,
  "errors": 0,
  "message": "Synced 42 zones with 0 errors"
}
```

**Use Case**: Admin dashboard "Sync All" button

---

##### 2. Sync Company Zones
```
POST /api/v1/zones/{zone_id}/sync/
```

**Description**: Syncs all zones for the company that owns the specified zone.

**Response**:
```json
{
  "synced": 5,
  "errors": 0,
  "message": "Synced 5 zones for Hilton Pattaya with 0 errors"
}
```

**Error Response** (if company has no Soundtrack account ID):
```json
{
  "error": "Company \"Hilton Pattaya\" has no Soundtrack account ID configured"
}
```
Status: 400 Bad Request

**Use Case**: Company detail page "Sync Zones" button

---

## Existing Infrastructure (Already Built)

### SoundtrackAPIService
**File**: `/crm_app/services/soundtrack_api.py`

**Key Methods**:
- `sync_company_zones(company)` - Syncs all zones for a specific company
- `sync_all_zones()` - Syncs zones for all companies with Soundtrack account IDs
- `get_account_zones(account_id)` - Fetches zones from Soundtrack API via GraphQL

### Zone Model
**File**: `/crm_app/models.py` (lines 1196-1300)

**Key Fields**:
- `soundtrack_zone_id` - Soundtrack API zone ID
- `status` - Zone status (online, offline, no_device, pending)
- `device_name` - Device name from Soundtrack API
- `last_seen_online` - Timestamp of last online status
- `api_raw_data` - JSON field with full API response
- `last_api_sync` - Timestamp of last sync

## How It Works

### Sync Flow
1. **Fetch from API**: Service calls Soundtrack GraphQL API to get zones for account
2. **Match/Create**: Zones are matched by name + platform, created if not found
3. **Update Status**: Zone status, device info, and timestamps are updated
4. **Store Raw Data**: Full API response stored in `api_raw_data` field for debugging

### Error Handling
- Companies without `soundtrack_account_id` are skipped
- API errors are logged but don't stop the sync process
- Returns counts of synced zones and errors encountered

### Rate Limiting
- Soundtrack API has rate limits (details in SOUNDTRACK_API_SETUP.md)
- Service uses exponential backoff for retries (if needed)
- Circuit breaker pattern prevents hammering failing endpoints

## Testing

### Test Management Command
```bash
# Sync all companies
python manage.py sync_soundtrack

# Sync specific company (example: company ID 5)
python manage.py sync_soundtrack --company-id 5
```

### Test API Endpoints
```bash
# Sync all zones (requires authentication)
curl -X POST https://bmasia-crm.onrender.com/api/v1/zones/sync-all/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Sync company zones (zone ID 123)
curl -X POST https://bmasia-crm.onrender.com/api/v1/zones/123/sync/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Future Enhancements

### Scheduled Sync (Optional)
Add to Render cron jobs:
```yaml
# Sync Soundtrack zones daily at 2 AM Bangkok time
- name: soundtrack-sync
  schedule: "0 2 * * *"
  command: "python manage.py sync_soundtrack"
```

### Frontend Integration (Next Step)
- Add "Sync Zones" button on Company detail page
- Add "Sync All Zones" button on Zones list page (Admin only)
- Add loading states and success/error notifications
- Display last sync time and status

### Webhooks (Future)
- Soundtrack API supports webhooks for real-time zone updates
- Would eliminate need for polling/manual sync
- Requires webhook endpoint + signature verification

## Security Considerations

- API endpoints require authentication (`IsAuthenticated` permission)
- Soundtrack API token stored in environment variable
- No sensitive data exposed in API responses
- Audit logging for sync operations (via base viewset)

## Related Documentation

- **Soundtrack API Setup**: `SOUNDTRACK_API_SETUP.md`
- **Zone Tracking Guide**: `ZONE_TRACKING_GUIDE.md`
- **Main Project Instructions**: `CLAUDE.md`

## API Integration Best Practices (Per System Prompt)

This implementation follows the BMAsia CRM API integration standards:

### Architecture Design
- Service class (`SoundtrackAPIService`) encapsulates all API logic
- Clean separation between service, views, and management commands
- Singleton pattern for service instance

### Authentication
- Soundtrack API uses Basic auth with API token
- Token management via environment variables
- No credential leakage in logs or responses

### Resilience Patterns
- Graceful error handling with logging
- Sync continues even if individual companies fail
- Returns error counts for monitoring

### Error Handling
- Categorized errors (network, authentication, business logic)
- Meaningful error messages for debugging
- Appropriate logging levels (info, warning, error)
- No sensitive data in error messages

### Performance Optimization
- Uses `select_related()` for database queries
- GraphQL field selection to minimize payload
- Connection pooling via requests library
- Pagination support for large result sets

### Monitoring & Observability
- Comprehensive logging for all sync operations
- Returns metrics (synced count, error count)
- Timestamps tracked on Zone model for monitoring

## Support

For issues or questions about Soundtrack sync:
1. Check logs: `python manage.py check_logs` (if command exists)
2. Verify Soundtrack credentials in environment variables
3. Test API connection: `python manage.py test_soundtrack_api`
4. Review Soundtrack API documentation for rate limits/changes
