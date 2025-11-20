#!/usr/bin/env python3
"""
Unit tests for CloudFlare firewall rules API method.

Tests the get_firewall_rules() method with pagination support.
"""

import pytest
from unittest.mock import Mock, patch
import responses

try:
    from src.ic.platforms.cloudflare.client import CloudFlareClient, CloudFlareConfig
except ImportError:
    from ic.platforms.cloudflare.client import CloudFlareClient, CloudFlareConfig


class TestFirewallRules:
    """Test CloudFlare firewall rules retrieval."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock CloudFlare configuration."""
        return CloudFlareConfig(
            email='test@example.com',
            api_token='test_token_123',
            accounts=[],
            zones=[]
        )
    
    @responses.activate
    def test_get_firewall_rules_single_page(self, mock_config):
        """Test retrieving firewall rules with single page of results."""
        zone_id = 'zone123'
        
        # Mock API response
        responses.add(
            responses.GET,
            f'https://api.cloudflare.com/client/v4/zones/{zone_id}/firewall/rules?page=1&per_page=50',
            json={
                'success': True,
                'result': [
                    {
                        'id': 'rule1',
                        'priority': 1,
                        'action': 'block',
                        'description': 'Block SQL injection',
                        'filter': {
                            'expression': '(http.request.uri.query contains "union select")'
                        },
                        'paused': False
                    },
                    {
                        'id': 'rule2',
                        'priority': 2,
                        'action': 'challenge',
                        'description': 'Challenge suspicious bots',
                        'filter': {
                            'expression': '(cf.bot_management.score lt 30)'
                        },
                        'paused': False
                    }
                ],
                'result_info': {
                    'page': 1,
                    'per_page': 50,
                    'total_pages': 1,
                    'count': 2,
                    'total_count': 2
                }
            },
            status=200
        )
        
        # Create client and get rules
        client = CloudFlareClient(mock_config)
        rules = client.get_firewall_rules(zone_id)
        
        # Verify
        assert len(rules) == 2
        assert rules[0]['id'] == 'rule1'
        assert rules[0]['action'] == 'block'
        assert rules[0]['priority'] == 1
        assert rules[1]['id'] == 'rule2'
        assert rules[1]['action'] == 'challenge'
        assert rules[1]['priority'] == 2
    
    @responses.activate
    def test_get_firewall_rules_multiple_pages(self, mock_config):
        """Test retrieving firewall rules with pagination."""
        zone_id = 'zone123'
        
        # Mock first page
        responses.add(
            responses.GET,
            f'https://api.cloudflare.com/client/v4/zones/{zone_id}/firewall/rules?page=1&per_page=50',
            json={
                'success': True,
                'result': [
                    {'id': f'rule{i}', 'priority': i, 'action': 'block'}
                    for i in range(1, 51)
                ],
                'result_info': {
                    'page': 1,
                    'per_page': 50,
                    'total_pages': 3,
                    'count': 50,
                    'total_count': 125
                }
            },
            status=200
        )
        
        # Mock second page
        responses.add(
            responses.GET,
            f'https://api.cloudflare.com/client/v4/zones/{zone_id}/firewall/rules?page=2&per_page=50',
            json={
                'success': True,
                'result': [
                    {'id': f'rule{i}', 'priority': i, 'action': 'challenge'}
                    for i in range(51, 101)
                ],
                'result_info': {
                    'page': 2,
                    'per_page': 50,
                    'total_pages': 3,
                    'count': 50,
                    'total_count': 125
                }
            },
            status=200
        )
        
        # Mock third page
        responses.add(
            responses.GET,
            f'https://api.cloudflare.com/client/v4/zones/{zone_id}/firewall/rules?page=3&per_page=50',
            json={
                'success': True,
                'result': [
                    {'id': f'rule{i}', 'priority': i, 'action': 'allow'}
                    for i in range(101, 126)
                ],
                'result_info': {
                    'page': 3,
                    'per_page': 50,
                    'total_pages': 3,
                    'count': 25,
                    'total_count': 125
                }
            },
            status=200
        )
        
        # Create client and get rules
        client = CloudFlareClient(mock_config)
        rules = client.get_firewall_rules(zone_id)
        
        # Verify all pages retrieved
        assert len(rules) == 125
        assert rules[0]['id'] == 'rule1'
        assert rules[0]['action'] == 'block'
        assert rules[50]['id'] == 'rule51'
        assert rules[50]['action'] == 'challenge'
        assert rules[100]['id'] == 'rule101'
        assert rules[100]['action'] == 'allow'
    
    @responses.activate
    def test_get_firewall_rules_empty_result(self, mock_config):
        """Test retrieving firewall rules when zone has no rules."""
        zone_id = 'zone123'
        
        # Mock API response with no rules
        responses.add(
            responses.GET,
            f'https://api.cloudflare.com/client/v4/zones/{zone_id}/firewall/rules?page=1&per_page=50',
            json={
                'success': True,
                'result': [],
                'result_info': {
                    'page': 1,
                    'per_page': 50,
                    'total_pages': 1,
                    'count': 0,
                    'total_count': 0
                }
            },
            status=200
        )
        
        # Create client and get rules
        client = CloudFlareClient(mock_config)
        rules = client.get_firewall_rules(zone_id)
        
        # Verify empty list
        assert len(rules) == 0
        assert rules == []
    
    @responses.activate
    def test_get_firewall_rules_with_detailed_data(self, mock_config):
        """Test retrieving firewall rules with complete rule data."""
        zone_id = 'zone123'
        
        # Mock API response with detailed rule data
        responses.add(
            responses.GET,
            f'https://api.cloudflare.com/client/v4/zones/{zone_id}/firewall/rules?page=1&per_page=50',
            json={
                'success': True,
                'result': [
                    {
                        'id': 'rule1',
                        'priority': 1,
                        'action': 'block',
                        'description': 'Block SQL injection attempts',
                        'filter': {
                            'id': 'filter1',
                            'expression': '(http.request.uri.query contains "union select")',
                            'paused': False,
                            'description': 'SQL injection filter'
                        },
                        'paused': False,
                        'created_on': '2023-01-01T00:00:00Z',
                        'modified_on': '2023-01-15T12:00:00Z'
                    },
                    {
                        'id': 'rule2',
                        'priority': 2,
                        'action': 'challenge',
                        'description': 'Challenge low-scoring bots',
                        'filter': {
                            'id': 'filter2',
                            'expression': '(cf.bot_management.score lt 30)',
                            'paused': False,
                            'description': 'Bot score filter'
                        },
                        'paused': False,
                        'created_on': '2023-01-02T00:00:00Z',
                        'modified_on': '2023-01-16T12:00:00Z'
                    },
                    {
                        'id': 'rule3',
                        'priority': 3,
                        'action': 'allow',
                        'description': 'Allow trusted IPs',
                        'filter': {
                            'id': 'filter3',
                            'expression': '(ip.src in {192.168.1.0/24})',
                            'paused': False,
                            'description': 'Trusted IP filter'
                        },
                        'paused': True,
                        'created_on': '2023-01-03T00:00:00Z',
                        'modified_on': '2023-01-17T12:00:00Z'
                    }
                ],
                'result_info': {
                    'page': 1,
                    'per_page': 50,
                    'total_pages': 1,
                    'count': 3,
                    'total_count': 3
                }
            },
            status=200
        )
        
        # Create client and get rules
        client = CloudFlareClient(mock_config)
        rules = client.get_firewall_rules(zone_id)
        
        # Verify detailed data
        assert len(rules) == 3
        
        # Check first rule (block)
        assert rules[0]['id'] == 'rule1'
        assert rules[0]['action'] == 'block'
        assert rules[0]['priority'] == 1
        assert rules[0]['description'] == 'Block SQL injection attempts'
        assert rules[0]['paused'] is False
        assert 'filter' in rules[0]
        assert rules[0]['filter']['expression'] == '(http.request.uri.query contains "union select")'
        
        # Check second rule (challenge)
        assert rules[1]['id'] == 'rule2'
        assert rules[1]['action'] == 'challenge'
        assert rules[1]['priority'] == 2
        
        # Check third rule (allow, paused)
        assert rules[2]['id'] == 'rule3'
        assert rules[2]['action'] == 'allow'
        assert rules[2]['priority'] == 3
        assert rules[2]['paused'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
