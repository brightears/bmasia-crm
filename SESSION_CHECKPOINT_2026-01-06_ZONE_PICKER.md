# Session Checkpoint: Zone Picker & Deduplication Fix
**Date**: January 6, 2026
**Status**: ✅ COMPLETE

## Summary

Implemented Zone Picker component to replace manual zone text entry in contracts. Fixed Soundtrack sync deduplication to prevent duplicate zones.

## Problem Solved

When creating contracts, users manually typed zone names which created **new Zone records**. When Soundtrack synced, it also created zones. This resulted in **duplicates** for the same physical location:
- Manual zone: Has contract linked, no Soundtrack data
- Synced zone: Has Soundtrack status/device info, no contract

**Example**: "Canvas Ploenchit" appeared twice - one manual (pending, with contract) and one synced (online, no contract).

## Solution Implemented

### 1. Zone Picker Component (NEW)

**File**: `bmasia-crm-frontend/src/components/ZonePicker.tsx`

Features:
- Multi-select Autocomplete dropdown
- Filters zones by selected company
- Shows zone status indicators (Online/Offline/Pending/No Device)
- Displays platform (Soundtrack/Beat Breeze)
- Shows warning if no zones exist for company
- Requires company selection first

### 2. Fixed Soundtrack Sync Deduplication

**File**: `crm_app/services/soundtrack_api.py`

Changed `sync_company_zones()` method:
```python
# OLD: Only matched by name + platform (could miss existing zones)
zone, created = Zone.objects.get_or_create(
    company=company,
    name=zone_name,
    platform='soundtrack',
    defaults={...}
)

# NEW: Three-tier matching
# 1. PRIMARY: Match by soundtrack_zone_id (unique API identifier)
zone = company.zones.filter(soundtrack_zone_id=zone_id).first()

if not zone:
    # 2. FALLBACK: Match by name + platform (catches manually created zones)
    zone = company.zones.filter(name=zone_name, platform='soundtrack').first()

if not zone:
    # 3. CREATE: Only if no match found
    zone = Zone.objects.create(...)
```

### 3. Update Contract Zones Endpoint (NEW)

**File**: `crm_app/views.py`

New endpoint: `PUT /api/v1/contracts/{id}/update-zones/`

```python
@action(detail=True, methods=['put'], url_path='update-zones')
def update_zones(self, request, pk=None):
    """Replace all zones for a contract with provided zone IDs"""
    contract = self.get_object()
    zone_ids = request.data.get('zone_ids', [])

    with transaction.atomic():
        # Deactivate current zones
        ContractZone.objects.filter(contract=contract, is_active=True).update(
            is_active=False, end_date=timezone.now().date()
        )

        # Activate/create links for new zones
        for zone_id in zone_ids:
            zone = Zone.objects.get(id=zone_id)
            ContractZone.objects.update_or_create(
                contract=contract, zone=zone,
                defaults={'is_active': True, 'end_date': None, ...}
            )

    return Response(ContractZoneSerializer(active_zones, many=True).data)
```

### 4. Updated ContractForm

**File**: `bmasia-crm-frontend/src/components/ContractForm.tsx`

Changes:
- Replaced `zones: ZoneFormData[]` state with `selectedZones: Zone[]`
- Added `ZonePicker` component instead of manual text fields
- Clears zones when company changes
- Loads existing zones when editing a contract
- Calls `ApiService.updateContractZones()` on save

### 5. Frontend API Method

**File**: `bmasia-crm-frontend/src/services/api.ts`

```typescript
async updateContractZones(contractId: string, zoneIds: string[]): Promise<ContractZone[]> {
  const response = await authApi.put(`/contracts/${contractId}/update-zones/`, {
    zone_ids: zoneIds
  });
  return response.data;
}
```

## Duplicate Cleanup

Created one-time management command to clean up existing duplicates:

**File**: `crm_app/management/commands/cleanup_duplicate_zone.py`

Ran on production to fix Canvas Ploenchit duplicate:
1. Transferred contract C-2026-0105-001 to synced zone
2. Deleted inactive ContractZone record
3. Deleted manual duplicate zone

**Result**: Only 1 "Canvas Ploenchit" zone remains with:
- Online status ✅
- Device name (FLG-FN7R224) ✅
- Contract linked ✅
- Soundtrack sync data ✅

## New User Workflow

1. **Sync zones first**: Go to Zone Status → Click "Sync All Zones"
2. **Create contract**: Select company → Zone picker shows synced zones → Select zones
3. **Edit contract**: Zone picker pre-populated with linked zones → Add/remove as needed

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `crm_app/services/soundtrack_api.py` | Modified | Fixed deduplication logic |
| `crm_app/views.py` | Modified | Added `update_zones` action |
| `bmasia-crm-frontend/src/components/ZonePicker.tsx` | **Created** | New zone picker component |
| `bmasia-crm-frontend/src/components/ContractForm.tsx` | Modified | Uses ZonePicker |
| `bmasia-crm-frontend/src/components/index.ts` | Modified | Export ZonePicker |
| `bmasia-crm-frontend/src/services/api.ts` | Modified | Added updateContractZones |
| `crm_app/management/commands/cleanup_duplicate_zone.py` | **Created** | One-time cleanup script |

## Commits

- `0f5a9507` - Feature: Zone Picker for Contract Forms
- `f30b3122` - Add cleanup script for duplicate Canvas Ploenchit zone

## Production URLs

- **Frontend**: https://bmasia-crm-frontend.onrender.com
- **Backend API**: https://bmasia-crm.onrender.com

## Technical Notes

- ZonePicker uses `ApiService.getZonesByCompany()` to fetch available zones
- Contract zones are linked via `ContractZone` through model (ManyToMany)
- `update-zones` endpoint uses atomic transaction for data integrity
- Zone deletion is protected by ContractZone foreign key - must delete ContractZone first
