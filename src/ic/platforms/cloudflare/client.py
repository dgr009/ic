#!/usr/bin/env python3
"""
CloudFlare API Client

Centralized CloudFlare API client with authentication, error handling, and rate limiting.
Provides reusable methods for common API operations with comprehensive logging.
"""

import time
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

try:
    from ic.config.manager import ConfigManager
except ImportError:
    try:
        from ic.config.manager import ConfigManager
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        from ic.config.manager import ConfigManager

try:
    from src.common.log import log_info_non_console as log_info, log_error, log_exception
except ImportError:
    from common.log import log_info_non_console as log_info, log_error, log_exception


# Custom Exception Classes
class CloudFlareAPIError(Exception):
    """Base exception for CloudFlare API errors."""
    pass


class AuthenticationError(CloudFlareAPIError):
    """Raised when authentication fails."""
    pass


class RateLimitError(CloudFlareAPIError):
    """Raised when API rate limit is exceeded."""
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class NetworkError(CloudFlareAPIError):
    """Raised when network connectivity issues occur."""
    pass


@dataclass
class CloudFlareConfig:
    """CloudFlare configuration data model."""
    email: str
    api_token: str
    accounts: List[str]  # Filter list, empty = all
    zones: List[str]     # Filter list, empty = all
    
    @classmethod
    def from_config_manager(cls, config_manager: ConfigManager) -> 'CloudFlareConfig':
        """
        Load configuration from Config Manager.
        
        Args:
            config_manager: ConfigManager instance
            
        Returns:
            CloudFlareConfig instance
        """
        config = config_manager.load_all_configs()
        cf_config = config.get('cloudflare', {})
        
        # Parse account filters
        accounts_config = cf_config.get('cloudflare_accounts', [])
        if isinstance(accounts_config, str):
            accounts = [a.strip() for a in accounts_config.split(',') if a.strip()]
        elif isinstance(accounts_config, list):
            accounts = [a.strip() for a in accounts_config if a and a.strip()]
        else:
            accounts = []
        
        # Parse zone filters
        zones_config = cf_config.get('cloudflare_zones', [])
        if isinstance(zones_config, str):
            zones = [z.strip() for z in zones_config.split(',') if z.strip()]
        elif isinstance(zones_config, list):
            zones = [z.strip() for z in zones_config if z and z.strip()]
        else:
            zones = []
        
        return cls(
            email=cf_config.get('email', ''),
            api_token=cf_config.get('api_token', ''),
            accounts=accounts,
            zones=zones
        )


