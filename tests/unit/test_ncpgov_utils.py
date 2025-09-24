"""
Unit tests for NCP Gov utilities.

Tests NCP Government Cloud utility functions, enhanced security validation,
compliance checking, and government-specific error handling.
"""

import os
import yaml
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from datetime import datetime

# Import NCP Gov utilities
from common.ncpgov_utils import (
    load_ncpgov_config, validate_ncpgov_config, create_ncpgov_config_directory,
    handle_ncpgov_api_error, validate_government_compliance,
    mask_sensitive_data, audit_log, get_ncpgov_region_name,
    validate_network_policy_compliance, NCPGovOutputFormatter
)
from ncpgov.client import NCPGovClient, NCPGovAPIError


class TestNCPGovConfigUtils:
    """Test cases for NCP Gov configuration utilities."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_config = {
            'default': {
                'access_key': 'gov-access-key',
                'secret_key': 'gov-secret-key',
                'region': 'KR',
                'security_policy': 'government_compliant',
                'audit_logging': True,
                'encryption_enabled': True
            },
            'production': {
                'access_key': 'prod-gov-access-key',
                'secret_key': 'prod-gov-secret-key',
                'region': 'KR',
                'security_policy': 'government_compliant',
                'audit_logging': True,
                'encryption_enabled': True
            }
        }
    
    def test_load_ncpgov_config_success(self):
        """Test successful NCP Gov config loading."""
        config_content = yaml.dump(self.sample_config)
        
        with patch('builtins.open', mock_open(read_data=config_content)):
            with patch('os.path.exists', return_value=True):
                config = load_ncpgov_config()
        
        assert config is not None
        assert 'default' in config
        assert config['default']['access_key'] == 'gov-access-key'
        assert config['default']['security_policy'] == 'government_compliant'
        assert config['default']['audit_logging'] is True
    
    def test_load_ncpgov_config_file_not_found(self):
        """Test NCP Gov config loading when file doesn't exist."""
        with patch('os.path.exists', return_value=False):
            config = load_ncpgov_config()
        
        assert config is None
    
    def test_load_ncpgov_config_invalid_yaml(self):
        """Test NCP Gov config loading with invalid YAML."""
        invalid_yaml = "invalid: yaml: content: ["
        
        with patch('builtins.open', mock_open(read_data=invalid_yaml)):
            with patch('os.path.exists', return_value=True):
                config = load_ncpgov_config()
        
        assert config is None
    
    def test_validate_ncpgov_config_success(self):
        """Test successful NCP Gov config validation."""
        with patch('os.path.exists', return_value=True):
            with patch('common.ncpgov_utils.load_ncpgov_config', return_value=self.sample_config):
                result = validate_ncpgov_config()
        
        assert result is True
    
    def test_validate_ncpgov_config_missing_security_policy(self):
        """Test NCP Gov config validation with missing security policy."""
        invalid_config = {
            'default': {
                'access_key': 'gov-access-key',
                'secret_key': 'gov-secret-key',
                'region': 'KR'
                # Missing security_policy
            }
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('common.ncpgov_utils.load_ncpgov_config', return_value=invalid_config):
                result = validate_ncpgov_config()
        
        assert result is False
    
    def test_validate_ncpgov_config_missing_audit_logging(self):
        """Test NCP Gov config validation with missing audit logging."""
        invalid_config = {
            'default': {
                'access_key': 'gov-access-key',
                'secret_key': 'gov-secret-key',
                'region': 'KR',
                'security_policy': 'government_compliant'
                # Missing audit_logging
            }
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('common.ncpgov_utils.load_ncpgov_config', return_value=invalid_config):
                result = validate_ncpgov_config()
        
        assert result is False
    
    def test_create_ncpgov_config_directory(self):
        """Test NCP Gov config directory creation."""
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path('/home/test')
                
                result = create_ncpgov_config_directory()
                
                assert result == Path('/home/test/.ncpgov')
                mock_mkdir.assert_called_once_with(mode=0o700, exist_ok=True)


class TestNCPGovSecurityValidation:
    """Test cases for NCP Gov security validation utilities."""
    
    def test_validate_government_compliance_success(self):
        """Test government compliance validation for compliant config."""
        compliant_config = {
            'encryption_enabled': True,
            'audit_logging_enabled': True,
            'access_control_enabled': True
        }
        
        result = validate_government_compliance(compliant_config)
        assert result is True
    
    def test_validate_government_compliance_missing_encryption(self):
        """Test compliance validation with missing encryption."""
        non_compliant_config = {
            'encryption_enabled': False,  # Non-compliant
            'audit_logging_enabled': True,
            'access_control_enabled': True
        }
        
        result = validate_government_compliance(non_compliant_config)
        assert result is False
    
    def test_validate_government_compliance_missing_audit_logging(self):
        """Test compliance validation with missing audit logging."""
        non_compliant_config = {
            'encryption_enabled': True,
            'audit_logging_enabled': False,  # Non-compliant
            'access_control_enabled': True
        }
        
        result = validate_government_compliance(non_compliant_config)
        assert result is False
    
    def test_validate_government_compliance_missing_access_control(self):
        """Test compliance validation with missing access control."""
        non_compliant_config = {
            'encryption_enabled': True,
            'audit_logging_enabled': True,
            'access_control_enabled': False  # Non-compliant
        }
        
        result = validate_government_compliance(non_compliant_config)
        assert result is False
    
    def test_mask_sensitive_data_basic(self):
        """Test basic sensitive data masking."""
        sensitive_data = {
            'server_name': 'gov-server-1',
            'private_ip': '10.0.1.100',
            'internal_ip': '192.168.1.10',
            'access_key': 'GOV-AKIA123456789',
            'secret_key': 'gov-secret123456789'
        }
        
        masked_data = mask_sensitive_data(sensitive_data)
        
        # Non-sensitive data should be preserved
        assert masked_data['server_name'] == 'gov-server-1'
        
        # Sensitive data should be masked
        assert '***' in masked_data['private_ip']
        assert '***' in masked_data['access_key']
        assert '***' in masked_data['secret_key']
    
    def test_mask_sensitive_data_preserves_original(self):
        """Test that data masking preserves the original data object."""
        original_data = {
            'server_name': 'gov-server',
            'private_ip': '10.0.1.100'
        }
        
        masked_data = mask_sensitive_data(original_data)
        
        # Original should be unchanged
        assert original_data['private_ip'] == '10.0.1.100'
        
        # Masked should be different
        assert '***' in masked_data['private_ip']
    
    def test_validate_network_policy_compliance_compliant(self):
        """Test network policy compliance for compliant VPC."""
        compliant_vpc = {
            'vpcStatus': 'RUN',
            'encryption': 'enabled',
            'networkAcl': 'enabled'
        }
        
        result = validate_network_policy_compliance(compliant_vpc)
        assert result == 'compliant'
    
    def test_validate_network_policy_compliance_needs_review(self):
        """Test network policy compliance for VPC needing review."""
        review_vpc = {
            'vpcStatus': 'INIT'
        }
        
        result = validate_network_policy_compliance(review_vpc)
        assert result == 'needs_review'
    
    def test_get_ncpgov_region_name(self):
        """Test NCP Gov region name conversion."""
        result = get_ncpgov_region_name('KR')
        assert isinstance(result, str)
        assert len(result) > 0


class TestNCPGovErrorHandling:
    """Test cases for NCP Gov error handling utilities."""
    
    def test_handle_ncpgov_api_error_decorator_success(self):
        """Test successful function execution with gov error handler."""
        @handle_ncpgov_api_error
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
    
    def test_handle_ncpgov_api_error_decorator_gov_error(self):
        """Test function with NCPGovAPIError."""
        @handle_ncpgov_api_error
        def failing_function():
            raise NCPGovAPIError("Government cloud access denied", error_code="GOV-25001")
        
        result = failing_function()
        assert result == []
    
    def test_handle_ncpgov_api_error_decorator_generic_error(self):
        """Test function with generic exception."""
        @handle_ncpgov_api_error
        def failing_function():
            raise ValueError("Generic error")
        
        result = failing_function()
        assert result == []
    
    def test_audit_log_basic(self):
        """Test basic audit logging."""
        with patch('common.ncpgov_utils.logger') as mock_logger:
            event_details = {
                'user': 'user123',
                'action': 'get_server_instances',
                'result': 'success'
            }
            
            audit_log('api_access', event_details)
            
            # Should log the audit event
            mock_logger.info.assert_called_once()


class TestNCPGovOutputFormatting:
    """Test cases for NCP Gov output formatting utilities."""
    
    def test_government_output_formatter_basic(self):
        """Test basic government output formatter functionality."""
        formatter = NCPGovOutputFormatter()
        
        # Test format validation
        assert formatter.validate_format('table') is True
        assert formatter.validate_format('json') is True
        assert formatter.validate_format('invalid') is False
    
    def test_government_output_formatter_secure_output(self):
        """Test secure output formatting."""
        formatter = NCPGovOutputFormatter()
        
        test_data = [
            {
                'name': 'gov-server-1',
                'status': 'running',
                'private_ip': '10.0.1.100'
            }
        ]
        
        headers = ['name', 'status', 'private_ip']
        
        # Test JSON format
        json_output = formatter.format_secure_output(test_data, 'json', headers)
        assert isinstance(json_output, str)
        
        # Test table format
        table_output = formatter.format_secure_output(test_data, 'table', headers)
        assert isinstance(table_output, str)


if __name__ == '__main__':
    pytest.main([__file__])