# Contract-Zone Integration - Usage Guide

**Phase 1 Complete**: Backend data model with historical tracking
**Target Users**: Sales Team, Tech Support, Admins

---

## Quick Start

### What's New?
Contracts can now be linked to zones with complete historical tracking. When you terminate a contract, all linked zones are automatically marked as cancelled.

### Key Concepts

1. **ContractZone**: Links a zone to a contract with start/end dates
2. **Historical Tracking**: View what zones were on a contract at any point in time
3. **Auto-Termination**: Ending a contract automatically cancels its zones
4. **Renewals**: New contract can link to same zones (creates new history)

---

## Django Admin Usage

### Linking Zones to a Contract

**Method 1: From Contract Admin Page**
1. Go to Admin → Contracts → Select contract
2. Scroll to "Contract zones" section (inline table)
3. Click "Add another Contract zone"
4. Select zone from dropdown
5. Set start date (typically contract start date)
6. Leave end date blank (means "currently active")
7. Check "is_active" box
8. Add notes if needed
9. Click "Save"

**Method 2: From ContractZone Admin**
1. Go to Admin → Contract zones → Add contract zone
2. Fill in all fields:
   - Contract: Select from dropdown
   - Zone: Select from dropdown
   - Start date: When zone was added to contract
   - End date: When zone was removed (blank = active)
   - Is active: Check if currently covered
   - Notes: Optional internal notes
3. Click "Save"

### Viewing Zone History for a Contract

**Quick View (Contract Admin)**
1. Go to Admin → Contracts → Select contract
2. Scroll to "Contract zones" inline table
3. See all zones (past and present) with dates

**Detailed View (ContractZone Admin)**
1. Go to Admin → Contract zones
2. Filter by contract or use search
3. See complete history with timestamps
4. Use date hierarchy to browse by start date

### Finding Active Contract for a Zone

Currently via Python/Django shell (API coming in Phase 2):
```python
from crm_app.models import Zone
zone = Zone.objects.get(name="Lobby Music")
active_contract = zone.get_active_contract()
print(f"Zone is on contract: {active_contract}")
```

---

## Common Workflows

### Workflow 1: New Contract with Zones

**Scenario**: Sales closes a deal for 5 music zones

**Steps**:
1. Create Contract in admin (status: 'Signed')
2. Save the contract
3. Scroll to "Contract zones" section
4. Add 5 ContractZone entries:
   - Zone 1: Lobby, start_date = contract start, is_active = True
   - Zone 2: Restaurant, start_date = contract start, is_active = True
   - Zone 3: Pool, start_date = contract start, is_active = True
   - Zone 4: Gym, start_date = contract start, is_active = True
   - Zone 5: Bar, start_date = contract start, is_active = True
5. Save contract
6. Tech Support now sees these zones linked to the contract

### Workflow 2: Contract Termination

**Scenario**: Client cancels contract

**Steps**:
1. Go to Admin → Contracts → Select contract
2. Change status to 'Terminated'
3. Click "Save"

**What Happens Automatically**:
- All active ContractZone links set to is_active = False
- All ContractZone.end_date set to today
- All linked zones set to status = 'cancelled'
- Log entries created for audit trail

**No manual zone updates needed!**

### Workflow 3: Contract Renewal

**Scenario**: Client renews contract with same zones

**Steps**:
1. Create new Contract (new contract number, new dates)
2. Scroll to "Contract zones" section
3. Link the SAME zones to new contract:
   - Zone 1: Lobby, start_date = new contract start, is_active = True
   - Zone 2: Restaurant, start_date = new contract start, is_active = True
   - (etc.)
4. Save new contract

**Result**:
- Each zone now has 2 ContractZone records (one per contract)
- Old contract shows historical zones with end dates
- New contract shows active zones
- Complete audit trail maintained

### Workflow 4: Adding Zone Mid-Contract

**Scenario**: Client adds a zone during contract period

**Steps**:
1. Go to Admin → Contracts → Select contract
2. Scroll to "Contract zones" section
3. Click "Add another Contract zone"
4. Select new zone
5. Set start_date = date zone was added (not contract start)
6. Check is_active
7. Save

**Note**: Start date accurately reflects when zone was added.

### Workflow 5: Removing Zone Mid-Contract

**Scenario**: Client removes a zone before contract ends

**Steps**:
1. Go to Admin → Contract zones
2. Find the ContractZone for this zone + contract
3. Click to edit
4. Set end_date = date zone was removed
5. Uncheck is_active
6. Add note: "Client requested removal"
7. Save

**Result**: Historical record preserved, zone marked as inactive.

---

## Query Examples (Python/Django Shell)

### Get all active zones for a contract
```python
from crm_app.models import Contract
contract = Contract.objects.get(contract_number="C-2025-001")
active_zones = contract.get_active_zones()
print(f"Active zones: {active_zones.count()}")
for zone in active_zones:
    print(f"  - {zone.name}")
```

### Get zone count for a contract
```python
contract = Contract.objects.get(contract_number="C-2025-001")
count = contract.get_zone_count()
print(f"Contract has {count} active zones")
```

### Get historical zones (as of specific date)
```python
from datetime import date
contract = Contract.objects.get(contract_number="C-2024-001")
as_of = date(2024, 6, 15)
zones = contract.get_historical_zones(as_of_date=as_of)
print(f"Zones active on {as_of}: {zones.count()}")
```

