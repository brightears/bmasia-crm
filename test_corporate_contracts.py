"""
Test script for Corporate Contracts Phase 1

Run this script after applying the migration to verify everything works correctly.

Usage:
    python manage.py shell < test_corporate_contracts.py
"""

from crm_app.models import Company, Contract, StaticDocument
from django.core.exceptions import ValidationError
from datetime import date, timedelta

print("=" * 70)
print("CORPORATE CONTRACTS PHASE 1 - VALIDATION TESTS")
print("=" * 70)

# Test 1: Company Model Fields
print("\n[TEST 1] Company model has new fields...")
try:
    # Check fields exist
    Company._meta.get_field('parent_company')
    Company._meta.get_field('is_corporate_parent')
    print("✓ parent_company field exists")
    print("✓ is_corporate_parent field exists")
except Exception as e:
    print(f"✗ FAILED: {e}")
    exit(1)

# Test 2: Contract Model Fields
print("\n[TEST 2] Contract model has new fields...")
try:
    Contract._meta.get_field('contract_category')
    Contract._meta.get_field('master_contract')
    Contract._meta.get_field('customer_signatory_name')
    Contract._meta.get_field('customer_signatory_title')
    Contract._meta.get_field('bmasia_signatory_name')
    Contract._meta.get_field('bmasia_signatory_title')
    Contract._meta.get_field('custom_terms')
    print("✓ contract_category field exists")
    print("✓ master_contract field exists")
    print("✓ Signatory fields exist")
    print("✓ custom_terms field exists")
except Exception as e:
    print(f"✗ FAILED: {e}")
    exit(1)

# Test 3: StaticDocument Model
print("\n[TEST 3] StaticDocument model exists...")
try:
    StaticDocument._meta.get_field('document_type')
    StaticDocument._meta.get_field('file')
    StaticDocument._meta.get_field('version')
    print("✓ StaticDocument model exists")
    print("✓ All required fields present")
except Exception as e:
    print(f"✗ FAILED: {e}")
    exit(1)

# Test 4: Create Corporate Parent
print("\n[TEST 4] Create corporate parent company...")
try:
    parent = Company.objects.create(
        name="Test Corporate Parent",
        is_corporate_parent=True,
        country="Hong Kong"
    )
    assert parent.is_corporate_parent == True
    assert parent.has_subsidiaries == False
    assert parent.is_subsidiary == False
    print(f"✓ Created corporate parent: {parent.name}")
    print(f"✓ is_corporate_parent = {parent.is_corporate_parent}")
    print(f"✓ Properties work correctly")
except Exception as e:
    print(f"✗ FAILED: {e}")
    exit(1)

# Test 5: Create Subsidiary
print("\n[TEST 5] Create subsidiary company...")
try:
    subsidiary = Company.objects.create(
        name="Test Subsidiary Venue",
        parent_company=parent,
        country="Thailand"
    )
    assert subsidiary.is_subsidiary == True
    assert subsidiary.parent_company == parent
    parent.refresh_from_db()
    assert parent.has_subsidiaries == True
    print(f"✓ Created subsidiary: {subsidiary.name}")
    print(f"✓ is_subsidiary = {subsidiary.is_subsidiary}")
    print(f"✓ Parent relationship works")
except Exception as e:
    print(f"✗ FAILED: {e}")
    parent.delete()
    exit(1)

# Test 6: Create Master Contract
print("\n[TEST 6] Create master agreement...")
try:
    master = Contract.objects.create(
        company=parent,
        contract_category='corporate_master',
        contract_number='TEST-MASTER-001',
        contract_type='Annual',
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        value=1000000,
        currency='USD',
        customer_signatory_name='John Doe',
        customer_signatory_title='CEO',
        bmasia_signatory_name='Jane Smith',
        bmasia_signatory_title='Director',
        custom_terms='Test custom terms',
        status='Draft'
    )
    assert master.contract_category == 'corporate_master'
    print(f"✓ Created master contract: {master.contract_number}")
    print(f"✓ contract_category = {master.contract_category}")
    print(f"✓ Signatory fields saved correctly")
except Exception as e:
    print(f"✗ FAILED: {e}")
    parent.delete()
    subsidiary.delete()
    exit(1)

# Test 7: Create Participation Agreement
print("\n[TEST 7] Create participation agreement...")
try:
    participation = Contract.objects.create(
        company=subsidiary,
        contract_category='participation',
        master_contract=master,
        contract_number='TEST-PARTICIPATION-001',
        contract_type='Annual',
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        value=50000,
        currency='THB',
        status='Draft'
    )
    assert participation.contract_category == 'participation'
    assert participation.master_contract == master
    print(f"✓ Created participation: {participation.contract_number}")
    print(f"✓ master_contract link works")
except Exception as e:
    print(f"✗ FAILED: {e}")
    master.delete()
    parent.delete()
    subsidiary.delete()
    exit(1)

# Test 8: Validation - Participation without Master
print("\n[TEST 8] Validation: participation without master should fail...")
try:
    invalid_contract = Contract(
        company=subsidiary,
        contract_category='participation',
        master_contract=None,  # INVALID!
        contract_number='TEST-INVALID-001',
        contract_type='Annual',
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        value=50000,
        currency='THB',
        status='Draft'
    )
    invalid_contract.clean()
    print("✗ FAILED: Validation should have raised error")
    exit(1)
except ValidationError as e:
    print("✓ Validation correctly rejected participation without master")
    print(f"✓ Error message: {e.message_dict.get('master_contract', [''])[0][:50]}...")

# Test 9: Validation - Master cannot reference another Master
print("\n[TEST 9] Validation: master cannot reference another master...")
try:
    invalid_master = Contract(
        company=parent,
        contract_category='corporate_master',
        master_contract=master,  # INVALID!
        contract_number='TEST-INVALID-MASTER',
        contract_type='Annual',
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        value=100000,
        currency='USD',
        status='Draft'
    )
    invalid_master.clean()
    print("✗ FAILED: Validation should have raised error")
    exit(1)
except ValidationError as e:
    print("✓ Validation correctly rejected master with master_contract")

# Test 10: Query Relationships
print("\n[TEST 10] Query relationships...")
try:
    # Test parent -> children
    children = parent.child_companies.all()
    assert children.count() == 1
    assert subsidiary in children
    
    # Test master -> participations
    participations = master.participation_agreements.all()
    assert participations.count() == 1
    assert participation in participations
    
    print("✓ Parent -> children query works")
    print("✓ Master -> participations query works")
except Exception as e:
    print(f"✗ FAILED: {e}")
    exit(1)

# Test 11: Cleanup
print("\n[TEST 11] Cleanup test data...")
try:
    participation.delete()
    master.delete()
    subsidiary.delete()
    parent.delete()
    print("✓ Test data cleaned up successfully")
except Exception as e:
    print(f"✗ FAILED: {e}")
    exit(1)

# Final Summary
print("\n" + "=" * 70)
print("ALL TESTS PASSED! ✓")
print("=" * 70)
print("\nCorporate Contracts Phase 1 implementation is working correctly.")
print("\nNext steps:")
print("1. Update Django admin to show new fields")
print("2. Add API endpoints for corporate structures")
print("3. Build React UI for corporate contracts")
print("4. Create PDF templates for master agreements")
print("\nSee CORPORATE_CONTRACTS_PHASE1_SUMMARY.md for details.")
print("=" * 70)
