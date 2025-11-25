# Contract-Zone API Quick Reference

## Endpoints Cheat Sheet

### Contract Endpoints

```bash
# Add zones to contract (create new or link existing)
POST /api/v1/contracts/{contract_id}/add-zones/
Body: {"zones": [{"name": "Pool", "platform": "soundtrack"}, {"id": "zone-uuid"}]}

# Get all zones for contract
GET /api/v1/contracts/{contract_id}/zones/

# Get active zones only
GET /api/v1/contracts/{contract_id}/zones/?active=true

# Get zones as of specific date
GET /api/v1/contracts/{contract_id}/zones/?as_of=2024-06-15

# Remove zone from contract (soft delete)
POST /api/v1/contracts/{contract_id}/remove-zone/
Body: {"zone_id": "uuid"}
```

### Zone Endpoints

```bash
# Get all contracts for zone
GET /api/v1/zones/{zone_id}/contracts/

# Get active contract only
GET /api/v1/zones/{zone_id}/contracts/?active=true
```

## Response Structure

### ContractZone Object
```json
{
  "id": "uuid",
  "contract": "contract-uuid",
  "contract_number": "C-2024-1201-001",
  "zone": "zone-uuid",
  "zone_id": "zone-uuid",
  "zone_name": "Pool Bar",
  "zone_platform": "soundtrack",
  "zone_status": "online",
  "company_name": "Hilton Pattaya",
  "start_date": "2024-01-01",
  "end_date": null,
  "is_active": true,
  "notes": "",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Contract with Zones
```json
{
  "id": "uuid",
  "contract_number": "C-2024-1201-001",
  "contract_zones": [ContractZone, ...],
  "active_zone_count": 4,
  "total_zone_count": 6
}
```

### Zone with Contract
```json
{
  "id": "uuid",
  "name": "Pool Bar",
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

## Common Use Cases

### 1. Add Zones When Creating Contract
```javascript
// Create contract
const contract = await api.post('/api/v1/contracts/', contractData);

// Add zones
await api.post(`/api/v1/contracts/${contract.id}/add-zones/`, {
  zones: [
    {name: 'Lobby', platform: 'soundtrack'},
    {name: 'Dining', platform: 'soundtrack'}
  ]
});
```

### 2. Contract Renewal (Move Zones to New Contract)
```javascript
// Get active zones from old contract
const oldZones = await api.get(
  `/api/v1/contracts/${oldContractId}/zones/?active=true`
);

// Create new contract
const newContract = await api.post('/api/v1/contracts/', newContractData);

// Link zones to new contract
await api.post(`/api/v1/contracts/${newContract.id}/add-zones/`, {
  zones: oldZones.map(cz => ({id: cz.zone_id}))
});

// Remove zones from old contract
for (const cz of oldZones) {
  await api.post(`/api/v1/contracts/${oldContractId}/remove-zone/`, {
    zone_id: cz.zone_id
  });
}
```

### 3. View Zone History
```javascript
// Get all contracts this zone has been linked to
const contracts = await api.get(`/api/v1/zones/${zoneId}/contracts/`);

// Display timeline
contracts.forEach(cz => {
  console.log(`${cz.contract_number}: ${cz.start_date} - ${cz.end_date || 'current'}`);
});
```

### 4. Report: Zones on Contract at Specific Date
```javascript
// Get zones active on June 15, 2024
const historicalZones = await api.get(
  `/api/v1/contracts/${contractId}/zones/?as_of=2024-06-15`
);
```

## Error Handling

```javascript
try {
  const response = await api.post(`/api/v1/contracts/${id}/add-zones/`, data);

  // Check for partial success (HTTP 207)
  if (response.status === 207) {
    console.log(`Success: ${response.data.success_count}`);
    console.log(`Errors: ${response.data.error_count}`);
    console.error(response.data.errors);
  }

} catch (error) {
  if (error.response.status === 400) {
    // Validation error
    console.error(error.response.data.error);
  } else if (error.response.status === 404) {
    // Not found
    console.error('Resource not found');
  }
}
```

## Database Schema Reference

### ContractZone Model
- `id` (UUID, PK)
- `contract` (FK → Contract)
- `zone` (FK → Zone, PROTECT)
- `start_date` (Date)
- `end_date` (Date, nullable)
- `is_active` (Boolean, default True)
- `notes` (Text)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### Relationships
- `Contract.zones` → ManyToMany via ContractZone
- `Contract.contract_zones` → ContractZone objects for this contract
- `Zone.contracts` → ManyToMany via ContractZone
- `Zone.zone_contracts` → ContractZone objects for this zone

## Query Performance Tips

1. Use `active=true` filter when only current zones needed
2. The API uses `select_related()` internally - no N+1 queries
3. Results ordered by `-start_date` (newest first)
4. Pagination applies to all list endpoints

## Business Rules

1. **Zone Creation:** New zones default to `status='pending'`
2. **Duplicate Prevention:** Cannot link same zone to contract twice (if active)
3. **Soft Delete:** Removing zone sets `is_active=False`, `end_date=today`
4. **Historical Tracking:** All zone-contract relationships preserved
5. **Protection:** Cannot delete Zone if linked to any contract (PROTECT constraint)

## Testing Checklist

- [ ] Create contract and add zones
- [ ] Link existing zone to contract
- [ ] Query active zones
- [ ] Query historical zones with date filter
- [ ] Remove zone from contract
- [ ] Verify soft delete (zone still exists)
- [ ] Test duplicate prevention
- [ ] Test error handling (404, 400)
- [ ] Verify transaction rollback on error
- [ ] Test contract renewal workflow

---

**Quick Start:** See `CONTRACT_ZONE_API_SUMMARY.md` for complete documentation.
