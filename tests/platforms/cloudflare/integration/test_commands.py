#!/usr/bin/env python3
"""
CloudFlare Integration Tests

End-to-end integration tests for CloudFlare commands with mocked API responses.
Tests all CloudFlare services including account, zone, DNS, traffic, WAF, and page rules.
Verifies console output format, log file entries, and error scenarios.
"""

import pytest
import responses
import argparse
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from io import StringIO

try:
    from src.ic.platforms.cloudflare.client import (
        CloudFlareClient,
        CloudFlareConfig,
        AuthenticationError,
        RateLimitError,
        NetworkError
    )
    from src.ic.platforms.cloudflare.account import info as account_info
    from src.ic.platforms.cloudflare.zone import info as zone_info
    from src.ic.platforms.cloudflare.dns import info as dns_info
    from src.ic.platforms.cloudflare.traffic import info as traffic_info
    from src.ic.platforms.cloudflare.waf import info as waf_info
    from src.ic.platforms.cloudflare.rules import info as rules_info
except ImportError:
    from ic.platforms.cloudflare.client import (
        CloudFlareClient,
        CloudFlareConfig,
        AuthenticationError,
        RateLimitError,
        NetworkError
    )
    from ic.platforms.cloudflare.account import info as account_info
    from ic.platforms.cloudflare.zone import info as zone_info
    from ic.platforms.cloudflare.dns import info as dns_info
    from ic.platforms.cloudflare.traffic import info as traffic_info
    from ic.platforms.cloudflare.waf import info as waf_info
    from ic.platforms.cloudflare.rules import info as rules_info


class TestAccountInfoCommand:
    """Test account info command end-to-end."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager with test credentials."""
        mock_cm = MagicMock()
        mock_cm.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': ['Production'],
                'cloudflare_zones': []
            }
        }
        return mock_cm
    
    @responses.activate
    def test_account_info_success(self, mock_config_manager):
        """Test successful account info retrieval."""
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [
                    {
                        'id': 'acc1',
                        'name': 'Production Account',
                        'type': 'enterprise',
                        'settings': {'enforce_twofactor': True}
                    },
                    {
                        'id': 'acc2',
                        'name': 'Development Account',
                        'type': 'free',
                        'settings': {'enforce_twofactor': False}
                    }
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Create args
        args = argparse.Namespace(account=None)
        
        # Patch ConfigManager
        with patch('src.ic.platforms.cloudflare.account.info.ConfigManager', return_value=mock_config_manager):
            # Capture console output
            with patch('src.ic.platforms.cloudflare.account.info.console') as mock_console:
                result = account_info.main(args)
        
        # Verify result
        # Note: The config has 'Production' filter, so only 1 account will be returned
        assert result['success'] is True
        assert 'data' in result
        assert result['data']['count'] == 1  # Filtered by config
        assert len(result['data']['accounts']) == 1
        assert result['data']['accounts'][0]['name'] == 'Production Account'
        
        # Verify console output was called
        assert mock_console.print.called
    
    @responses.activate
    def test_account_info_with_filter(self, mock_config_manager):
        """Test account info with CLI filter."""
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
        
        # Create args with filter
        args = argparse.Namespace(account='Production')
        
        # Patch ConfigManager
        with patch('src.ic.platforms.cloudflare.account.info.ConfigManager', return_value=mock_config_manager):
            with patch('src.ic.platforms.cloudflare.account.info.console'):
                result = account_info.main(args)
        
        # Verify result - should only return Production account
        assert result['success'] is True
        assert result['data']['count'] == 1
        assert result['data']['accounts'][0]['name'] == 'Production Account'
    
    @responses.activate
    def test_account_info_no_accounts(self, mock_config_manager):
        """Test account info with no matching accounts."""
        # Mock API response with no accounts
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        args = argparse.Namespace(account=None)
        
        with patch('src.ic.platforms.cloudflare.account.info.ConfigManager', return_value=mock_config_manager):
            with patch('src.ic.platforms.cloudflare.account.info.console'):
                result = account_info.main(args)
        
        # Should still succeed but with 0 accounts
        assert result['success'] is True
        assert result['data']['count'] == 0


class TestZoneInfoCommand:
    """Test zone info command end-to-end."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager with test credentials."""
        mock_cm = MagicMock()
        mock_cm.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': [],
                'cloudflare_zones': []
            }
        }
        return mock_cm
    
    @responses.activate
    def test_zone_info_multiple_accounts(self, mock_config_manager):
        """Test zone info with multiple accounts."""
        # Mock accounts response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [
                    {'id': 'acc1', 'name': 'Production Account'},
                    {'id': 'acc2', 'name': 'Development Account'}
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Mock zones for account 1
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': [
                    {
                        'id': 'zone1',
                        'name': 'example.com',
                        'status': 'active',
                        'plan': {'name': 'Enterprise'},
                        'name_servers': ['ns1.cloudflare.com', 'ns2.cloudflare.com']
                    }
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Mock zones for account 2
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': [
                    {
                        'id': 'zone2',
                        'name': 'dev.example.com',
                        'status': 'active',
                        'plan': {'name': 'Free'},
                        'name_servers': ['ns3.cloudflare.com']
                    }
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        args = argparse.Namespace(account=None, zone=None)
        
        with patch('src.ic.platforms.cloudflare.zone.info.ConfigManager', return_value=mock_config_manager):
            with patch('src.ic.platforms.cloudflare.zone.info.console'):
                result = zone_info.main(args)
        
        # Verify result
        assert result['success'] is True
        assert result['data']['total_zones'] == 2
        assert result['data']['total_accounts'] == 2
        assert 'Production Account' in result['data']['zones_by_account']
        assert 'Development Account' in result['data']['zones_by_account']


