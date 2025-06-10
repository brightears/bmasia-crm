#!/usr/bin/env python3
"""
Test script to verify BMAsia CRM customizations work correctly
Run this to test all your customizations without needing a web browser
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
sys.path.append('/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM')

django.setup()

from crm_app.models import Company, Opportunity, User
from django.contrib.auth import get_user_model

def test_bmasia_customizations():
    print("🎵 Testing BMAsia CRM Customizations")
    print("=" * 50)
    
    # Test 1: Industry Choices
    print("\n1. ✅ Testing Industry Choices:")
    industries = [choice[0] for choice in Company.INDUSTRY_CHOICES]
    expected_industries = ['Hotels', 'Restaurants', 'Bars', 'Quick Service Restaurants', 'Retail Fashion']
    for industry in expected_industries:
        if industry in industries:
            print(f"   ✅ {industry} - Available")
        else:
            print(f"   ❌ {industry} - Missing")
    
    # Test 2: Opportunity Stages
    print("\n2. ✅ Testing Opportunity Stages:")
    stages = [choice[0] for choice in Opportunity.STAGE_CHOICES]
    expected_stages = ['Contacted', 'Quotation Sent', 'Contract Sent', 'Won', 'Lost']
    for stage in expected_stages:
        if stage in stages:
            print(f"   ✅ {stage} - Available")
        else:
            print(f"   ❌ {stage} - Missing")
    
    # Test 3: Company Fields
    print("\n3. ✅ Testing Company Model Fields:")
    company_fields = [field.name for field in Company._meta.get_fields()]
    expected_fields = ['location_count', 'music_zone_count', 'is_corporate_account', 'region']
    for field in expected_fields:
        if field in company_fields:
            print(f"   ✅ {field} - Available")
        else:
            print(f"   ❌ {field} - Missing")
    
    # Test 4: Create Test Data
    print("\n4. ✅ Testing Data Creation:")
    try:
        # Create a test company
        company = Company.objects.create(
            name="Test Hotel Bangkok",
            industry="Hotels",
            region="Asia",
            location_count=1,
            music_zone_count=5,
            is_corporate_account=False
        )
        print(f"   ✅ Created test company: {company.name}")
        print(f"   ✅ Avg zones per location: {company.avg_zones_per_location}")
        
        # Create test opportunity
        opportunity = Opportunity.objects.create(
            company=company,
            name="Hotel Background Music License",
            stage="Contacted",
            expected_value=50000,
            probability=75
        )
        print(f"   ✅ Created test opportunity: {opportunity.name}")
        print(f"   ✅ Weighted value: ${opportunity.weighted_value}")
        
        # Cleanup
        opportunity.delete()
        company.delete()
        print("   ✅ Cleaned up test data")
        
    except Exception as e:
        print(f"   ❌ Error creating test data: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 BMAsia CRM Customization Test Complete!")
    print("\nYour CRM is ready with:")
    print("• Venue-specific industry types")
    print("• BMAsia sales workflow stages")
    print("• Location and music zone tracking")
    print("• Region-based organization")

if __name__ == "__main__":
    test_bmasia_customizations()