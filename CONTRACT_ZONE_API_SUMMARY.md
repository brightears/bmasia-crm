# Contract-Zone API Implementation Summary

## Overview
This document summarizes the Phase 2 implementation of the Contract-Zone API layer for the BMAsia CRM system. Phase 1 (data model) was already complete with the ContractZone model and relationships.

## Implementation Date
November 25, 2025

## Files Modified

### 1. `/crm_app/serializers.py`
**Changes:**
- Added `ContractZone` to model imports
- Created `ContractZoneSerializer` (lines 341-361)
- Updated `ContractSerializer` with zone-related fields:
  - `contract_zones` (nested ContractZoneSerializer)
  - `active_zone_count` (method field)
  - `total_zone_count` (method field)
- Updated `ZoneSerializer` with contract-related fields:
  - `current_contract` (method field - returns active contract details)
  - `contract_count` (method field - total historical contracts)

### 2. `/crm_app/views.py`
**Changes:**
- Added `ContractZone` to model imports
- Added `ContractZoneSerializer` to serializer imports
- Created 3 custom actions in `ContractViewSet`:
  - `add_zones()` - POST /api/v1/contracts/{id}/add-zones/
  - `get_zones()` - GET /api/v1/contracts/{id}/zones/
  - `remove_zone()` - POST /api/v1/contracts/{id}/remove-zone/
- Created 1 custom action in `ZoneViewSet`:
  - `get_contracts()` - GET /api/v1/zones/{id}/contracts/

## API Endpoints

### Contract Endpoints

#### 1. Add Zones to Contract
**URL:** `POST /api/v1/contracts/{id}/add-zones/`

**Request Body:**
```json
{
  "zones": [
    {"name": "Pool Bar", "platform": "soundtrack", "notes": "Optional notes"},
    {"id": "existing-zone-uuid"}
  ]
}
```

**Features:**
- Creates new zones OR links existing zones
- Validates zone existence and prevents duplicates
- Uses transaction.atomic() for all-or-nothing operations
- Returns HTTP 207 (Multi-Status) if partial success with errors
- Returns HTTP 201 (Created) if all successful

**Response (Success):**
```json
[
  {
    "id": "uuid",
    "name": "Pool Bar",
    "platform": "soundtrack",
    "status": "pending",
    "company": "uuid",
    "current_contract": {
      "id": "uuid",
      "contract_number": "C-2024-1201-001",
      "status": "Active",
      "start_date": "2024-01-01",
      "end_date": null
    },
    "contract_count": 1
  }
]
```

**Response (Partial Success):**
```json
{
  "zones": [...],
  "errors": [
    "Zone 2: Zone 'Pool Bar' already linked to this contract"
  ],
  "success_count": 2,
  "error_count": 1
}
```

#### 2. Get Contract Zones
**URL:** `GET /api/v1/contracts/{id}/zones/`

**Query Parameters:**
- `active` (optional): `true|false` - Filter by is_active status
- `as_of` (optional): `YYYY-MM-DD` - Get zones active on specific date

**Examples:**
- Get all zones (active + historical): `/api/v1/contracts/{id}/zones/`
- Get only active zones: `/api/v1/contracts/{id}/zones/?active=true`
- Get zones as of date: `/api/v1/contracts/{id}/zones/?as_of=2024-06-15`

**Features:**
- Returns ContractZone relationships (not just zones)
- Supports historical queries
- Uses select_related() for optimized queries