class TestDNSInfoCommand:
    """Test DNS info command end-to-end."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager with test credentials."""
        mock_cm = MagicMock()
        mock_cm.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': [],
                'cloudflare_zones': ['example.com']
            }
        }
        return mock_cm
    
    @responses.activate
    def test_dns_info_with_filtering(self, mock_config_manager):
        """Test DNS info command with zone filtering."""
        # Mock accounts response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [{'id': 'acc1', 'name': 'Production Account'}],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Mock zones response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': [
                    {'id': 'zone1', 'name': 'example.com', 'status': 'active'}
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Mock DNS records response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/dns_records',
            json={
                'success': True,
                'result': [
                    {
                        'id': 'rec1',
                        'type': 'A',
                        'name': 'example.com',
                        'content': '192.0.2.1',
                        'ttl': 3600,
                        'proxied': True
                    },
                    {
                        'id': 'rec2',
                        'type': 'CNAME',
                        'name': 'www.example.com',
                        'content': 'example.com',
                        'ttl': 3600,
                        'proxied': True
                    }
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        args = argparse.Namespace(account=None, zone=None)
        
        with patch('src.ic.platforms.cloudflare.dns.info.ConfigManager', return_value=mock_config_manager):
            with patch('src.ic.platforms.cloudflare.dns.info.console'):
                result = dns_info.main(args)
        
        # Verify result
        assert result['success'] is True
        assert result['data']['zones'] == 1  # 1 zone processed
        assert result['data']['accounts'] == 1  # 1 account processed


class TestTrafficInfoCommand:
    """Test traffic info command end-to-end."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager with test credentials."""
        mock_cm = MagicMock()
        mock_cm.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': [],
                'cloudflare_zones': []
            }
        }
        return mock_cm
    
    @responses.activate
    def test_traffic_info_different_time_windows(self, mock_config_manager):
        """Test traffic info with different time windows."""
        # Mock accounts response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [{'id': 'acc1', 'name': 'Production Account'}],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Mock zones response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': [{'id': 'zone1', 'name': 'example.com', 'status': 'active'}],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Mock zone details response
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
        
        # Mock analytics response
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
        
        # Test with different time windows
        for time_window in ['5m', '8h', '1d', '24h']:
            args = argparse.Namespace(account=None, zone=None, time=time_window)
            
            with patch('src.ic.platforms.cloudflare.traffic.info.ConfigManager', return_value=mock_config_manager):
                with patch('src.ic.platforms.cloudflare.traffic.info.console'):
                    result = traffic_info.main(args)
            
            # Verify result
            assert result['success'] is True
            assert result['data']['zones_processed'] == 1
            assert result['data']['time_window'] == time_window


