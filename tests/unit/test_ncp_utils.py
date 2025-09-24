"""
Unit tests for NCP utilities.

Tests NCP utility functions, configuration loading, error handling decorators,
and output formatting functionality.
"""

import os
import yaml
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from datetime import datetime

# Import NCP utilities
from common.ncp_utils import (
    load_ncp_config, validate_ncp_config, create_ncp_config_directory,
    handle_ncp_api_error, retry_on_network_error, show_progress_for_long_operations,
    format_bytes, format_instance_type, get_ncp_region_name, OutputFormatter
)
from ncp.client import NCPClient, NCPAPIError


class TestNCPConfigUtils:
    """Test cases for NCP configuration utilities."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_config = {
            'default': {
                'access_key': 'test-access-key',
                'secret_key': 'test-secret-key',
                'region': 'KR'
            },
            'production': {
                'access_key': 'prod-access-key',
                'secret_key': 'prod-secret-key',
                'region': 'KR'
            }
        }
    
    def test_load_ncp_config_success(self):
        """Test successful NCP config loading."""
        config_content = yaml.dump(self.sample_config)
        
        with patch('builtins.open', mock_open(read_data=config_content)):
            with patch('os.path.exists', return_value=True):
                config = load_ncp_config()
        
        assert config is not None
        assert 'default' in config
        assert config['default']['access_key'] == 'test-access-key'
        assert config['default']['region'] == 'KR'
    
    def test_load_ncp_config_file_not_found(self):
        """Test NCP config loading when file doesn't exist."""
        with patch('os.path.exists', return_value=False):
            config = load_ncp_config()
        
        assert config is None
    
    def test_load_ncp_config_invalid_yaml(self):
        """Test NCP config loading with invalid YAML."""
        invalid_yaml = "invalid: yaml: content: ["
        
        with patch('builtins.open', mock_open(read_data=invalid_yaml)):
            with patch('os.path.exists', return_value=True):
                config = load_ncp_config()
        
        assert config is None
    
    def test_load_ncp_config_custom_path(self):
        """Test NCP config loading with custom path."""
        config_content = yaml.dump(self.sample_config)
        custom_path = "/custom/path/config"
        
        with patch('builtins.open', mock_open(read_data=config_content)):
            with patch('os.path.exists', return_value=True):
                config = load_ncp_config(config_path=custom_path)
        
        assert config is not None
    
    def test_validate_ncp_config_success(self):
        """Test successful NCP config validation."""
        with patch('os.path.exists', return_value=True):
            with patch('common.ncp_utils.load_ncp_config', return_value=self.sample_config):
                result = validate_ncp_config()
        
        assert result is True
    
    def test_validate_ncp_config_file_not_found(self):
        """Test NCP config validation when file doesn't exist."""
        with patch('os.path.exists', return_value=False):
            result = validate_ncp_config()
        
        assert result is False
    
    def test_validate_ncp_config_missing_access_key(self):
        """Test NCP config validation with missing access key."""
        invalid_config = {
            'default': {
                'secret_key': 'test-secret-key',
                'region': 'KR'
            }
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('common.ncp_utils.load_ncp_config', return_value=invalid_config):
                result = validate_ncp_config()
        
        assert result is False
    
    def test_validate_ncp_config_missing_secret_key(self):
        """Test NCP config validation with missing secret key."""
        invalid_config = {
            'default': {
                'access_key': 'test-access-key',
                'region': 'KR'
            }
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('common.ncp_utils.load_ncp_config', return_value=invalid_config):
                result = validate_ncp_config()
        
        assert result is False
    
    def test_validate_ncp_config_no_default_profile(self):
        """Test NCP config validation with no default profile."""
        invalid_config = {
            'production': {
                'access_key': 'prod-access-key',
                'secret_key': 'prod-secret-key',
                'region': 'KR'
            }
        }
        
        with patch('os.path.exists', return_value=True):
            with patch('common.ncp_utils.load_ncp_config', return_value=invalid_config):
                result = validate_ncp_config()
        
        assert result is False
    
    def test_create_ncp_config_directory(self):
        """Test NCP config directory creation."""
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path('/home/test')
                
                result = create_ncp_config_directory()
                
                assert result == Path('/home/test/.ncp')
                mock_mkdir.assert_called_once_with(mode=0o700, exist_ok=True)


class TestNCPErrorHandling:
    """Test cases for NCP error handling decorators."""
    
    def test_handle_ncp_api_error_decorator_success(self):
        """Test successful function execution with error handler."""
        @handle_ncp_api_error
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
    
    def test_handle_ncp_api_error_decorator_ncp_error(self):
        """Test function with NCPAPIError."""
        @handle_ncp_api_error
        def failing_function():
            raise NCPAPIError("API Error", error_code="25001")
        
        result = failing_function()
        assert result == []
    
    def test_handle_ncp_api_error_decorator_generic_error(self):
        """Test function with generic exception."""
        @handle_ncp_api_error
        def failing_function():
            raise ValueError("Generic error")
        
        result = failing_function()
        assert result == []
    
    def test_retry_on_network_error_success(self):
        """Test successful function execution with retry decorator."""
        @retry_on_network_error(max_retries=3, delay=0.1)
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
    
    @patch('time.sleep')
    def test_retry_on_network_error_with_retries(self, mock_sleep):
        """Test function with network errors and retries."""
        call_count = 0
        
        @retry_on_network_error(max_retries=3, delay=0.1)
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                import requests
                raise requests.exceptions.ConnectionError("Network error")
            return "success"
        
        result = failing_then_success()
        assert result == "success"
        assert call_count == 3
        assert mock_sleep.call_count == 2  # 2 retries before success
    
    @patch('time.sleep')
    def test_retry_on_network_error_max_retries_exceeded(self, mock_sleep):
        """Test function that fails all retries."""
        @retry_on_network_error(max_retries=2, delay=0.1)
        def always_failing():
            import requests
            raise requests.exceptions.ConnectionError("Network error")
        
        result = always_failing()
        assert result == []
        assert mock_sleep.call_count == 2  # Max retries reached
    
    def test_retry_on_network_error_non_network_error(self):
        """Test function with non-network error (should not retry)."""
        @retry_on_network_error(max_retries=3, delay=0.1)
        def non_network_error():
            raise ValueError("Not a network error")
        
        result = non_network_error()
        assert result == []
    
    @patch('time.time')
    def test_show_progress_for_long_operations_short(self, mock_time):
        """Test progress decorator for short operations."""
        mock_time.side_effect = [0, 2]  # 2 second operation
        
        @show_progress_for_long_operations
        def short_operation():
            return "quick"
        
        result = short_operation()
        assert result == "quick"
    
    @patch('time.time')
    def test_show_progress_for_long_operations_long(self, mock_time):
        """Test progress decorator for long operations."""
        mock_time.side_effect = [0, 8]  # 8 second operation
        
        @show_progress_for_long_operations
        def long_operation():
            return "slow"
        
        result = long_operation()
        assert result == "slow"


class TestNCPFormatUtils:
    """Test cases for NCP formatting utilities."""
    
    def test_format_bytes_basic(self):
        """Test bytes formatting for basic values."""
        assert format_bytes(512) == "512 B"
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1048576) == "1.0 MB"
        assert format_bytes(1073741824) == "1.0 GB"
    
    def test_format_bytes_zero(self):
        """Test bytes formatting for zero."""
        assert format_bytes(0) == "0 B"
    
    def test_format_bytes_negative(self):
        """Test bytes formatting for negative values."""
        # Should handle gracefully
        result = format_bytes(-1024)
        assert isinstance(result, str)
    
    def test_format_instance_type_basic(self):
        """Test instance type formatting."""
        instance_type = "SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002"
        result = format_instance_type(instance_type)
        
        # Should return a formatted string
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_format_instance_type_invalid(self):
        """Test instance type formatting with invalid input."""
        result = format_instance_type("invalid-type")
        assert isinstance(result, str)
    
    def test_get_ncp_region_name_kr(self):
        """Test NCP region name for KR."""
        result = get_ncp_region_name("KR")
        assert "Korea" in result or "한국" in result
    
    def test_get_ncp_region_name_us(self):
        """Test NCP region name for US."""
        result = get_ncp_region_name("US")
        assert "US" in result or "United States" in result
    
    def test_get_ncp_region_name_unknown(self):
        """Test NCP region name for unknown region."""
        result = get_ncp_region_name("UNKNOWN")
        assert isinstance(result, str)


class TestNCPOutputFormatter:
    """Test cases for NCP output formatting."""
    
    def setup_method(self):
        """Set up test fixtures."""
        from common.ncp_utils import OutputFormatter
        self.formatter = OutputFormatter()
        
        self.sample_data = [
            {
                'name': 'server-1',
                'status': 'RUN',
                'type': 'SVR.VSVR.STAND.C002.M008'
            },
            {
                'name': 'server-2',
                'status': 'STOP',
                'type': 'SVR.VSVR.STAND.C004.M016'
            }
        ]
        
        self.headers = ['name', 'status', 'type']
    
    def test_format_output_json(self):
        """Test JSON output formatting."""
        result = self.formatter.format_output(self.sample_data, 'json', self.headers)
        
        import json
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]['name'] == 'server-1'
        assert parsed[1]['status'] == 'STOP'
    
    def test_format_output_table(self):
        """Test table output formatting."""
        result = self.formatter.format_output(self.sample_data, 'table', self.headers)
        
        # Should contain table structure
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain data
        assert 'server-1' in result
        assert 'server-2' in result
    
    def test_format_output_invalid_format(self):
        """Test output formatting with invalid format."""
        with pytest.raises(ValueError) as exc_info:
            self.formatter.format_output(self.sample_data, 'invalid', self.headers)
        
        assert '지원하지 않는 출력 형식' in str(exc_info.value)
    
    def test_format_output_empty_data(self):
        """Test output formatting with empty data."""
        result = self.formatter.format_output([], 'json', self.headers)
        
        import json
        parsed = json.loads(result)
        assert parsed == []
    
    def test_format_table_with_korean_text(self):
        """Test table formatting with Korean text."""
        korean_data = [
            {
                'name': '서버-1',
                'status': '실행중',
                'region': '한국'
            }
        ]
        headers = ['name', 'status', 'region']
        
        result = self.formatter.format_output(korean_data, 'table', headers)
        
        assert '서버-1' in result
        assert '실행중' in result
        assert '한국' in result


if __name__ == '__main__':
    pytest.main([__file__])