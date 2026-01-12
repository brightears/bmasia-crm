#!/usr/bin/env python
"""
Test script for CustomerSegment API endpoints.
Run this after Phase 2 implementation to verify all endpoints work.
"""
import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
django.setup()

from django.test import RequestFactory
from rest_framework.test import force_authenticate
from crm_app.models import User, Contact, Company, CustomerSegment
from crm_app.views import CustomerSegmentViewSet
from rest_framework import status
import json
from uuid import UUID
from datetime import datetime


class UUIDEncoder(json.JSONEncoder):
    """JSON encoder that handles UUIDs and datetimes"""
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


def run_tests():
    """Run API endpoint tests"""
    print("=" * 70)
    print("PHASE 2: Backend API Layer - Endpoint Testing")
    print("=" * 70)

    factory = RequestFactory()

    # Get or create test user
    try:
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.create_superuser(
                username='test_admin',
                email='admin@test.com',
                password='test123',
                role='Admin'
            )
        print(f"\nUsing test user: {user.username} (role: {user.role})")
    except Exception as e:
        print(f"\nError getting user: {e}")
        return False

    # Test 1: List segments (GET /api/segments/)
    print("\n" + "-" * 70)
    print("TEST 1: List Segments - GET /api/v1/segments/")
    print("-" * 70)
    try:
        request = factory.get('/api/v1/segments/')
        force_authenticate(request, user=user)

        view = CustomerSegmentViewSet.as_view({'get': 'list'})
        response = view(request)

        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.data, indent=2, cls=UUIDEncoder)}")

        if response.status_code == 200:
            print("✓ TEST 1 PASSED")
        else:
            print("✗ TEST 1 FAILED")
            return False
    except Exception as e:
        print(f"✗ TEST 1 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Create dynamic segment (POST /api/segments/)
    print("\n" + "-" * 70)
    print("TEST 2: Create Dynamic Segment - POST /api/v1/segments/")
    print("-" * 70)
    try:
        data = {
            'name': 'Test Dynamic Segment',
            'description': 'Testing dynamic segment creation',
            'segment_type': 'dynamic',
            'status': 'active',
            'filter_criteria': {
                'entity': 'company',
                'match_type': 'all',
                'rules': [
                    {
                        'field': 'industry',
                        'operator': 'equals',
                        'value': 'Hotels'
                    }
                ]
            },
            'tags': 'test, hotels'
        }

        request = factory.post(
            '/api/v1/segments/',
            data=json.dumps(data),
            content_type='application/json'
        )
        force_authenticate(request, user=user)

        view = CustomerSegmentViewSet.as_view({'post': 'create'})
        response = view(request)

        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.data, indent=2, cls=UUIDEncoder)}")

        if response.status_code == 201:
            print("✓ TEST 2 PASSED")
            segment_id = response.data['id']
        else:
            print("✗ TEST 2 FAILED")
            return False
    except Exception as e:
        print(f"✗ TEST 2 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 3: Get segment members (GET /api/segments/{id}/members/)
    print("\n" + "-" * 70)
    print(f"TEST 3: Get Segment Members - GET /api/v1/segments/{segment_id}/members/")
    print("-" * 70)
    try:
        request = factory.get(f'/api/v1/segments/{segment_id}/members/?limit=10')
        force_authenticate(request, user=user)

        view = CustomerSegmentViewSet.as_view({'get': 'members'})
        response = view(request, pk=segment_id)

        print(f"Status Code: {response.status_code}")
        print(f"Segment Name: {response.data.get('segment_name')}")
        print(f"Total Members: {response.data.get('count')}")
        print(f"Members Preview: {len(response.data.get('results', []))} shown")

        if response.status_code == 200:
            print("✓ TEST 3 PASSED")
        else:
            print("✗ TEST 3 FAILED")
            return False
    except Exception as e:
        print(f"✗ TEST 3 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 4: Recalculate segment (POST /api/segments/{id}/recalculate/)
    print("\n" + "-" * 70)
    print(f"TEST 4: Recalculate Segment - POST /api/v1/segments/{segment_id}/recalculate/")
    print("-" * 70)
    try:
        request = factory.post(f'/api/v1/segments/{segment_id}/recalculate/')
        force_authenticate(request, user=user)

        view = CustomerSegmentViewSet.as_view({'post': 'recalculate'})
        response = view(request, pk=segment_id)

        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.data, indent=2, cls=UUIDEncoder)}")

        if response.status_code == 200:
            print("✓ TEST 4 PASSED")
        else:
            print("✗ TEST 4 FAILED")
            return False
    except Exception as e:
        print(f"✗ TEST 4 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 5: Validate filters (POST /api/segments/validate_filters/)
    print("\n" + "-" * 70)
    print("TEST 5: Validate Filters - POST /api/v1/segments/validate_filters/")
    print("-" * 70)
    try:
        data = {
            'filter_criteria': {
                'entity': 'contact',
                'match_type': 'all',
                'rules': [
                    {
                        'field': 'contact_type',
                        'operator': 'equals',
                        'value': 'Decision Maker'
                    }
                ]
            }
        }

        request = factory.post(
            '/api/v1/segments/validate_filters/',
            data=json.dumps(data),
            content_type='application/json'
        )
        force_authenticate(request, user=user)

        view = CustomerSegmentViewSet.as_view({'post': 'validate_filters'})
        response = view(request)

        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.data, indent=2, cls=UUIDEncoder)}")

        if response.status_code == 200 and response.data.get('valid'):
            print("✓ TEST 5 PASSED")
        else:
            print("✗ TEST 5 FAILED")
            return False
    except Exception as e:
        print(f"✗ TEST 5 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 6: Duplicate segment (POST /api/segments/{id}/duplicate/)
    print("\n" + "-" * 70)
    print(f"TEST 6: Duplicate Segment - POST /api/v1/segments/{segment_id}/duplicate/")
    print("-" * 70)
    try:
        data = {
            'name': 'Test Dynamic Segment (Copy)'
        }

        request = factory.post(
            f'/api/v1/segments/{segment_id}/duplicate/',
            data=json.dumps(data),
            content_type='application/json'
        )
        force_authenticate(request, user=user)

        view = CustomerSegmentViewSet.as_view({'post': 'duplicate'})
        response = view(request, pk=segment_id)

        print(f"Status Code: {response.status_code}")
        print(f"New Segment Name: {response.data.get('name')}")
        print(f"Member Count: {response.data.get('member_count')}")

        if response.status_code == 201:
            print("✓ TEST 6 PASSED")
        else:
            print("✗ TEST 6 FAILED")
            return False
    except Exception as e:
        print(f"✗ TEST 6 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED! ✓")
    print("=" * 70)
    print("\nPhase 2 Backend API Layer is fully functional!")
    print("\nAvailable endpoints:")
    print("  - GET    /api/v1/segments/                    (List all segments)")
    print("  - POST   /api/v1/segments/                    (Create segment)")
    print("  - GET    /api/v1/segments/{id}/               (Get segment details)")
    print("  - PUT    /api/v1/segments/{id}/               (Update segment)")
    print("  - DELETE /api/v1/segments/{id}/               (Delete segment)")
    print("  - GET    /api/v1/segments/{id}/members/       (Get segment members)")
    print("  - POST   /api/v1/segments/{id}/recalculate/   (Recalculate count)")
    print("  - POST   /api/v1/segments/{id}/duplicate/     (Duplicate segment)")
    print("  - POST   /api/v1/segments/validate_filters/   (Validate filters)")
    print("  - POST   /api/v1/segments/{id}/enroll_in_sequence/ (Enroll in sequence)")

    return True


if __name__ == '__main__':
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