class TestWAFInfoCommand:
    """Test WAF info command end-to-end."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager with test credentials."""
        mock_cm = MagicMock()
        mock_cm.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': [],
                'cloudflare_zones': []
            }
        }
        return mock_cm
    
    @responses.activate
    def test_waf_info_with_rules(self, mock_config_manager):
        """Test WAF info command with firewall rules."""
        # Mock accounts response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [{'id': 'acc1', 'name': 'Production Account'}],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Mock zones response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': [{'id': 'zone1', 'name': 'example.com', 'status': 'active'}],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Mock firewall rules response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/firewall/rules',
            json={
                'success': True,
                'result': [
                    {
                        'id': 'rule1',
                        'action': 'block',
                        'description': 'Block SQL injection',
                        'priority': 1,
                        'paused': False,
                        'filter': {
                            'expression': '(http.request.uri.query contains "union select")'
                        }
                    },
                    {
                        'id': 'rule2',
                        'action': 'challenge',
                        'description': 'Challenge suspicious bots',
                        'priority': 2,
                        'paused': False,
                        'filter': {
                            'expression': '(cf.bot_management.score lt 30)'
                        }
                    }
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        args = argparse.Namespace(account=None, zone=None)
        
        with patch('src.ic.platforms.cloudflare.waf.info.ConfigManager', return_value=mock_config_manager):
            with patch('src.ic.platforms.cloudflare.waf.info.console'):
                result = waf_info.main(args)
        
        # Verify result
        assert result['success'] is True
        assert result['data']['total_rules'] == 2


class TestPageRulesInfoCommand:
    """Test page rules info command end-to-end."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager with test credentials."""
        mock_cm = MagicMock()
        mock_cm.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': [],
                'cloudflare_zones': []
            }
        }
        return mock_cm
    
    @responses.activate
    def test_rules_info_with_page_rules(self, mock_config_manager):
        """Test rules info command with page rules."""
        # Mock accounts response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [{'id': 'acc1', 'name': 'Production Account'}],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Mock zones response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones',
            json={
                'success': True,
                'result': [{'id': 'zone1', 'name': 'example.com', 'status': 'active'}],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        # Mock page rules response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/zones/zone1/pagerules',
            json={
                'success': True,
                'result': [
                    {
                        'id': 'pr1',
                        'status': 'active',
                        'priority': 1,
                        'targets': [
                            {'target': 'url', 'constraint': {'operator': 'matches', 'value': '*example.com/static/*'}}
                        ],
                        'actions': [
                            {'id': 'cache_level', 'value': 'cache_everything'},
                            {'id': 'edge_cache_ttl', 'value': 86400}
                        ]
                    },
                    {
                        'id': 'pr2',
                        'status': 'active',
                        'priority': 2,
                        'targets': [
                            {'target': 'url', 'constraint': {'operator': 'matches', 'value': 'http://*example.com/*'}}
                        ],
                        'actions': [
                            {'id': 'always_use_https', 'value': 'on'}
                        ]
                    }
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        args = argparse.Namespace(account=None, zone=None)
        
        with patch('src.ic.platforms.cloudflare.rules.info.ConfigManager', return_value=mock_config_manager):
            with patch('src.ic.platforms.cloudflare.rules.info.console'):
                result = rules_info.main(args)
        
        # Verify result
        assert result['success'] is True
        assert result['data']['total_rules'] == 2


class TestErrorScenarios:
    """Test error scenarios for all commands."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager with test credentials."""
        mock_cm = MagicMock()
        mock_cm.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': [],
                'cloudflare_zones': []
            }
        }
        return mock_cm
    
    @responses.activate
    def test_authentication_failure(self, mock_config_manager):
        """Test authentication failure error handling."""
        # Mock 401 authentication error
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={'success': False, 'errors': [{'message': 'Invalid credentials'}]},
            status=401
        )
        
        args = argparse.Namespace(account=None)
        
        with patch('src.ic.platforms.cloudflare.account.info.ConfigManager', return_value=mock_config_manager):
            with patch('src.ic.platforms.cloudflare.account.info.console'):
                result = account_info.main(args)
        
        # Verify error handling
        assert result['success'] is False
        assert result['error'] == 'Authentication failed'
    
    @responses.activate
    def test_rate_limit_error(self, mock_config_manager):
        """Test rate limit error handling."""
        # Mock 429 rate limit error
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={'success': False, 'errors': [{'message': 'Rate limit exceeded'}]},
            status=429,
            headers={'Retry-After': '120'}
        )
        
        args = argparse.Namespace(account=None)
        
        with patch('src.ic.platforms.cloudflare.account.info.ConfigManager', return_value=mock_config_manager):
            with patch('src.ic.platforms.cloudflare.account.info.console'):
                result = account_info.main(args)
        
        # Verify error handling
        assert result['success'] is False
        assert result['error'] == 'Rate limit exceeded'
    
    @responses.activate
    def test_network_error(self, mock_config_manager):
        """Test network error handling."""
        import requests
        
        # Mock connection error
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            body=requests.exceptions.ConnectionError()
        )
        
        args = argparse.Namespace(account=None)
        
        with patch('src.ic.platforms.cloudflare.account.info.ConfigManager', return_value=mock_config_manager):
            with patch('src.ic.platforms.cloudflare.account.info.console'):
                result = account_info.main(args)
        
        # Verify error handling
        assert result['success'] is False
        assert result['error'] == 'Network error'
    
    def test_missing_credentials(self):
        """Test missing credentials error handling."""
        # Mock ConfigManager with missing credentials
        mock_cm = MagicMock()
        mock_cm.load_all_configs.return_value = {
            'cloudflare': {
                'email': '',
                'api_token': '',
                'cloudflare_accounts': [],
                'cloudflare_zones': []
            }
        }
        
        args = argparse.Namespace(account=None)
        
        with patch('src.ic.platforms.cloudflare.account.info.ConfigManager', return_value=mock_cm):
            with patch('src.ic.platforms.cloudflare.account.info.console'):
                result = account_info.main(args)
        
        # Verify error handling
        assert result['success'] is False
        assert result['error'] == 'Missing credentials'


