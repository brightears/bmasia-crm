"""Test Soundtrack API authentication"""
import base64
from django.core.management.base import BaseCommand
import requests
import json


class Command(BaseCommand):
    help = 'Test different authentication methods for Soundtrack API'
    
    def handle(self, *args, **options):
        # The token from environment
        token = "YVhId2UyTWJVWEhMRWlycUFPaUl3Y2NtOXNGeUoxR0Q6SVRHazZSWDVYV2FTenhiS1ZwNE1sSmhHUUJEVVRDdDZGU0FwVjZqMXNEQU1EMjRBT2pub2hmZ3NQODRRNndQWg=="
        
        # Try to decode it
        try:
            decoded = base64.b64decode(token).decode('utf-8')
            self.stdout.write(f"Decoded token: {decoded[:50]}...")  # Show first 50 chars
        except Exception as e:
            self.stdout.write(f"Could not decode token: {e}")
        
        # Test different auth methods
        url = "https://api.soundtrackyourbrand.com/v2"
        query = {"query": "{ me { businessName } }"}
        
        # Method 1: Token as-is with Basic
        self.stdout.write("\n1. Testing Basic auth with token as-is:")
        headers1 = {
            'Authorization': f'Basic {token}',
            'Content-Type': 'application/json',
        }
        try:
            response = requests.post(url, json=query, headers=headers1, timeout=10)
            self.stdout.write(f"   Status: {response.status_code}")
            self.stdout.write(f"   Response: {response.text[:200]}")
        except Exception as e:
            self.stdout.write(f"   Error: {e}")
        
        # Method 2: Bearer token
        self.stdout.write("\n2. Testing Bearer auth:")
        headers2 = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        try:
            response = requests.post(url, json=query, headers=headers2, timeout=10)
            self.stdout.write(f"   Status: {response.status_code}")
            self.stdout.write(f"   Response: {response.text[:200]}")
        except Exception as e:
            self.stdout.write(f"   Error: {e}")
        
        # Method 3: Just the token
        self.stdout.write("\n3. Testing with just token:")
        headers3 = {
            'Authorization': token,
            'Content-Type': 'application/json',
        }
        try:
            response = requests.post(url, json=query, headers=headers3, timeout=10)
            self.stdout.write(f"   Status: {response.status_code}")
            self.stdout.write(f"   Response: {response.text[:200]}")
        except Exception as e:
            self.stdout.write(f"   Error: {e}")