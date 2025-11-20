#!/usr/bin/env python3
"""
Unit tests for CloudFlare API Client.

Tests the CloudFlareClient class methods, error handling, and pagination logic.
Uses responses library to mock CloudFlare API responses.
"""

import pytest
import responses
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

try:
    from src.ic.platforms.cloudflare.client import (
        CloudFlareClient,
        CloudFlareConfig,
        AuthenticationError,
        RateLimitError,
        NetworkError,
        CloudFlareAPIError
    )
except ImportError:
    from ic.platforms.cloudflare.client import (
        CloudFlareClient,
        CloudFlareConfig,
        AuthenticationError,
        RateLimitError,
        NetworkError,
        CloudFlareAPIError
    )


class TestCloudFlareClient:
    """Test CloudFlareClient class."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return CloudFlareConfig(
            email='test@example.com',
            api_token='test_token_123',
            accounts=['Production'],
            zones=['example.com']
        )
    
    @pytest.fixture
    def client(self, config):
        """Create a test client."""
        return CloudFlareClient(config)
    
    def test_client_initialization_success(self, config):
        """Test successful client initialization."""
        client = CloudFlareClient(config)
        
        assert client.config == config
        assert client.headers['X-Auth-Email'] == 'test@example.com'
        assert client.headers['Authorization'] == 'Bearer test_token_123'
        assert client.headers['Content-Type'] == 'application/json'
    
    def test_client_initialization_missing_email(self):
        """Test client initialization fails with missing email."""
        config = CloudFlareConfig(
            email='',
            api_token='test_token_123',
            accounts=[],
            zones=[]
        )
        
        with pytest.raises(AuthenticationError) as exc_info:
            CloudFlareClient(config)
        
        assert 'credentials not configured' in str(exc_info.value).lower()
    
    def test_client_initialization_missing_token(self):
        """Test client initialization fails with missing token."""
        config = CloudFlareConfig(
            email='test@example.com',
            api_token='',
            accounts=[],
            zones=[]
        )
        
        with pytest.raises(AuthenticationError) as exc_info:
            CloudFlareClient(config)
        
        assert 'credentials not configured' in str(exc_info.value).lower()
    
    @responses.activate
    def test_get_accounts_success(self, client):
        """Test successful account retrieval."""
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [
                    {'id': 'acc1', 'name': 'Production Account', 'type': 'enterprise'},
                    {'id': 'acc2', 'name': 'Development Account', 'type': 'free'}
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        accounts = client.get_accounts()
        
        assert len(accounts) == 2
        assert accounts[0]['name'] == 'Production Account'
        assert accounts[1]['name'] == 'Development Account'
    
    @responses.activate
    def test_get_accounts_with_filter(self, client):
        """Test account retrieval with name filter."""
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [
                    {'id': 'acc1', 'name': 'Production Account', 'type': 'enterprise'},
                    {'id': 'acc2', 'name': 'Development Account', 'type': 'free'},
                    {'id': 'acc3', 'name': 'Staging Account', 'type': 'free'}
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        accounts = client.get_accounts(name_filter=['Production', 'Staging'])
        
        assert len(accounts) == 2
        assert accounts[0]['name'] == 'Production Account'
        assert accounts[1]['name'] == 'Staging Account'
    
    @responses.activate
    def test_get_accounts_case_insensitive_filter(self, client):
        """Test account filtering is case-insensitive."""
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [
                    {'id': 'acc1', 'name': 'Production Account', 'type': 'enterprise'},
                    {'id': 'acc2', 'name': 'development account', 'type': 'free'}
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        accounts = client.get_accounts(name_filter=['PRODUCTION', 'DEVELOPMENT'])
        
        assert len(accounts) == 2
    
    @responses.activate
    def test_get_accounts_pagination(self, client):
        """Test account retrieval with pagination."""
        # Mock first page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [
                    {'id': 'acc1', 'name': 'Account 1', 'type': 'free'},
                    {'id': 'acc2', 'name': 'Account 2', 'type': 'free'}
                ],
                'result_info': {'page': 1, 'per_page': 2, 'total_pages': 2}
            },
            status=200
        )
        
        # Mock second page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [
                    {'id': 'acc3', 'name': 'Account 3', 'type': 'free'}
                ],
                'result_info': {'page': 2, 'per_page': 2, 'total_pages': 2}
            },
            status=200
        )
        
        accounts = client.get_accounts()
        
        assert len(accounts) == 3
        assert accounts[0]['name'] == 'Account 1'
        assert accounts[2]['name'] == 'Account 3'
    
    @responses.activate
    def test_get_zones_success(self, client):
        """Test successful zone retrieval."""
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': [
                    {'id': 'zone1', 'name': 'example.com', 'status': 'active'},
                    {'id': 'zone2', 'name': 'test.com', 'status': 'active'}
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        zones = client.get_zones('acc1')
        
        assert len(zones) == 2
        assert zones[0]['name'] == 'example.com'
        assert zones[1]['name'] == 'test.com'
    
    @responses.activate
    def test_get_zones_with_filter(self, client):
        """Test zone retrieval with name filter."""
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': [
                    {'id': 'zone1', 'name': 'example.com', 'status': 'active'},
                    {'id': 'zone2', 'name': 'test.com', 'status': 'active'},
                    {'id': 'zone3', 'name': 'dev.example.com', 'status': 'active'}
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        zones = client.get_zones('acc1', name_filter=['example.com'])
        
        assert len(zones) == 2
        assert 'example.com' in zones[0]['name']
        assert 'example.com' in zones[1]['name']
    
    @responses.activate
    def test_get_zones_pagination(self, client):
        """Test zone retrieval with pagination."""
        # Mock first page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': [
                    {'id': 'zone1', 'name': 'zone1.com', 'status': 'active'},
                    {'id': 'zone2', 'name': 'zone2.com', 'status': 'active'}
                ],
                'result_info': {'page': 1, 'per_page': 2, 'total_pages': 3}
            },
            status=200
        )
        
        # Mock second page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': [
                    {'id': 'zone3', 'name': 'zone3.com', 'status': 'active'},
                    {'id': 'zone4', 'name': 'zone4.com', 'status': 'active'}
                ],
                'result_info': {'page': 2, 'per_page': 2, 'total_pages': 3}
            },
            status=200
        )
        
        # Mock third page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': [
                    {'id': 'zone5', 'name': 'zone5.com', 'status': 'active'}
                ],
                'result_info': {'page': 3, 'per_page': 2, 'total_pages': 3}
            },
            status=200
        )
        
        zones = client.get_zones('acc1')
        
        assert len(zones) == 5
        assert zones[0]['name'] == 'zone1.com'
        assert zones[4]['name'] == 'zone5.com'
    
    @responses.activate
    def test_get_dns_records_success(self, client):
        """Test successful DNS records retrieval."""
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/dns_records',
            json={
                'success': True,
                'result': [
                    {'id': 'rec1', 'type': 'A', 'name': 'example.com', 'content': '192.0.2.1'},
                    {'id': 'rec2', 'type': 'CNAME', 'name': 'www.example.com', 'content': 'example.com'}
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        records = client.get_dns_records('zone1')
        
        assert len(records) == 2
        assert records[0]['type'] == 'A'
        assert records[1]['type'] == 'CNAME'
    
    @responses.activate
    def test_get_dns_records_pagination(self, client):
        """Test DNS records retrieval with pagination."""
        # Mock first page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/dns_records',
            json={
                'success': True,
                'result': [
                    {'id': 'rec1', 'type': 'A', 'name': 'example.com', 'content': '192.0.2.1'}
                ],
                'result_info': {'page': 1, 'per_page': 1, 'total_pages': 2}
            },
            status=200
        )
        
        # Mock second page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/dns_records',
            json={
                'success': True,
                'result': [
                    {'id': 'rec2', 'type': 'CNAME', 'name': 'www.example.com', 'content': 'example.com'}
                ],
                'result_info': {'page': 2, 'per_page': 1, 'total_pages': 2}
            },
            status=200
        )
        
        records = client.get_dns_records('zone1')
        
        assert len(records) == 2
    
    @responses.activate
    def test_get_firewall_rules_success(self, client):
        """Test successful firewall rules retrieval."""
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/firewall/rules',
            json={
                'success': True,
                'result': [
                    {'id': 'rule1', 'action': 'block', 'description': 'Block SQL injection'},
                    {'id': 'rule2', 'action': 'challenge', 'description': 'Challenge bots'}
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        rules = client.get_firewall_rules('zone1')
        
        assert len(rules) == 2
        assert rules[0]['action'] == 'block'
        assert rules[1]['action'] == 'challenge'
    
    @responses.activate
    def test_get_firewall_rules_pagination(self, client):
        """Test firewall rules retrieval with pagination."""
        # Mock first page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/firewall/rules',
            json={
                'success': True,
                'result': [
                    {'id': 'rule1', 'action': 'block', 'description': 'Rule 1'}
                ],
                'result_info': {'page': 1, 'per_page': 1, 'total_pages': 2}
            },
            status=200
        )
        
        # Mock second page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/firewall/rules',
            json={
                'success': True,
                'result': [
                    {'id': 'rule2', 'action': 'allow', 'description': 'Rule 2'}
                ],
                'result_info': {'page': 2, 'per_page': 1, 'total_pages': 2}
            },
            status=200
        )
        
        rules = client.get_firewall_rules('zone1')
        
        assert len(rules) == 2
    
    @responses.activate
    def test_get_page_rules_success(self, client):
        """Test successful page rules retrieval."""
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/pagerules',
            json={
                'success': True,
                'result': [
                    {'id': 'pr1', 'status': 'active', 'priority': 1},
                    {'id': 'pr2', 'status': 'disabled', 'priority': 2}
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        rules = client.get_page_rules('zone1')
        
        assert len(rules) == 2
        assert rules[0]['status'] == 'active'
        assert rules[1]['status'] == 'disabled'
    
    @responses.activate
    def test_get_page_rules_pagination(self, client):
        """Test page rules retrieval with pagination."""
        # Mock first page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/pagerules',
            json={
                'success': True,
                'result': [
                    {'id': 'pr1', 'status': 'active', 'priority': 1}
                ],
                'result_info': {'page': 1, 'per_page': 1, 'total_pages': 2}
            },
            status=200
        )
        
        # Mock second page
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/pagerules',
            json={
                'success': True,
                'result': [
                    {'id': 'pr2', 'status': 'disabled', 'priority': 2}
                ],
                'result_info': {'page': 2, 'per_page': 1, 'total_pages': 2}
            },
            status=200
        )
        
        rules = client.get_page_rules('zone1')
        
        assert len(rules) == 2
    
    @responses.activate
    def test_authentication_error_401(self, client):
        """Test handling of 401 authentication error."""
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={'success': False, 'errors': [{'message': 'Invalid credentials'}]},
            status=401
        )
        
        with pytest.raises(AuthenticationError) as exc_info:
            client.get_accounts()
        
        assert 'authentication failed' in str(exc_info.value).lower()
    
    @responses.activate
    def test_authentication_error_403(self, client):
        """Test handling of 403 authentication error."""
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={'success': False, 'errors': [{'message': 'Forbidden'}]},
            status=403
        )
        
        with pytest.raises(AuthenticationError) as exc_info:
            client.get_accounts()
        
        assert 'authentication failed' in str(exc_info.value).lower()
    
    @responses.activate
    def test_rate_limit_error(self, client):
        """Test handling of rate limit error."""
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={'success': False, 'errors': [{'message': 'Rate limit exceeded'}]},
            status=429,
            headers={'Retry-After': '120'}
        )
        
        with pytest.raises(RateLimitError) as exc_info:
            client.get_accounts()
        
        assert exc_info.value.retry_after == 120
        assert 'rate limit' in str(exc_info.value).lower()
    
    @responses.activate
    def test_rate_limit_error_default_retry(self, client):
        """Test rate limit error with default retry time."""
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={'success': False, 'errors': [{'message': 'Rate limit exceeded'}]},
            status=429
        )
        
        with pytest.raises(RateLimitError) as exc_info:
            client.get_accounts()
        
        assert exc_info.value.retry_after == 60  # Default
    
    @responses.activate
    def test_network_timeout_error(self, client):
        """Test handling of network timeout."""
        import requests
        
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            body=requests.exceptions.Timeout()
        )
        
        with pytest.raises(NetworkError) as exc_info:
            client.get_accounts()
        
        assert 'timeout' in str(exc_info.value).lower()
    
    @responses.activate
    def test_network_connection_error(self, client):
        """Test handling of connection error."""
        import requests
        
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            body=requests.exceptions.ConnectionError()
        )
        
        with pytest.raises(NetworkError) as exc_info:
            client.get_accounts()
        
        assert 'connect' in str(exc_info.value).lower() or 'network' in str(exc_info.value).lower()
    
    @responses.activate
    def test_api_error_4xx(self, client):
        """Test handling of 4xx API errors."""
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={'success': False, 'errors': [{'message': 'Bad request'}]},
            status=400
        )
        
        with pytest.raises(CloudFlareAPIError) as exc_info:
            client.get_accounts()
        
        assert 'bad request' in str(exc_info.value).lower()
    
    @responses.activate
    def test_api_error_5xx(self, client):
        """Test handling of 5xx API errors."""
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={'success': False, 'errors': [{'message': 'Internal server error'}]},
            status=500
        )
        
        with pytest.raises(CloudFlareAPIError) as exc_info:
            client.get_accounts()
        
        assert '500' in str(exc_info.value)
    
    @responses.activate
    def test_api_success_false_in_response(self, client):
        """Test handling of success=false in API response."""
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': False,
                'errors': [{'message': 'Something went wrong'}],
                'result': []
            },
            status=200
        )
        
        with pytest.raises(CloudFlareAPIError) as exc_info:
            client.get_accounts()
        
        assert 'something went wrong' in str(exc_info.value).lower()


class TestGetAnalytics:
    """Test get_analytics method with Enterprise and Free zones."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return CloudFlareConfig(
            email='test@example.com',
            api_token='test_token_123',
            accounts=[],
            zones=[]
        )
    
    @pytest.fixture
    def client(self, config):
        """Create a test client."""
        return CloudFlareClient(config)
    
    @responses.activate
    def test_get_analytics_enterprise_zone(self, client):
        """Test analytics retrieval for Enterprise zone."""
        # Mock zone details request
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1',
            json={
                'success': True,
                'result': {
                    'id': 'zone1',
                    'name': 'example.com',
                    'plan': {'name': 'Enterprise'}
                }
            },
            status=200
        )
        
        # Mock GraphQL analytics request
        responses.add(
            responses.POST,
            'https://api.cloudflare.com/client/v4/graphql',
            json={
                'data': {
                    'viewer': {
                        'zones': [{
                            'httpRequests1dGroups': [{
                                'sum': {
                                    'requests': 1000000,
                                    'bytes': 5000000000,
                                    'threats': 1500,
                                    'cachedRequests': 800000,
                                    'pageViews': 50000
                                },
                                'uniq': {
                                    'uniques': 25000
                                }
                            }]
                        }]
                    }
                }
            },
            status=200
        )
        
        since = datetime.now() - timedelta(hours=8)
        until = datetime.now()
        
        analytics = client.get_analytics('zone1', since, until)
        
        assert analytics['license_type'] == 'Enterprise'
        assert analytics['requests'] == 1000000
        assert analytics['bandwidth'] == 5000000000
        assert analytics['unique_visitors'] == 25000
        assert analytics['threats_blocked'] == 1500
        assert analytics['cache_hit_ratio'] == 0.8
    
    @responses.activate
    def test_get_analytics_free_zone(self, client):
        """Test analytics retrieval for Free zone."""
        # Mock zone details request
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1',
            json={
                'success': True,
                'result': {
                    'id': 'zone1',
                    'name': 'example.com',
                    'plan': {'name': 'Free'}
                }
            },
            status=200
        )
        
        # Mock REST analytics request
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/analytics/dashboard',
            json={
                'success': True,
                'result': {
                    'totals': {
                        'requests': {'all': 50000, 'cached': 30000},
                        'bandwidth': {'all': 250000000},
                        'threats': {'all': 0},
                        'pageviews': {'all': 0}
                    }
                }
            },
            status=200
        )
        
        since = datetime.now() - timedelta(hours=8)
        until = datetime.now()
        
        analytics = client.get_analytics('zone1', since, until)
        
        assert analytics['license_type'] == 'Free'
        assert analytics['requests'] == 50000
        assert analytics['bandwidth'] == 250000000
        assert analytics['unique_visitors'] is None  # Not available for Free
        assert analytics['cache_hit_ratio'] == 0.6
    
    @responses.activate
    def test_get_analytics_graphql_fallback_to_rest(self, client):
        """Test fallback to REST API when GraphQL fails."""
        # Mock zone details request
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1',
            json={
                'success': True,
                'result': {
                    'id': 'zone1',
                    'name': 'example.com',
                    'plan': {'name': 'Enterprise'}
                }
            },
            status=200
        )
        
        # Mock GraphQL failure
        responses.add(
            responses.POST,
            'https://api.cloudflare.com/client/v4/graphql',
            json={'errors': [{'message': 'GraphQL error'}]},
            status=500
        )
        
        # Mock REST analytics request (fallback)
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/analytics/dashboard',
            json={
                'success': True,
                'result': {
                    'totals': {
                        'requests': {'all': 100000, 'cached': 80000},
                        'bandwidth': {'all': 500000000},
                        'threats': {'all': 500},
                        'pageviews': {'all': 10000}
                    }
                }
            },
            status=200
        )
        
        since = datetime.now() - timedelta(hours=8)
        until = datetime.now()
        
        analytics = client.get_analytics('zone1', since, until)
        
        # Should fall back to REST API
        assert analytics['license_type'] == 'Enterprise'
        assert analytics['requests'] == 100000
        assert analytics['bandwidth'] == 500000000
    
    @responses.activate
    def test_get_analytics_empty_data(self, client):
        """Test analytics with no data available."""
        # Mock zone details request
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1',
            json={
                'success': True,
                'result': {
                    'id': 'zone1',
                    'name': 'example.com',
                    'plan': {'name': 'Free'}
                }
            },
            status=200
        )
        
        # Mock REST analytics with empty data
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/analytics/dashboard',
            json={
                'success': True,
                'result': {
                    'totals': {
                        'requests': {'all': 0},
                        'bandwidth': {'all': 0},
                        'threats': {'all': 0},
                        'pageviews': {'all': 0}
                    }
                }
            },
            status=200
        )
        
        since = datetime.now() - timedelta(hours=8)
        until = datetime.now()
        
        analytics = client.get_analytics('zone1', since, until)
        
        assert analytics['requests'] == 0
        assert analytics['bandwidth'] == 0
        assert analytics['unique_visitors'] is None
        assert analytics['cache_hit_ratio'] is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
