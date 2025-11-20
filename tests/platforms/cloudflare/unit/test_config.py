#!/usr/bin/env python3
"""
Unit tests for CloudFlare configuration data model.

Tests the CloudFlareConfig dataclass and its from_config_manager() method.
"""

import pytest
from unittest.mock import Mock, MagicMock

try:
    from src.ic.platforms.cloudflare.client import CloudFlareConfig
except ImportError:
    from ic.platforms.cloudflare.client import CloudFlareConfig


class TestCloudFlareConfig:
    """Test CloudFlareConfig dataclass."""
    
    def test_from_config_manager_with_comma_separated_accounts(self):
        """Test parsing comma-separated account filters."""
        # Mock ConfigManager
        mock_config_manager = Mock()
        mock_config_manager.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': 'Production, Development, Staging',
                'cloudflare_zones': []
            }
        }
        
        # Load config
        config = CloudFlareConfig.from_config_manager(mock_config_manager)
        
        # Verify
        assert config.email == 'test@example.com'
        assert config.api_token == 'test_token_123'
        assert config.accounts == ['Production', 'Development', 'Staging']
        assert config.zones == []
    
    def test_from_config_manager_with_list_accounts(self):
        """Test parsing list-format account filters."""
        # Mock ConfigManager
        mock_config_manager = Mock()
        mock_config_manager.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': ['Production', 'Development', 'Staging'],
                'cloudflare_zones': []
            }
        }
        
        # Load config
        config = CloudFlareConfig.from_config_manager(mock_config_manager)
        
        # Verify
        assert config.accounts == ['Production', 'Development', 'Staging']
    
    def test_from_config_manager_with_comma_separated_zones(self):
        """Test parsing comma-separated zone filters."""
        # Mock ConfigManager
        mock_config_manager = Mock()
        mock_config_manager.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': [],
                'cloudflare_zones': 'example.com, test.com, dev.example.com'
            }
        }
        
        # Load config
        config = CloudFlareConfig.from_config_manager(mock_config_manager)
        
        # Verify
        assert config.zones == ['example.com', 'test.com', 'dev.example.com']
    
    def test_from_config_manager_with_list_zones(self):
        """Test parsing list-format zone filters."""
        # Mock ConfigManager
        mock_config_manager = Mock()
        mock_config_manager.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': [],
                'cloudflare_zones': ['example.com', 'test.com', 'dev.example.com']
            }
        }
        
        # Load config
        config = CloudFlareConfig.from_config_manager(mock_config_manager)
        
        # Verify
        assert config.zones == ['example.com', 'test.com', 'dev.example.com']
    
    def test_from_config_manager_with_empty_filters(self):
        """Test handling empty filter lists."""
        # Mock ConfigManager
        mock_config_manager = Mock()
        mock_config_manager.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': [],
                'cloudflare_zones': []
            }
        }
        
        # Load config
        config = CloudFlareConfig.from_config_manager(mock_config_manager)
        
        # Verify empty lists
        assert config.accounts == []
        assert config.zones == []
    
    def test_from_config_manager_with_missing_filters(self):
        """Test handling missing filter configuration."""
        # Mock ConfigManager
        mock_config_manager = Mock()
        mock_config_manager.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123'
                # No cloudflare_accounts or cloudflare_zones keys
            }
        }
        
        # Load config
        config = CloudFlareConfig.from_config_manager(mock_config_manager)
        
        # Verify empty lists for missing filters
        assert config.accounts == []
        assert config.zones == []
    
    def test_from_config_manager_with_empty_string_filters(self):
        """Test handling empty string filters."""
        # Mock ConfigManager
        mock_config_manager = Mock()
        mock_config_manager.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': '',
                'cloudflare_zones': ''
            }
        }
        
        # Load config
        config = CloudFlareConfig.from_config_manager(mock_config_manager)
        
        # Verify empty lists for empty strings
        assert config.accounts == []
        assert config.zones == []
    
    def test_from_config_manager_with_whitespace_in_filters(self):
        """Test handling whitespace in filter values."""
        # Mock ConfigManager
        mock_config_manager = Mock()
        mock_config_manager.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': '  Production  ,  Development  ,  Staging  ',
                'cloudflare_zones': ['  example.com  ', '  test.com  ']
            }
        }
        
        # Load config
        config = CloudFlareConfig.from_config_manager(mock_config_manager)
        
        # Verify whitespace is stripped
        assert config.accounts == ['Production', 'Development', 'Staging']
        assert config.zones == ['example.com', 'test.com']
    
    def test_from_config_manager_with_empty_list_items(self):
        """Test handling empty items in filter lists."""
        # Mock ConfigManager
        mock_config_manager = Mock()
        mock_config_manager.load_all_configs.return_value = {
            'cloudflare': {
                'email': 'test@example.com',
                'api_token': 'test_token_123',
                'cloudflare_accounts': ['Production', '', 'Development', None, 'Staging'],
                'cloudflare_zones': 'example.com,,test.com,,'
            }
        }
        
        # Load config
        config = CloudFlareConfig.from_config_manager(mock_config_manager)
        
        # Verify empty items are filtered out
        assert config.accounts == ['Production', 'Development', 'Staging']
        assert config.zones == ['example.com', 'test.com']
    
    def test_from_config_manager_with_missing_credentials(self):
        """Test handling missing credentials."""
        # Mock ConfigManager
        mock_config_manager = Mock()
        mock_config_manager.load_all_configs.return_value = {
            'cloudflare': {
                'cloudflare_accounts': ['Production'],
                'cloudflare_zones': ['example.com']
            }
        }
        
        # Load config
        config = CloudFlareConfig.from_config_manager(mock_config_manager)
        
        # Verify empty strings for missing credentials
        assert config.email == ''
        assert config.api_token == ''
        assert config.accounts == ['Production']
        assert config.zones == ['example.com']
    
    def test_from_config_manager_with_no_cloudflare_section(self):
        """Test handling missing cloudflare configuration section."""
        # Mock ConfigManager
        mock_config_manager = Mock()
        mock_config_manager.load_all_configs.return_value = {
            'aws': {},
            'azure': {}
            # No cloudflare section
        }
        
        # Load config
        config = CloudFlareConfig.from_config_manager(mock_config_manager)
        
        # Verify defaults
        assert config.email == ''
        assert config.api_token == ''
        assert config.accounts == []
        assert config.zones == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
