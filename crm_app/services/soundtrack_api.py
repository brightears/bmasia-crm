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
                ... on PublicAPIClient {
                    accounts(first: 10) {
                        edges {
                            node {
                                id
                                businessName
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
                                                        isPaired
                                                        device {
                                                            id
                                                            name
                                                        }
                                                        schedule {
                                                            id
                                                            name
                                                        }
                                                        playFrom {
                                                            __typename
                                                            ... on Playlist {
                                                                id
                                                                name
                                                            }
                                                            ... on Schedule {
                                                                id
                                                                name
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
            }
        }
        """
        
        return self._make_graphql_query(query)
    
    def get_account_zones(self, account_id: str = None) -> List[Dict]:
        """Get zones for a specific account or all accounts if no account_id provided"""
        if account_id:
            # Use specific account query when account ID is provided
            return self._get_specific_account_zones(account_id)
        else:
            # Fall back to getting all accounts
            return self._get_all_account_zones()
    
    def _get_specific_account_zones(self, account_id: str) -> List[Dict]:
        """Get zones for a specific account ID using direct account query"""
        query = """
        query($accountId: ID!) {
            account(id: $accountId) {
                id
                businessName
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
                                        isPaired
                                        device {
                                            id
                                            name
                                        }
                                        schedule {
                                            id
                                            name
                                        }
                                        playFrom {
                                            __typename
                                            ... on Playlist {
                                                id
                                                name
                                            }
                                            ... on Schedule {
                                                id
                                                name
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
        
        variables = {"accountId": account_id}
        result = self._make_graphql_query(query, variables)
        
        if not result or 'account' not in result:
            logger.error(f"Failed to get account info for ID: {account_id}")
            return []
        
        zones = []
        account = result['account']
        business_name = account.get('businessName', 'Unknown Business')
        
        # Iterate through all locations in this account
        for location_edge in account.get('locations', {}).get('edges', []):
            location = location_edge['node']
            location_name = location.get('name', 'Unknown Location')
            
            # Iterate through all sound zones in this location
            for zone_edge in location.get('soundZones', {}).get('edges', []):
                zone = zone_edge['node']
                
                # Determine zone status based on isPaired and device presence
                if zone.get('isPaired', False) and zone.get('device'):
                    status = 'online'
                    is_online = True
                elif zone.get('device'):
                    status = 'offline'  # Has device but not paired
                    is_online = False
                else:
                    status = 'no_device'
                    is_online = False
                
                # Get schedule and playFrom information
                schedule_name = zone.get('schedule', {}).get('name', '') if zone.get('schedule') else ''
                play_from = zone.get('playFrom', {})
                play_from_type = play_from.get('__typename', '') if play_from else ''
                play_from_name = play_from.get('name', '') if play_from else ''
                
                zones.append({
                    'id': zone['id'],
                    'name': f"{location_name} - {zone['name']}",
                    'zone_name': zone['name'],
                    'location_name': location_name,
                    'account_name': business_name,
                    'account_id': account_id,
                    'is_online': is_online,
                    'is_paired': zone.get('isPaired', False),
                    'device_name': zone.get('device', {}).get('name', '') if zone.get('device') else '',
                    'device_id': zone.get('device', {}).get('id', '') if zone.get('device') else '',
                    'status': status,
                    'schedule_name': schedule_name,
                    'play_from_type': play_from_type,
                    'play_from_name': play_from_name,
                    'currently_playing': f"{play_from_type}: {play_from_name}" if play_from_name else 'No active playlist/schedule',
                })
        
        return zones
    
    def _get_all_account_zones(self) -> List[Dict]:
        """Get zones for all accounts using me query"""
        account_info = self.get_account_info()
        
        if not account_info or 'me' not in account_info:
            logger.error("Failed to get account info")
            return []
        
        zones = []
        me = account_info['me']
        
        # Iterate through all accounts
        for account_edge in me.get('accounts', {}).get('edges', []):
            account = account_edge['node']
            current_account_id = account['id']
            business_name = account.get('businessName', 'Unknown Business')
            
            # Iterate through all locations in this account
            for location_edge in account.get('locations', {}).get('edges', []):
                location = location_edge['node']
                location_name = location.get('name', 'Unknown Location')
                
                # Iterate through all sound zones in this location
                for zone_edge in location.get('soundZones', {}).get('edges', []):
                    zone = zone_edge['node']
                    
                    # Determine zone status based on isPaired and device presence
                    if zone.get('isPaired', False) and zone.get('device'):
                        status = 'online'
                        is_online = True
                    elif zone.get('device'):
                        status = 'offline'  # Has device but not paired
                        is_online = False
                    else:
                        status = 'no_device'
                        is_online = False
                    
                    # Get schedule and playFrom information
                    schedule_name = zone.get('schedule', {}).get('name', '') if zone.get('schedule') else ''
                    play_from = zone.get('playFrom', {})
                    play_from_type = play_from.get('__typename', '') if play_from else ''
                    play_from_name = play_from.get('name', '') if play_from else ''
                    
                    zones.append({
                        'id': zone['id'],
                        'name': f"{location_name} - {zone['name']}",
                        'zone_name': zone['name'],
                        'location_name': location_name,
                        'account_name': business_name,
                        'account_id': current_account_id,
                        'is_online': is_online,
                        'is_paired': zone.get('isPaired', False),
                        'device_name': zone.get('device', {}).get('name', '') if zone.get('device') else '',
                        'device_id': zone.get('device', {}).get('id', '') if zone.get('device') else '',
                        'status': status,
                        'schedule_name': schedule_name,
                        'play_from_type': play_from_type,
                        'play_from_name': play_from_name,
                        'currently_playing': f"{play_from_type}: {play_from_name}" if play_from_name else 'No active playlist/schedule',
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

    def preview_zones(self, account_id: str) -> List[Dict]:
        """
        Preview zones from Soundtrack API without saving to database.
        Used to preview what zones would be synced before committing.

        Args:
            account_id: Soundtrack account ID

        Returns:
            List of zone dictionaries from the API
        """
        return self.get_account_zones(account_id)
    
    def sync_company_zones(self, company):
        """Sync all zones for a company with Soundtrack

        Deduplication logic:
        1. PRIMARY: Match by soundtrack_zone_id (unique API identifier)
        2. FALLBACK: Match by name + platform (for manually created zones)
        3. CREATE: Only if no match found
        4. ORPHAN DETECTION: Mark zones not in API as orphaned
        """
        from crm_app.models import Zone

        if not company.soundtrack_account_id:
            return 0, 0

        # Get all zones from the API
        api_zones = self.get_account_zones(company.soundtrack_account_id)

        if not api_zones:
            logger.warning(f"No zones found for company {company.name}")
            return 0, 0

        # Track API zone IDs for orphan detection
        api_zone_ids = set()

        # Create or update zones based on API data
        synced_count = 0
        for api_zone in api_zones:
            zone_name = api_zone.get('name', 'Unknown Zone')
            zone_id = api_zone.get('id', '')

            if zone_id:
                api_zone_ids.add(zone_id)

            # PRIMARY: Match by soundtrack_zone_id (most reliable)
            zone = company.zones.filter(soundtrack_zone_id=zone_id).first() if zone_id else None

            if not zone:
                # FALLBACK: Match by name + platform (catches manually created zones)
                zone = company.zones.filter(
                    name=zone_name,
                    platform='soundtrack'
                ).first()

            if not zone:
                # CREATE: Only if no match found
                zone = Zone.objects.create(
                    company=company,
                    name=zone_name,
                    platform='soundtrack',
                    soundtrack_zone_id=zone_id,
                    status='pending'
                )
                logger.info(f"Created new zone: {zone_name} for {company.name}")

            # Update zone with latest data from API
            zone.soundtrack_zone_id = zone_id  # Ensure ID is set (links manual zones)
            zone.name = zone_name  # Update name in case it changed in Soundtrack
            zone.status = api_zone.get('status', 'offline')
            zone.device_name = api_zone.get('device_name', '')
            if api_zone.get('is_online'):
                zone.last_seen_online = timezone.now()
            zone.api_raw_data = api_zone
            zone.last_api_sync = timezone.now()

            # Unmark as orphaned if it was previously orphaned
            if zone.is_orphaned:
                zone.is_orphaned = False
                zone.orphaned_at = None
                logger.info(f"Zone {zone_name} found in API again - unmarking as orphaned")

            zone.save()

            synced_count += 1

        # Detect orphaned zones (zones in DB but not in API)
        db_zones = company.zones.filter(platform='soundtrack').exclude(soundtrack_zone_id='')
        for db_zone in db_zones:
            if db_zone.soundtrack_zone_id and db_zone.soundtrack_zone_id not in api_zone_ids:
                if not db_zone.is_orphaned:
                    db_zone.is_orphaned = True
                    db_zone.orphaned_at = timezone.now()
                    db_zone.save(update_fields=['is_orphaned', 'orphaned_at'])
                    logger.warning(f"Zone {db_zone.name} not found in API - marked as orphaned")

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