**Response:**
```json
[
  {
    "id": "uuid",
    "contract": "uuid",
    "contract_number": "C-2024-1201-001",
    "zone": "uuid",
    "zone_id": "uuid",
    "zone_name": "Pool Bar",
    "zone_platform": "soundtrack",
    "zone_status": "online",
    "company_name": "Hilton Pattaya",
    "start_date": "2024-01-01",
    "end_date": null,
    "is_active": true,
    "notes": "Zone added during initial setup",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

#### 3. Remove Zone from Contract
**URL:** `POST /api/v1/contracts/{id}/remove-zone/`

**Request Body:**
```json
{
  "zone_id": "uuid"
}
```

**Features:**
- Sets end_date to current date
- Sets is_active to false
- Maintains historical record
- Does NOT delete the zone or relationship

**Response:**
```json
{
  "id": "uuid",
  "contract": "uuid",
  "zone": "uuid",
  "start_date": "2024-01-01",
  "end_date": "2024-12-01",
  "is_active": false,
  "notes": "Zone added during initial setup",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-12-01T10:30:00Z"
}
```

### Zone Endpoints

#### 4. Get Zone Contracts
**URL:** `GET /api/v1/zones/{id}/contracts/`

**Query Parameters:**
- `active` (optional): `true|false` - Filter by is_active status

**Examples:**
- Get all contracts: `/api/v1/zones/{id}/contracts/`
- Get active contract only: `/api/v1/zones/{id}/contracts/?active=true`

**Features:**
- Returns all contracts (active + historical) for this zone
- Useful for contract renewal tracking
- Uses select_related() for optimization

**Response:**
```json
[
  {
    "id": "uuid",
    "contract": "uuid",
    "contract_number": "C-2024-1201-001",
    "zone": "uuid",
    "zone_id": "uuid",
    "zone_name": "Pool Bar",
    "zone_platform": "soundtrack",
    "zone_status": "online",
    "company_name": "Hilton Pattaya",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "is_active": false,
    "notes": "Original contract",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-12-31T23:59:00Z"
  },
  {
    "id": "uuid",
    "contract": "uuid",
    "contract_number": "C-2025-0101-001",
    "zone": "uuid",
    "zone_id": "uuid",
    "zone_name": "Pool Bar",
    "zone_platform": "soundtrack",
    "zone_status": "online",
    "company_name": "Hilton Pattaya",
    "start_date": "2025-01-01",
    "end_date": null,
    "is_active": true,
    "notes": "Renewal contract",
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z"
  }
]
```

## Enhanced Serializer Fields

### ContractSerializer
Now includes:
- `contract_zones`: List of ContractZone relationships (read-only)
- `active_zone_count`: Count of currently active zones (computed)
- `total_zone_count`: Total count including historical zones (computed)

**Example response when fetching a contract:**
```json
{
  "id": "uuid",
  "contract_number": "C-2024-1201-001",
  "company": "uuid",
  "company_name": "Hilton Pattaya",
  "status": "Active",
  "contract_zones": [
    {
      "id": "uuid",
      "zone_name": "Pool Bar",
      "is_active": true,
      "start_date": "2024-01-01"
    }
  ],
  "active_zone_count": 4,
  "total_zone_count": 6
}
```

### ZoneSerializer
Now includes:
- `current_contract`: Active contract details (computed, null if none)
- `contract_count`: Total number of contracts linked to this zone (computed)

**Example response when fetching a zone:**
```json
{
  "id": "uuid",
  "name": "Pool Bar",
  "company": "uuid",
  "company_name": "Hilton Pattaya",
  "platform": "soundtrack",
  "status": "online",
  "current_contract": {
    "id": "uuid",
    "contract_number": "C-2025-0101-001",
    "status": "Active",
    "start_date": "2025-01-01",
    "end_date": null
  },
  "contract_count": 2
}
```

## Query Optimizations Applied

All custom actions use query optimization:
- `select_related('zone', 'contract')` for ContractZone queries
- `select_related('contract')` for active contract lookups
- Proper ordering: `-start_date` for chronological history

## Error Handling

The API provides clear error messages:

### 400 Bad Request
- Missing required fields: `{"error": "No zones provided"}`
- Invalid zone data: `{"error": "Missing required fields 'name' or 'platform'"}`
- Missing zone_id: `{"error": "zone_id is required"}`

### 404 Not Found
- Zone not found: `"Zone {i+1}: Zone with id {zone_id} not found"`
- Active link not found: `{"error": "Active zone link not found"}`

### 207 Multi-Status
- Partial success with errors (includes successful zones + error list)

## Business Logic

### Add Zones
1. Accepts array of zone objects
2. Each zone can be:
   - New zone: `{"name": "X", "platform": "Y"}` → creates Zone + ContractZone
   - Existing zone: `{"id": "uuid"}` → creates ContractZone link only
3. Validates:
   - Zone exists (if linking existing)
   - Required fields present (if creating new)
   - No duplicate active links
4. Uses transaction for atomicity
5. Returns partial results if some fail

### Remove Zone
1. Finds active ContractZone link
2. Sets `end_date = today`
3. Sets `is_active = False`
4. Preserves historical record
5. Zone itself remains in database

### Historical Tracking
- All queries support `active=true/false` filtering
- Date-based queries: `as_of=YYYY-MM-DD`
- Maintains complete audit trail
- Supports contract renewal workflows

## Testing

All functionality tested and verified:
- ✅ Serializer field structure
- ✅ Create/link zones to contracts
- ✅ Query active vs. historical zones
- ✅ Remove zones (soft delete)
- ✅ Historical date queries
- ✅ Query optimization (select_related)
- ✅ Error handling
- ✅ Transaction safety

## Migration Status

Migration `0035_add_contract_zone_relationship` applied successfully:
- Creates `crm_app_contractzone` table
- Adds ManyToMany relationship to Contract model
- Adds 'cancelled' status to Zone model

## Next Steps (Phase 3 - Frontend)

Frontend integration will need:
1. Zone management UI in contract detail page
2. Add/remove zone buttons
3. Historical zone view with timeline
4. Contract renewal workflow with zone migration
5. Visual indicators for active vs. cancelled zones

## Files Reference

**Modified Files:**
- `/crm_app/serializers.py` - Serializers with zone/contract fields
- `/crm_app/views.py` - ViewSets with custom actions

**Related Files (from Phase 1):**
- `/crm_app/models.py` - ContractZone model, Contract.zones relationship
- `/crm_app/migrations/0035_add_contract_zone_relationship.py` - Database schema

## API Usage Examples

### Example 1: Create Contract with Zones
```python
# 1. Create contract
response = requests.post('/api/v1/contracts/', {
    "company": "uuid",
    "contract_type": "Annual",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "value": "50000",
    "currency": "USD"
})
contract_id = response.json()['id']

