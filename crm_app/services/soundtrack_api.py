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
        
        if not all([self.api_token]):
            logger.warning("Soundtrack API token not configured")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        # The API uses Basic authentication with the token
        return {
            'Authorization': f'Basic {self.api_token}',
            'Content-Type': 'application/json',
        }
    
    def _make_graphql_query(self, query: str, variables: Optional[Dict] = None) -> Optional[Dict]:
        """Execute a GraphQL query against the Soundtrack API"""
        try:
            payload = {
                'query': query,
                'variables': variables or {}
            }
            
            response = requests.post(
                self.base_url,
                json=payload,
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    logger.error(f"GraphQL errors: {data['errors']}")
                    return None
                return data.get('data')
            else:
                logger.error(f"API request failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error making GraphQL query: {str(e)}")
            return None
    
    def get_account_info(self) -> Optional[Dict]:
        """Get current account information"""
        query = """
        query {
            me {
                businessName
                accounts(first: 100) {
                    edges {
                        node {
                            id
                            name
                            locations(first: 100) {
                                edges {
                                    node {
                                        id
                                        name
                                        soundZones(first: 100) {
                                            edges {
                                                node {
                                                    id
                                                    name
                                                    currentlyPlaying {
                                                        track {
                                                            name
                                                        }
                                                    }
                                                    isOnline
                                                    isPaired
                                                    subscription {
                                                        validUntil
                                                        isExpired
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        return self._make_graphql_query(query)
    
    def get_account_zones(self, account_id: str = None) -> List[Dict]:
        """Get all zones across all accounts and locations"""
        # For now, we'll get all zones since we don't have the GraphQL ID structure
        account_info = self.get_account_info()
        
        if not account_info or 'me' not in account_info:
            logger.error("Failed to get account info")
            return []
        
        zones = []
        me = account_info['me']
        
        # Iterate through accounts
        for account_edge in me.get('accounts', {}).get('edges', []):
            account = account_edge['node']
            account_name = account['name']
            
            # Iterate through locations
            for location_edge in account.get('locations', {}).get('edges', []):
                location = location_edge['node']
                location_name = location['name']
                
                # Iterate through sound zones
                for zone_edge in location.get('soundZones', {}).get('edges', []):
                    zone = zone_edge['node']
                    
                    # Determine zone status
                    status = 'offline'
                    if zone.get('isOnline'):
                        status = 'online'
                    elif not zone.get('isPaired'):
                        status = 'no_device'
                    elif zone.get('subscription', {}).get('isExpired', False):
                        status = 'expired'
                    
                    zones.append({
                        'id': zone['id'],
                        'name': f"{location_name} - {zone['name']}",
                        'zone_name': zone['name'],
                        'location_name': location_name,
                        'account_name': account_name,
                        'is_online': zone.get('isOnline', False),
                        'is_paired': zone.get('isPaired', False),
                        'status': status,
                        'currently_playing': zone.get('currentlyPlaying', {}).get('track', {}).get('name') if zone.get('currentlyPlaying') else None,
                        'subscription_valid_until': zone.get('subscription', {}).get('validUntil'),
                        'subscription_expired': zone.get('subscription', {}).get('isExpired', False),
                    })
        
        return zones
    
    def parse_zone_status(self, zone_data: Dict) -> Dict:
        """Parse zone data from API into our status format"""
        return {
            'status': zone_data.get('status', 'offline'),
            'device_name': zone_data.get('zone_name', ''),
            'last_seen': timezone.now() if zone_data.get('is_online') else None,
            'is_online': zone_data.get('is_online', False),
            'raw_data': zone_data
        }
    
    def sync_company_zones(self, company):
        """Sync all zones for a company with Soundtrack"""
        if not company.soundtrack_account_id:
            return 0, 0
        
        # Get all zones from the API
        api_zones = self.get_account_zones(company.soundtrack_account_id)
        
        if not api_zones:
            logger.warning(f"No zones found for company {company.name}")
            return 0, 0
        
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
            
            # Update zone with latest data
            zone.soundtrack_zone_id = zone_id
            zone.status = api_zone.get('status', 'offline')
            zone.device_name = api_zone.get('zone_name', '')
            if api_zone.get('is_online'):
                zone.last_seen_online = timezone.now()
            zone.api_raw_data = api_zone
            zone.last_api_sync = timezone.now()
            zone.save()
            
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