### Get all zones ever on a contract
```python
contract = Contract.objects.get(contract_number="C-2024-001")
all_zones = contract.get_historical_zones()  # No date = all time
print(f"Total zones ever: {all_zones.count()}")
```

### Get active contract for a zone
```python
from crm_app.models import Zone
zone = Zone.objects.get(name__icontains="Lobby")
contract = zone.get_active_contract()
if contract:
    print(f"Zone is on contract: {contract.contract_number}")
else:
    print("Zone has no active contract")
```

### Get contract history for a zone
```python
zone = Zone.objects.get(name__icontains="Lobby")
history = zone.get_contract_history()
print(f"Zone contract history:")
for link in history:
    status = "Active" if link.is_active else "Ended"
    print(f"  {link.contract.contract_number}: {link.start_date} - {link.end_date or 'Present'} ({status})")
```

---

## Admin Search & Filters

### ContractZone Admin Filters
- **Is active**: Show only active/inactive zone links
- **Start date**: Browse by when zones were added
- **End date**: Browse by when zones were removed

### ContractZone Admin Search
Search by:
- Contract number: "C-2025-001"
- Zone name: "Lobby Music"
- Company name: "Hilton Pattaya"

### Date Hierarchy
Click on year/month to drill down into zone additions by date.

---

## Data Integrity Features

### Protection Rules
1. **Cannot delete zone if linked to contract**: PROTECT constraint prevents orphaned contracts
2. **Cannot delete ContractZone via admin**: Delete permission disabled for safety
3. **Zone is readonly after creation**: Prevents accidental zone changes in inline
4. **Unique constraint**: Same zone can't be added to contract on same date twice

### Automatic Actions
1. **Contract termination**: Automatically closes all zone links and cancels zones
2. **Cascade delete**: Deleting contract removes its ContractZone links
3. **Logging**: All automatic actions logged for audit trail

---

## Troubleshooting

### Q: I can't delete a zone
**A**: Zone is linked to a contract. Either:
- Remove the ContractZone link first (set is_active=False, add end_date)
- Or this is working as intended (data protection)

### Q: Zone isn't showing in Contract admin
**A**: Check:
1. ContractZone exists with is_active=True
2. Zone hasn't been deleted
3. Start date is valid
4. Inline table is expanded (may be collapsed)

### Q: Contract termination didn't cancel zones
**A**: Check:
1. Contract status is exactly 'Terminated' (case-sensitive)
2. Signal handler is registered (check apps.py has ready() method)
3. Check logs for errors
4. Verify ContractZone.is_active was True before termination

### Q: Can't edit zone in Contract inline
**A**: By design. Zone field is readonly after creation to prevent:
- Accidentally changing which zone is linked
- Data integrity issues
- To change zone: delete ContractZone and create new one

### Q: Duplicate zone error
**A**: You're trying to add the same zone to the same contract on the same start date. Either:
- Use a different start date (if re-adding later)
- Update the existing ContractZone instead
- This protection prevents data duplication

---

## Best Practices

### Start Dates
- **New contract**: Use contract start_date
- **Mid-contract addition**: Use actual date zone was added
- **Contract renewal**: Use new contract start_date (not old contract dates)

### End Dates
- **Leave blank** for currently active zones
- **Set to actual date** when zone is removed mid-contract
- **Automatic** when contract is terminated (set to termination date)

### Notes Field
Use notes to document:
- Why zone was added mid-contract
- Client requests or special circumstances
- Issues or exceptions
- Migration from old system

### Data Hygiene
- Review inactive zones periodically
- Archive old contracts with ended zone links
- Document contract renewals in notes
- Keep zone names consistent

---

## Reporting Queries

### Contracts by Zone Count
```python
from django.db.models import Count
from crm_app.models import Contract

contracts = Contract.objects.annotate(
    zone_count=Count('contract_zones', filter=Q(contract_zones__is_active=True))
).filter(zone_count__gt=0).order_by('-zone_count')

for contract in contracts:
    print(f"{contract.contract_number}: {contract.zone_count} zones")
```

### Zones by Contract History
```python
from django.db.models import Count
from crm_app.models import Zone

zones = Zone.objects.annotate(
    contract_count=Count('zone_contracts')
).filter(contract_count__gt=1).order_by('-contract_count')

for zone in zones:
    print(f"{zone.name}: {zone.contract_count} contracts (includes renewals)")
```

### Active vs Cancelled Zones
```python
from crm_app.models import Zone
from django.db.models import Count

stats = Zone.objects.values('status').annotate(count=Count('id'))
for stat in stats:
    print(f"{stat['status']}: {stat['count']} zones")
```

---

## Future Enhancements (Coming in Phase 2+)

### API Endpoints (Phase 2)
- REST API for ContractZone management
- Bulk zone creation from contract
- Zone status updates
- Historical queries via API

### Frontend UI (Phase 3)
- Visual zone selector in contract form
- Drag-and-drop zone management
- Timeline view of zone-contract history
- Zone health dashboard

### Automation (Phase 4)
- Auto-create zones when contract signed
- Smart renewal workflow (copy zones to new contract)
- Zone monitoring alerts
- Predictive zone health scoring

---

## Getting Help

### For Technical Issues
- Check Django admin logs
- Review signal handler logs
- Run `python manage.py check`
- Contact Tech Support

### For Business Process Questions
- Review this guide's workflows section
- Contact Sales Manager for contract questions
- Contact Tech Support for zone technical issues

---

**Last Updated**: November 25, 2025
**Phase**: 1 (Data Model Complete)
**Next Phase**: API Layer (TBD)
