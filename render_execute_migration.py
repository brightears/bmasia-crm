#!/usr/bin/env python3
"""
Use Render API to execute the migration on the production server
"""

import requests
import json
import time
import sys

RENDER_API_KEY = "rnd_QAJKR0jggzsxSLOCx3HfovreCzOd"
API_BASE = "https://api.render.com/v1"

def get_services():
    """Get list of services"""
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Accept": "application/json"
    }
    
    response = requests.get(f"{API_BASE}/services", headers=headers)
    response.raise_for_status()
    return response.json()

def run_shell_command(service_id, command):
    """Run a shell command on the service"""
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    data = {
        "command": command
    }
    
    response = requests.post(
        f"{API_BASE}/services/{service_id}/shell",
        headers=headers,
        json=data
    )
    response.raise_for_status()
    return response.json()

def main():
    print("\n" + "=" * 80)
    print("Render API: Execute Production Migration")
    print("=" * 80 + "\n")

    try:
        # Get services
        print("Step 1: Fetching Render services...")
        services_data = get_services()
        
        # Find the web service (not the database)
        web_service = None
        for service in services_data:
            if service.get('type') == 'web_service':
                print(f"  Found web service: {service.get('name')} (ID: {service.get('id')})")
                web_service = service
                break
        
        if not web_service:
            print("  ✗ No web service found")
            print("\nAvailable services:")
            for service in services_data:
                print(f"  - {service.get('name')} ({service.get('type')})")
            sys.exit(1)
        
        service_id = web_service.get('id')
        print(f"\n  ✓ Using service: {web_service.get('name')}\n")
        
        # Run migration command
        print("Step 2: Executing migration via Render shell...")
        print("  Command: python manage.py migrate crm_app 0024\n")
        
        result = run_shell_command(service_id, "python manage.py migrate crm_app 0024")
        
        print("  ✓ Command executed")
        print(f"\n  Response: {json.dumps(result, indent=2)}\n")
        
        print("=" * 80)
        print("SUCCESS: Migration command sent to Render")
        print("=" * 80)
        print("\nCheck the Render dashboard logs to verify the migration completed.")
        print("URL: https://dashboard.render.com\n")
        
    except requests.exceptions.HTTPError as e:
        print(f"\n✗ API Error: {e}")
        print(f"  Response: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