class TestConsoleOutputFormat:
    """Test console output format verification."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager with test credentials."""
        mock_cm = MagicMock()
        mock_cm.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': [],
                'cloudflare_zones': []
            }
        }
        return mock_cm
    
    @responses.activate
    def test_account_info_console_output(self, mock_config_manager):
        """Test account info console output format."""
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [
                    {'id': 'acc1', 'name': 'Production Account', 'type': 'enterprise', 'settings': {}}
                ],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        args = argparse.Namespace(account=None)
        
        with patch('src.ic.platforms.cloudflare.account.info.ConfigManager', return_value=mock_config_manager):
            # Capture console output
            with patch('src.ic.platforms.cloudflare.account.info.console') as mock_console:
                result = account_info.main(args)
        
        # Verify console.print was called
        assert mock_console.print.called
        
        # Verify success message was printed
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        success_message_found = any('✓' in str(call) or 'Retrieved' in str(call) for call in print_calls)
        assert success_message_found


class TestLogFileEntries:
    """Test log file entries verification."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager with test credentials."""
        mock_cm = MagicMock()
        mock_cm.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': [],
                'cloudflare_zones': []
            }
        }
        return mock_cm
    
    @responses.activate
    def test_log_entries_created(self, mock_config_manager):
        """Test that log entries are created during command execution."""
        # Mock API response
        responses.add(
            responses.GET,
            'https://api.cloudflare.com/client/v4/accounts',
            json={
                'success': True,
                'result': [{'id': 'acc1', 'name': 'Production Account', 'type': 'enterprise'}],
                'result_info': {'page': 1, 'per_page': 50, 'total_pages': 1}
            },
            status=200
        )
        
        args = argparse.Namespace(account=None)
        
        with patch('src.ic.platforms.cloudflare.account.info.ConfigManager', return_value=mock_config_manager):
            with patch('src.ic.platforms.cloudflare.account.info.console'):
                # Capture log calls
                with patch('src.ic.platforms.cloudflare.account.info.log_info') as mock_log_info:
                    result = account_info.main(args)
        
        # Verify log_info was called
        assert mock_log_info.called
        
        # Verify specific log messages
        log_calls = [str(call) for call in mock_log_info.call_args_list]
        assert any('Initializing CloudFlare client' in str(call) for call in log_calls)
        assert any('Successfully retrieved' in str(call) for call in log_calls)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
