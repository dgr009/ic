#!/usr/bin/env python3
"""
Unit tests for CloudFlare DNS service refactoring.

Tests that the DNS service correctly uses CloudFlareClient and maintains
backward compatibility with list_info command.
"""

import pytest
import warnings
from unittest.mock import Mock, MagicMock, patch
from argparse import Namespace

try:
    from src.ic.platforms.cloudflare.dns import info, list_info
    from src.ic.platforms.cloudflare.client import CloudFlareClient, CloudFlareConfig
except ImportError:
    from ic.platforms.cloudflare.dns import info, list_info
    from ic.platforms.cloudflare.client import CloudFlareClient, CloudFlareConfig


class TestDNSServiceRefactor:
    """Test DNS service refactoring to use CloudFlareClient."""
    
    def test_info_module_has_required_functions(self):
        """Test that info module has required add_arguments and main functions."""
        assert hasattr(info, 'add_arguments')
        assert hasattr(info, 'main')
        assert callable(info.add_arguments)
        assert callable(info.main)
    
    def test_list_info_module_has_required_functions(self):
        """Test that list_info module has required functions for backward compatibility."""
        assert hasattr(list_info, 'add_arguments')
        assert hasattr(list_info, 'main')
        assert callable(list_info.add_arguments)
        assert callable(list_info.main)
    
    def test_list_info_shows_deprecation_warning(self):
        """Test that importing list_info shows deprecation warning."""
        # The warning is shown on import, so we need to reload the module
        import importlib
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Reload to trigger the warning
            try:
                from src.ic.platforms.cloudflare.dns import list_info as test_module
                importlib.reload(test_module)
            except ImportError:
                from ic.platforms.cloudflare.dns import list_info as test_module
                importlib.reload(test_module)
            
            # Check that a deprecation warning was issued
            assert len(w) >= 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
    
    def test_info_add_arguments(self):
        """Test that add_arguments adds correct CLI arguments."""
        parser = Mock()
        parser.add_argument = Mock()
        
        info.add_arguments(parser)
        
        # Verify arguments were added
        assert parser.add_argument.call_count >= 2
        
        # Check for account and zone arguments
        calls = [str(call) for call in parser.add_argument.call_args_list]
        assert any('-a' in str(call) or '--account' in str(call) for call in calls)
        assert any('-z' in str(call) or '--zone' in str(call) for call in calls)
    
    @patch('src.ic.platforms.cloudflare.dns.info.CloudFlareClient')
    @patch('src.ic.platforms.cloudflare.dns.info.ConfigManager')
    def test_info_main_with_missing_credentials(self, mock_config_manager, mock_client):
        """Test that main handles missing credentials gracefully."""
        # Mock config with missing credentials
        mock_config_manager_instance = Mock()
        mock_config_manager.return_value = mock_config_manager_instance
        
        with patch('src.ic.platforms.cloudflare.dns.info.CloudFlareConfig') as mock_config_class:
            mock_config = Mock()
            mock_config.email = ''
            mock_config.api_token = ''
            mock_config_class.from_config_manager.return_value = mock_config
            
            args = Namespace(account=None, zone=None)
            result = info.main(args)
            
            # Verify error response
            assert result['success'] is False
            assert 'error' in result
            assert 'credentials' in result['error'].lower()
    
    @patch('src.ic.platforms.cloudflare.dns.info.CloudFlareClient')
    @patch('src.ic.platforms.cloudflare.dns.info.ConfigManager')
    @patch('src.ic.platforms.cloudflare.dns.info.console')
    def test_info_main_with_valid_credentials(self, mock_console, mock_config_manager, mock_client_class):
        """Test that main executes successfully with valid credentials."""
        # Mock config with valid credentials
        mock_config_manager_instance = Mock()
        mock_config_manager.return_value = mock_config_manager_instance
        
        with patch('src.ic.platforms.cloudflare.dns.info.CloudFlareConfig') as mock_config_class:
            mock_config = Mock()
            mock_config.email = 'test@example.com'
            mock_config.api_token = 'test_token'
            mock_config.accounts = []
            mock_config.zones = []
            mock_config_class.from_config_manager.return_value = mock_config
            
            # Mock client
            mock_client = Mock()
            mock_client.get_accounts.return_value = [
                {'id': 'acc1', 'name': 'Test Account'}
            ]
            mock_client.get_zones.return_value = [
                {'id': 'zone1', 'name': 'example.com'}
            ]
            mock_client.get_dns_records.return_value = [
                {
                    'type': 'A',
                    'name': 'example.com',
                    'content': '192.0.2.1',
                    'proxied': True,
                    'ttl': 300,
                    'created_on': '2024-01-01T00:00:00.000Z',
                    'modified_on': '2024-01-01T00:00:00.000Z',
                    'comment': ''
                }
            ]
            mock_client_class.return_value = mock_client
            
            args = Namespace(account=None, zone=None)
            
            with patch('src.ic.platforms.cloudflare.dns.info.ManualProgress'):
                result = info.main(args)
            
            # Verify success
            assert result['success'] is True
            assert 'data' in result
            assert result['data']['accounts'] == 1
            assert result['data']['zones'] == 1
    
    def test_helper_functions_exist(self):
        """Test that helper functions are available."""
        assert hasattr(info, 'type_color')
        assert hasattr(info, 'proxy_color')
        assert hasattr(info, 'simplify_name')
        assert hasattr(info, 'format_time')
        assert hasattr(info, 'display_dns_table')
    
    def test_type_color_returns_correct_colors(self):
        """Test that type_color returns appropriate colors for record types."""
        assert info.type_color('A') == 'cyan'
        assert info.type_color('CNAME') == 'green'
        assert info.type_color('MX') == 'yellow'
        assert info.type_color('UNKNOWN') == 'white'
    
    def test_proxy_color_returns_correct_colors(self):
        """Test that proxy_color returns appropriate colors for proxy status."""
        assert info.proxy_color(True) == 'bright_green'
        assert info.proxy_color(False) == 'bright_red'
    
    def test_simplify_name_removes_zone_suffix(self):
        """Test that simplify_name correctly removes zone suffix."""
        assert info.simplify_name('example.com', 'example.com') == 'example.com'
        assert info.simplify_name('www.example.com', 'example.com') == 'www'
        assert info.simplify_name('api.example.com', 'example.com') == 'api'
        assert info.simplify_name('other.com', 'example.com') == 'other.com'
    
    def test_format_time_converts_iso_timestamp(self):
        """Test that format_time converts ISO timestamps correctly."""
        result = info.format_time('2024-01-15T14:30:45.123Z')
        assert result == '2024-01-15 14:30'
        
        # Test invalid format returns original
        invalid = 'invalid-timestamp'
        assert info.format_time(invalid) == invalid


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