class CloudFlareClient:
    """
    Centralized CloudFlare API client.
    
    Provides methods for common CloudFlare API operations with:
    - Authentication management
    - Error handling and retries
    - Rate limiting
    - Pagination support
    - Comprehensive logging
    """
    
    API_ENDPOINT = "https://api.cloudflare.com/client/v4"
    DEFAULT_TIMEOUT = 30
    DEFAULT_PER_PAGE = 50
    
    def __init__(self, config: CloudFlareConfig):
        """
        Initialize CloudFlare client.
        
        Args:
            config: CloudFlareConfig instance with credentials and filters
        """
        self.config = config
        self.headers = {
            "X-Auth-Email": config.email,
            "Authorization": f"Bearer {config.api_token}",
            "Content-Type": "application/json",
        }
        
        # Validate credentials
        if not config.email or not config.api_token:
            raise AuthenticationError(
                "CloudFlare credentials not configured. "
                "Please configure email and api_token in ~/.ic/config/secrets.yaml"
            )
        
        log_info("CloudFlare client initialized")
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        timeout: int = DEFAULT_TIMEOUT,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an API request with error handling and logging.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (without base URL)
            timeout: Request timeout in seconds
            **kwargs: Additional arguments for requests
            
        Returns:
            API response data
            
        Raises:
            AuthenticationError: If authentication fails
            RateLimitError: If rate limit is exceeded
            NetworkError: If network connectivity issues occur
            CloudFlareAPIError: For other API errors
        """
        url = f"{self.API_ENDPOINT}{endpoint}"
        
        # Log request details (without credentials)
        # Include parameters if present (but not auth headers)
        params_str = ""
        if 'params' in kwargs:
            params_str = f" with params: {kwargs['params']}"
        log_info(f"CloudFlare API request: {method} {endpoint}{params_str}")
        
        start_time = time.time()
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                timeout=timeout,
                **kwargs
            )
            
            elapsed_time = time.time() - start_time
            log_info(f"CloudFlare API response: {method} {endpoint} completed in {elapsed_time:.2f}s (status: {response.status_code})")
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                log_error(f"CloudFlare API rate limit exceeded. Retry after {retry_after}s")
                raise RateLimitError(
                    f"API rate limit exceeded. Please wait {retry_after} seconds.",
                    retry_after=retry_after
                )
            
            # Handle authentication errors
            if response.status_code in (401, 403):
                log_error(f"CloudFlare authentication failed: {response.status_code}")
                raise AuthenticationError(
                    "CloudFlare authentication failed. Please check your credentials "
                    "in ~/.ic/config/secrets.yaml"
                )
            
            # Handle other errors
            if not response.ok:
                error_data = response.json() if response.content else {}
                error_messages = error_data.get('errors', [])
                error_text = ', '.join([e.get('message', '') for e in error_messages]) if error_messages else response.text
                log_error(f"CloudFlare API error {response.status_code}: {error_text}")
                raise CloudFlareAPIError(
                    f"CloudFlare API error ({response.status_code}): {error_text}"
                )
            
            # Parse and return response
            response_data = response.json()
            
            # Check for API-level errors
            if not response_data.get('success', True):
                error_messages = response_data.get('errors', [])
                error_text = ', '.join([e.get('message', '') for e in error_messages])
                log_error(f"CloudFlare API returned errors: {error_text}")
                raise CloudFlareAPIError(f"CloudFlare API error: {error_text}")
            
            return response_data
            
        except requests.exceptions.Timeout:
            log_error(f"CloudFlare API request timeout after {timeout}s")
            raise NetworkError(
                f"Request timeout after {timeout} seconds. "
                "Please check your internet connection."
            )
        except requests.exceptions.ConnectionError as e:
            log_error(f"CloudFlare API connection error: {e}")
            raise NetworkError(
                "Failed to connect to CloudFlare API. "
                "Please check your internet connection."
            )
        except requests.exceptions.RequestException as e:
            log_exception(e)
            raise NetworkError(f"Network error: {str(e)}")
    
    def get_accounts(self, name_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Retrieve CloudFlare accounts with optional filtering.
        
        Args:
            name_filter: Optional list of account name filters (case-insensitive substring match)
            
        Returns:
            List of account dictionaries
        """
        log_info("Fetching CloudFlare accounts from API")
        
        # Use pagination to get all accounts
        accounts = []
        page = 1
        
        while True:
            endpoint = f"/accounts?page={page}&per_page={self.DEFAULT_PER_PAGE}"
            response = self._make_request("GET", endpoint)
            
            result = response.get("result", [])
            accounts.extend(result)
            
            # Check if more pages exist
            result_info = response.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            
            log_info(f"Fetched page {page}/{total_pages} of accounts ({len(result)} accounts on this page)")
            
            if page >= total_pages:
                break
            
            page += 1
        
        log_info(f"Retrieved total of {len(accounts)} CloudFlare accounts from API")
        
        # Apply name filter if provided
        if name_filter:
            log_info(f"Applying account filter: {name_filter}")
            filtered_accounts = []
            for account in accounts:
                account_name = account.get("name", "").lower()
                if any(filter_term.lower() in account_name for filter_term in name_filter):
                    filtered_accounts.append(account)
            
            log_info(f"Filter applied: {len(filtered_accounts)} of {len(accounts)} accounts matched filter criteria")
            return filtered_accounts
        
        log_info("No filter applied, returning all accounts")
        return accounts
    
    def get_zones(
        self,
        account_id: str,
        name_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve zones for an account with optional filtering.
        
        Args:
            account_id: CloudFlare account ID
            name_filter: Optional list of zone name filters (case-insensitive substring match)
            
        Returns:
            List of zone dictionaries
        """
        log_info(f"Fetching zones for account {account_id} from API")
        
        # Use pagination to get all zones
        zones = []
        page = 1
        
        while True:
            endpoint = f"/zones?account.id={account_id}&page={page}&per_page={self.DEFAULT_PER_PAGE}"
            response = self._make_request("GET", endpoint)
            
            result = response.get("result", [])
            zones.extend(result)
            
            # Check if more pages exist
            result_info = response.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            
            log_info(f"Fetched page {page}/{total_pages} of zones for account {account_id} ({len(result)} zones on this page)")
            
            if page >= total_pages:
                break
            
            page += 1
        
        log_info(f"Retrieved total of {len(zones)} zones for account {account_id} from API")
        
        # Apply name filter if provided
        if name_filter:
            log_info(f"Applying zone filter: {name_filter}")
            filtered_zones = []
            for zone in zones:
                zone_name = zone.get("name", "").lower()
                if any(filter_term.lower() in zone_name for filter_term in name_filter):
                    filtered_zones.append(zone)
            
            log_info(f"Filter applied: {len(filtered_zones)} of {len(zones)} zones matched filter criteria")
            return filtered_zones
        
        log_info("No filter applied, returning all zones")
        return zones
    
    def get_dns_records(self, zone_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve DNS records for a zone.
        
        Args:
            zone_id: CloudFlare zone ID
            
        Returns:
            List of DNS record dictionaries
        """
        log_info(f"Fetching DNS records for zone {zone_id} from API")
        
        # Use pagination to get all DNS records
        records = []
        page = 1
        
        while True:
            endpoint = f"/zones/{zone_id}/dns_records?page={page}&per_page={self.DEFAULT_PER_PAGE}"
            response = self._make_request("GET", endpoint)
            
            result = response.get("result", [])
            records.extend(result)
            
            # Check if more pages exist
            result_info = response.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            
            log_info(f"Fetched page {page}/{total_pages} of DNS records for zone {zone_id} ({len(result)} records on this page)")
            
            if page >= total_pages:
                break
            
            page += 1
        
        log_info(f"Retrieved total of {len(records)} DNS records for zone {zone_id} from API")
        return records
    
    def get_firewall_rules(self, zone_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve WAF/firewall rules for a zone.
        
        Args:
            zone_id: CloudFlare zone ID
            
        Returns:
            List of firewall rule dictionaries
        """
        log_info(f"Fetching firewall rules for zone {zone_id} from API")
        
        # Use pagination to get all firewall rules
        rules = []
        page = 1
        
        while True:
            endpoint = f"/zones/{zone_id}/firewall/rules?page={page}&per_page={self.DEFAULT_PER_PAGE}"
            response = self._make_request("GET", endpoint)
            
            result = response.get("result", [])
            rules.extend(result)
            
            # Check if more pages exist
            result_info = response.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            
            log_info(f"Fetched page {page}/{total_pages} of firewall rules for zone {zone_id} ({len(result)} rules on this page)")
            
            if page >= total_pages:
                break
            
            page += 1
        
        log_info(f"Retrieved total of {len(rules)} firewall rules for zone {zone_id} from API")
        return rules
    
    def get_page_rules(self, zone_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve page rules for a zone.
        
        Args:
            zone_id: CloudFlare zone ID
            
        Returns:
            List of page rule dictionaries
        """
        log_info(f"Fetching page rules for zone {zone_id} from API")
        
        # Use pagination to get all page rules
        rules = []
        page = 1
        
        while True:
            endpoint = f"/zones/{zone_id}/pagerules?page={page}&per_page={self.DEFAULT_PER_PAGE}"
            response = self._make_request("GET", endpoint)
            
            result = response.get("result", [])
            rules.extend(result)
            
            # Check if more pages exist
            result_info = response.get("result_info", {})
            total_pages = result_info.get("total_pages", 1)
            
            log_info(f"Fetched page {page}/{total_pages} of page rules for zone {zone_id} ({len(result)} rules on this page)")
            
            if page >= total_pages:
                break
            
            page += 1
        
        log_info(f"Retrieved total of {len(rules)} page rules for zone {zone_id} from API")
        return rules
    
    def get_analytics(
        self,
        zone_id: str,
        since: datetime,
        until: datetime
    ) -> Dict[str, Any]:
        """
        Retrieve analytics data for a zone.
        
        Automatically detects zone license type and uses the appropriate API:
        - Enterprise zones: GraphQL Analytics API (full metrics)
        - Free zones: REST Analytics API (limited metrics)
        
        Args:
            zone_id: CloudFlare zone ID
            since: Start datetime for analytics period
            until: End datetime for analytics period
            
        Returns:
            Unified analytics dictionary with all available metrics.
            Missing metrics are set to None for unavailable data.
            
        Example return structure:
            {
                "zone_id": "abc123...",
                "license_type": "Enterprise" or "Free",
                "requests": 1234567,
                "bandwidth": 123456789,  # bytes
                "unique_visitors": 45678 or None,
                "cache_hit_ratio": 0.873 or None,
                "threats_blocked": 1234 or None,
                "peak_requests_per_hour": 45678 or None
            }
        """
        log_info(f"Fetching analytics for zone {zone_id} from API (period: {since.isoformat()} to {until.isoformat()})")
        
        # First, get zone details to determine license type
        zone_endpoint = f"/zones/{zone_id}"
        zone_response = self._make_request("GET", zone_endpoint)
        zone_data = zone_response.get("result", {})
        
        # Determine license type from plan
        plan = zone_data.get("plan", {})
        plan_name = plan.get("name", "").lower()
        
        # Enterprise plans include "enterprise" in the name
        is_enterprise = "enterprise" in plan_name
        license_type = "Enterprise" if is_enterprise else "Free"
        
        log_info(f"Zone {zone_id} license type detected: {license_type} (plan: {plan_name})")
        
        # Format datetime for API
        since_str = since.isoformat() + "Z"
        until_str = until.isoformat() + "Z"
        
        if is_enterprise:
            # Use GraphQL Analytics API for Enterprise zones
            return self._get_analytics_graphql(zone_id, since_str, until_str, license_type)
        else:
            # Use REST Analytics API for Free zones
            return self._get_analytics_rest(zone_id, since_str, until_str, license_type)
    
    def _get_analytics_graphql(
        self,
        zone_id: str,
        since: str,
        until: str,
        license_type: str
    ) -> Dict[str, Any]:
        """
        Retrieve analytics using GraphQL API (Enterprise zones).
        
        Args:
            zone_id: CloudFlare zone ID
            since: ISO format datetime string
            until: ISO format datetime string
            license_type: License type string
            
        Returns:
            Analytics dictionary with full metrics
        """
        log_info(f"Using GraphQL Analytics API for zone {zone_id}")
        
        # GraphQL query for comprehensive analytics
        # Note: CloudFlare GraphQL uses date_geq/date_leq, not datetime_geq/datetime_leq
        # Format dates as YYYY-MM-DD
        since_date = since.split('T')[0] if 'T' in since else since[:10]
        until_date = until.split('T')[0] if 'T' in until else until[:10]
        
        graphql_query = """
        query {
          viewer {
            zones(filter: {zoneTag: "%s"}) {
              httpRequests1dGroups(
                limit: 1000,
                filter: {
                  date_geq: "%s",
                  date_leq: "%s"
                }
              ) {
                sum {
                  requests
                  bytes
                  threats
                  cachedRequests
                  pageViews
                }
                uniq {
                  uniques
                }
              }
            }
          }
        }
        """ % (zone_id, since_date, until_date)
        
        try:
            # Make GraphQL request
            graphql_endpoint = "https://api.cloudflare.com/client/v4/graphql"
            response = requests.post(
                graphql_endpoint,
                headers=self.headers,
                json={"query": graphql_query},
                timeout=self.DEFAULT_TIMEOUT
            )
            
            if not response.ok:
                log_error(f"GraphQL API error: {response.status_code}")
                # Fall back to basic metrics
                return self._get_analytics_rest(zone_id, since, until, license_type)
            
            data = response.json()
            
            # Check if response is valid
            if data is None:
                log_error("GraphQL API returned None response")
                return self._create_empty_analytics(zone_id, license_type)
            
            # Check for GraphQL errors
            if "errors" in data and data['errors']:
                errors = data['errors']
                error_messages = [e.get('message', str(e)) for e in errors]
                log_error(f"GraphQL errors: {', '.join(error_messages)}")
                return self._create_empty_analytics(zone_id, license_type)
            
            # Parse GraphQL response
            data_obj = data.get("data")
            if data_obj is None:
                log_error(f"GraphQL response missing 'data' field. Response: {data}")
                return self._create_empty_analytics(zone_id, license_type)
            
            viewer = data_obj.get("viewer")
            if viewer is None:
                log_error(f"GraphQL response missing 'viewer' field")
                return self._create_empty_analytics(zone_id, license_type)
            
            zones = viewer.get("zones", [])
            if not zones:
                log_error("No zone data in GraphQL response")
                return self._create_empty_analytics(zone_id, license_type)
            
            groups = zones[0].get("httpRequests1dGroups", [])
            if not groups:
                log_info("No analytics data available for time period")
                return self._create_empty_analytics(zone_id, license_type)
            
            # Aggregate metrics across all time groups
            total_requests = 0
            total_bytes = 0
            total_threats = 0
            total_cached = 0
            total_page_views = 0
            unique_visitors = 0
            
            for group in groups:
                sum_data = group.get("sum", {})
                uniq_data = group.get("uniq", {})
                
                total_requests += sum_data.get("requests", 0)
                total_bytes += sum_data.get("bytes", 0)
                total_threats += sum_data.get("threats", 0)
                total_cached += sum_data.get("cachedRequests", 0)
                total_page_views += sum_data.get("pageViews", 0)
                unique_visitors = max(unique_visitors, uniq_data.get("uniques", 0))
            
            # Calculate cache hit ratio
            cache_hit_ratio = None
            if total_requests > 0:
                cache_hit_ratio = total_cached / total_requests
            
            # Calculate peak requests per hour (approximate)
            time_diff_hours = (datetime.fromisoformat(until.rstrip('Z')) - 
                             datetime.fromisoformat(since.rstrip('Z'))).total_seconds() / 3600
            peak_requests_per_hour = None
            if time_diff_hours > 0:
                peak_requests_per_hour = int(total_requests / time_diff_hours)
            
            log_info(
                f"Retrieved GraphQL analytics for zone {zone_id}: "
                f"{total_requests} requests, {total_bytes} bytes, "
                f"{unique_visitors} unique visitors, {total_threats} threats blocked"
            )
            
            return {
                "zone_id": zone_id,
                "license_type": license_type,
                "requests": total_requests,
                "bandwidth": total_bytes,
                "unique_visitors": unique_visitors if unique_visitors > 0 else None,
                "cache_hit_ratio": cache_hit_ratio,
                "threats_blocked": total_threats if total_threats > 0 else None,
                "peak_requests_per_hour": peak_requests_per_hour
            }
            
        except Exception as e:
            log_exception(e)
            log_error(f"GraphQL analytics failed, falling back to REST API: {e}")
            # Fall back to REST API
            return self._get_analytics_rest(zone_id, since, until, license_type)
    
    def _get_analytics_rest(
        self,
        zone_id: str,
        since: str,
        until: str,
        license_type: str
    ) -> Dict[str, Any]:
        """
        Retrieve analytics using REST API (Free zones or fallback).
        
        Args:
            zone_id: CloudFlare zone ID
            since: ISO format datetime string
            until: ISO format datetime string
            license_type: License type string
            
        Returns:
            Analytics dictionary with limited metrics
        """
        log_info(f"Using REST Analytics API for zone {zone_id}")
        
        try:
            # Note: REST Analytics API has been sunset by CloudFlare
            # This fallback will likely fail with 404
            log_info(f"Attempting REST Analytics API (may be unavailable)")
            
            endpoint = f"/zones/{zone_id}/analytics/dashboard"
            params = {
                "since": since,
                "until": until,
                "continuous": "true"
            }
            
            response = self._make_request("GET", endpoint, params=params)
            result = response.get("result", {})
            
            # Extract totals
            totals = result.get("totals", {})
            
            requests = totals.get("requests", {}).get("all", 0)
            bandwidth = totals.get("bandwidth", {}).get("all", 0)
            
            # Cache metrics (may not be available for Free zones)
            cached_requests = totals.get("requests", {}).get("cached", 0)
            cache_hit_ratio = None
            if requests > 0 and cached_requests > 0:
                cache_hit_ratio = cached_requests / requests
            
            # Threats (may not be available for Free zones)
            threats = totals.get("threats", {}).get("all", 0)
            
            # Page views (may not be available for Free zones)
            page_views = totals.get("pageviews", {}).get("all", 0)
            
            # Calculate peak requests per hour (approximate)
            time_diff_hours = (datetime.fromisoformat(until.rstrip('Z')) - 
                             datetime.fromisoformat(since.rstrip('Z'))).total_seconds() / 3600
            peak_requests_per_hour = None
            if time_diff_hours > 0 and requests > 0:
                peak_requests_per_hour = int(requests / time_diff_hours)
            
            log_info(
                f"Retrieved REST analytics for zone {zone_id}: "
                f"{requests} requests, {bandwidth} bytes, "
                f"cache hit ratio: {cache_hit_ratio if cache_hit_ratio else 'N/A'}"
            )
            
            return {
                "zone_id": zone_id,
                "license_type": license_type,
                "requests": requests,
                "bandwidth": bandwidth,
                "unique_visitors": None,  # Not available in REST API
                "cache_hit_ratio": cache_hit_ratio if cache_hit_ratio else None,
                "threats_blocked": threats if threats > 0 else None,
                "peak_requests_per_hour": peak_requests_per_hour
            }
            
        except Exception as e:
            log_exception(e)
            log_error(f"REST analytics failed: {e}")
            return self._create_empty_analytics(zone_id, license_type)
    
    def _create_empty_analytics(self, zone_id: str, license_type: str) -> Dict[str, Any]:
        """
        Create an empty analytics dictionary when data is unavailable.
        
        Args:
            zone_id: CloudFlare zone ID
            license_type: License type string
            
        Returns:
            Analytics dictionary with None values
        """
        return {
            "zone_id": zone_id,
            "license_type": license_type,
            "requests": 0,
            "bandwidth": 0,
            "unique_visitors": None,
            "cache_hit_ratio": None,
            "threats_blocked": None,
            "peak_requests_per_hour": None
        }