# 2. Add zones
requests.post(f'/api/v1/contracts/{contract_id}/add-zones/', {
    "zones": [
        {"name": "Lobby", "platform": "soundtrack"},
        {"name": "Dining", "platform": "soundtrack"},
        {"name": "Gym", "platform": "soundtrack"}
    ]
})
```

### Example 2: Contract Renewal with Zone Migration
```python
# Get zones from old contract
old_contract_id = "uuid"
response = requests.get(f'/api/v1/contracts/{old_contract_id}/zones/?active=true')
active_zones = [zone['zone_id'] for zone in response.json()]

# Create new contract
new_contract = requests.post('/api/v1/contracts/', {...}).json()

# Link same zones to new contract
requests.post(f'/api/v1/contracts/{new_contract["id"]}/add-zones/', {
    "zones": [{"id": zone_id} for zone_id in active_zones]
})

# Remove zones from old contract
for zone_id in active_zones:
    requests.post(f'/api/v1/contracts/{old_contract_id}/remove-zone/', {
        "zone_id": zone_id
    })
```

### Example 3: Historical Query
```python
# Get zones active on June 15, 2024
response = requests.get(f'/api/v1/contracts/{contract_id}/zones/?as_of=2024-06-15')
historical_zones = response.json()

# Get all contracts for a zone (including historical)
response = requests.get(f'/api/v1/zones/{zone_id}/contracts/')
all_contracts = response.json()
```

## Technical Decisions

### Why ContractZone Instead of Direct ManyToMany?
- Historical tracking: Need start_date, end_date, is_active
- Contract renewals: Same zone can move between contracts
- Audit trail: Complete history of zone assignments
- Business logic: Notes, custom fields per relationship

### Why Separate add-zones Endpoint?
- Supports batch operations (add multiple zones at once)
- Allows creating new zones AND linking existing zones
- Transaction safety (all-or-nothing)
- Clear separation from contract creation

### Why Soft Delete (is_active=False)?
- Maintain audit trail for compliance
- Support historical reporting
- Enable "what zones were on contract X in 2023?" queries
- Prevent accidental data loss

## Performance Considerations

All queries use:
- `select_related()` for FK lookups (contract, zone)
- Proper database indexes (from Phase 1 migration)
- Pagination support (via DRF's default pagination)
- Read-only serializer fields where appropriate

Expected query counts:
- Get contract with zones: 2 queries (contract + contract_zones with select_related)
- Add zones: 1 query per zone + 1 for ContractZone creation
- Remove zone: 1 query (get) + 1 query (update)

## Security

- All endpoints require authentication (IsAuthenticated permission)
- Uses existing RoleBasedPermission from BaseModelViewSet
- Transaction safety prevents partial updates
- Input validation on all endpoints
- UUID validation for zone_id/contract_id

---

**Implementation Complete:** November 25, 2025
**Phase:** 2 - API Layer
**Status:** Ready for Frontend Integration (Phase 3)
