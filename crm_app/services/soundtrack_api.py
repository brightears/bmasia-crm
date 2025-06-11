"""Soundtrack Your Brand API integration service"""
import os
import requests
import base64
from typing import Dict, List, Optional
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class SoundtrackAPIService:
    """Service to interact with Soundtrack Your Brand API"""
    
    def __init__(self):
        # Load credentials from environment variables or settings
        self.api_token = os.environ.get('SOUNDTRACK_API_TOKEN', '')
        self.client_id = os.environ.get('SOUNDTRACK_CLIENT_ID', '')
        self.client_secret = os.environ.get('SOUNDTRACK_CLIENT_SECRET', '')
        self.base_url = 'https://api.soundtrackyourbrand.com/v2'
        
        if not all([self.api_token, self.client_id, self.client_secret]):
            logger.warning("Soundtrack API credentials not fully configured")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }
    
    def get_account_details(self, account_id: str) -> Optional[Dict]:
        """Get details for a specific account"""
        try:
            url = f"{self.base_url}/accounts/{account_id}"
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get account {account_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching account {account_id}: {str(e)}")
            return None
    
    def get_account_zones(self, account_id: str) -> List[Dict]:
        """Get all zones for an account"""
        try:
            url = f"{self.base_url}/accounts/{account_id}/zones"
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 200:
                return response.json().get('zones', [])
            else:
                logger.error(f"Failed to get zones for account {account_id}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching zones for account {account_id}: {str(e)}")
            return []
    
    def get_zone_status(self, account_id: str, zone_id: str) -> Optional[Dict]:
        """Get detailed status for a specific zone"""
        try:
            url = f"{self.base_url}/accounts/{account_id}/zones/{zone_id}/status"
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get zone status {zone_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching zone status {zone_id}: {str(e)}")
            return None
    
    def parse_zone_status(self, zone_data: Dict) -> Dict:
        """Parse zone data from API into our status format"""
        status = 'offline'  # default
        
        # Parse based on actual API response structure
        # This is a template - adjust based on real API response
        if zone_data.get('online', False):
            status = 'online'
        elif not zone_data.get('device_paired', True):
            status = 'no_device'
        elif not zone_data.get('subscription_active', True):
            status = 'expired'
        
        return {
            'status': status,
            'device_name': zone_data.get('device_name', ''),
            'last_seen': zone_data.get('last_seen'),
            'admin_email': zone_data.get('admin_email', ''),
            'is_online': zone_data.get('online', False),
            'raw_data': zone_data
        }
    
    def sync_company_zones(self, company):
        """Sync all zones for a company with Soundtrack"""
        if not company.soundtrack_account_id:
            return 0, 0
        
        # Get all zones from the API
        api_zones = self.get_account_zones(company.soundtrack_account_id)
        
        # Create or update zones based on API data
        synced_count = 0
        for api_zone in api_zones:
            zone_name = api_zone.get('name', 'Unknown Zone')
            zone_id = api_zone.get('id', '')
            
            # Get or create zone
            zone, created = company.zones.get_or_create(
                name=zone_name,
                platform='soundtrack',
                defaults={
                    'soundtrack_zone_id': zone_id,
                    'status': 'pending'
                }
            )
            
            # Update zone status
            parsed_data = self.parse_zone_status(api_zone)
            zone.update_from_api(parsed_data)
            synced_count += 1
        
        logger.info(f"Synced {synced_count} zones for {company.name}")
        return synced_count, 0
    
    def sync_all_zones(self):
        """Sync all zones for companies with Soundtrack account IDs"""
        from crm_app.models import Company
        
        companies = Company.objects.filter(
            soundtrack_account_id__isnull=False
        ).exclude(soundtrack_account_id='')
        
        total_synced = 0
        total_errors = 0
        
        for company in companies:
            synced, errors = self.sync_company_zones(company)
            total_synced += synced
            total_errors += errors
        
        logger.info(f"Total sync complete: {total_synced} synced, {total_errors} errors")
        return total_synced, total_errors


# Singleton instance
soundtrack_api = SoundtrackAPIService()