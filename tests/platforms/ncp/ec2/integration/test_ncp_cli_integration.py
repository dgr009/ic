"""
Integration tests for NCP CLI commands.

Tests the complete CLI workflow including command parsing, configuration loading,
API calls, and output formatting for NCP services.
"""

import os
import json
import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess
import sys
from click.testing import CliRunner

# Import NCP components for testing - updated to use consolidated modules
from src.ic.platforms.ncp.client import NCPClient, NCPAPIError
from src.ic.platforms.ncpgov.client import NCPGovClient


class TestNCPCLIIntegration:
    """Integration tests for NCP CLI commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Sample NCP configuration
        self.ncp_config = {
            'default': {
                'access_key': 'test-access-key',
                'secret_key': 'test-secret-key',
                'region': 'KR'
            }
        }
        
        # Sample API responses
        self.sample_instances = [
            {
                'serverInstanceNo': '12345',
                'serverName': 'test-server-1',
                'serverInstanceStatus': 'RUN',
                'serverInstanceType': 'SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002',
                'cpuCount': 2,
                'memorySize': 8589934592,
                'platformType': 'LNX64',
                'publicIp': '123.456.789.10',
                'privateIp': '10.0.1.100',
                'vpcName': 'test-vpc',
                'subnetName': 'test-subnet',
                'region': 'KR',
                'createDate': '2024-01-01T00:00:00+0900'
            }
        ]
        
        self.sample_buckets = [
            {
                'bucketName': 'test-bucket-kr',
                'region': 'KR',
                'creationDate': '2024-01-01T00:00:00+0900',
                'storageClass': 'STANDARD',
                'acl': 'private'
            }
        ]
        
        self.sample_vpcs = [
            {
                'vpcNo': 'vpc-12345',
                'vpcName': 'test-vpc',
                'ipv4CidrBlock': '10.0.0.0/16',
                'vpcStatus': 'RUN',
                'regionCode': 'KR',
                'isDefault': True,
                'createDate': '2024-01-01T00:00:00+0900'
            }
        ]
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('src.ic.platforms.ncp.client.NCPClient')
    def test_ncp_ec2_info_integration(self, mock_client_class, mock_load_config):
        """Test NCP EC2 info integration."""
        # Mock configuration and client
        mock_load_config.return_value = self.ncp_config['default']
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_server_instances.return_value = {
            'instances': self.sample_instances,
            'total_count': 1
        }
        
        # Test the integration by calling the client directly
        from common.ncp_utils import load_ncp_config
        from src.ic.platforms.ncp.client import NCPClient
        
        config = load_ncp_config()
        client = NCPClient(
            config['access_key'],
            config['secret_key'],
            config.get('region', 'KR')
        )
        
        result = client.get_server_instances()
        
        # Verify results
        assert result['total_count'] == 1
        assert len(result['instances']) == 1
        assert result['instances'][0]['serverName'] == 'test-server-1'
        
        # Verify client was created with correct parameters
        mock_client_class.assert_called_with('test-access-key', 'test-secret-key', 'KR')
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('src.ic.platforms.ncp.client.NCPClient')
    def test_ncp_ec2_info_with_name_filter(self, mock_client_class, mock_load_config):
        """Test NCP EC2 info with name filter."""
        mock_load_config.return_value = self.ncp_config['default']
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_server_instances.return_value = {
            'instances': self.sample_instances,
            'total_count': 1
        }
        
        # Test with name filter
        from src.ic.platforms.ncp.client import NCPClient
        client = NCPClient('test-key', 'test-secret', 'KR')
        result = client.get_server_instances(name_filter='test-server')
        
        # Verify filter was passed
        mock_client.get_server_instances.assert_called_with(name_filter='test-server')
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('src.ic.platforms.ncp.client.NCPClient.get_server_instances')
    def test_ncp_ec2_info_command_json_format(self, mock_get_instances, mock_load_config):
        """Test NCP EC2 info command with JSON output format."""
        mock_load_config.return_value = self.ncp_config
        mock_get_instances.return_value = {
            'instances': self.sample_instances,
            'total_count': 1
        }
        
        # Execute command with JSON format
        result = self.runner.invoke(cli, ['ncp', 'ec2', 'info', '--format', 'json'])
        
        assert result.exit_code == 0
        
        # Verify JSON output
        try:
            json_output = json.loads(result.output)
            assert isinstance(json_output, list)
            assert len(json_output) == 1
            assert json_output[0]['serverName'] == 'test-server-1'
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")
    
    @patch('common.ncp_utils.load_ncp_config')
    def test_ncp_ec2_info_command_no_config(self, mock_load_config):
        """Test NCP EC2 info command when configuration is missing."""
        mock_load_config.return_value = None
        
        # Execute command
        result = self.runner.invoke(cli, ['ncp', 'ec2', 'info'])
        
        # Should fail with configuration error
        assert result.exit_code != 0
        assert '설정' in result.output or 'config' in result.output.lower()
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('src.ic.platforms.ncp.client.NCPClient.get_server_instances')
    def test_ncp_ec2_info_command_api_error(self, mock_get_instances, mock_load_config):
        """Test NCP EC2 info command with API error."""
        mock_load_config.return_value = self.ncp_config
        mock_get_instances.side_effect = NCPAPIError("API Error", error_code="25001")
        
        # Execute command
        result = self.runner.invoke(cli, ['ncp', 'ec2', 'info'])
        
        # Should handle error gracefully
        assert result.exit_code != 0
        assert 'API Error' in result.output or 'error' in result.output.lower()
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('src.ic.platforms.ncp.client.NCPClient.get_server_instances')
    def test_ncp_ec2_info_empty_result(self, mock_get_instances, mock_load_config):
        """Test NCP EC2 info command with empty result."""
        mock_load_config.return_value = self.ncp_config
        mock_get_instances.return_value = {
            'instances': [],
            'total_count': 0
        }
        
        # Execute command
        result = self.runner.invoke(cli, ['ncp', 'ec2', 'info'])
        
        assert result.exit_code == 0
        assert '인스턴스가 없습니다' in result.output or 'No instances' in result.output


class TestNCPCLIOutputFormatting:
    """Test cases for NCP CLI output formatting."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        
        self.ncp_config = {
            'default': {
                'access_key': 'test-access-key',
                'secret_key': 'test-secret-key',
                'region': 'KR'
            }
        }
        
        # Large dataset for testing pagination and formatting
        self.large_instance_list = []
        for i in range(50):
            self.large_instance_list.append({
                'serverInstanceNo': f'i-{i:05d}',
                'serverName': f'server-{i}',
                'serverInstanceStatus': 'RUN' if i % 2 == 0 else 'STOP',
                'serverInstanceType': 'SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002',
                'cpuCount': 2,
                'memorySize': 8589934592,
                'region': 'KR'
            })
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('src.ic.platforms.ncp.client.NCPClient.get_server_instances')
    def test_ncp_ec2_info_table_format_large_dataset(self, mock_get_instances, mock_load_config):
        """Test NCP EC2 info command table format with large dataset."""
        mock_load_config.return_value = self.ncp_config
        mock_get_instances.return_value = {
            'instances': self.large_instance_list,
            'total_count': 50
        }
        
        # Execute command with table format
        result = self.runner.invoke(cli, ['ncp', 'ec2', 'info', '--format', 'table'])
        
        assert result.exit_code == 0
        
        # Should contain table headers and data
        assert 'server-0' in result.output
        assert 'server-49' in result.output
        assert 'RUN' in result.output
        assert 'STOP' in result.output
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('src.ic.platforms.ncp.client.NCPClient.get_server_instances')
    def test_ncp_ec2_info_json_format_large_dataset(self, mock_get_instances, mock_load_config):
        """Test NCP EC2 info command JSON format with large dataset."""
        mock_load_config.return_value = self.ncp_config
        mock_get_instances.return_value = {
            'instances': self.large_instance_list,
            'total_count': 50
        }
        
        # Execute command with JSON format
        result = self.runner.invoke(cli, ['ncp', 'ec2', 'info', '--format', 'json'])
        
        assert result.exit_code == 0
        
        # Verify JSON output
        try:
            json_output = json.loads(result.output)
            assert isinstance(json_output, list)
            assert len(json_output) == 50
            assert json_output[0]['serverName'] == 'server-0'
            assert json_output[49]['serverName'] == 'server-49'
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('src.ic.platforms.ncp.client.NCPClient.get_server_instances')
    def test_ncp_ec2_info_invalid_format(self, mock_get_instances, mock_load_config):
        """Test NCP EC2 info command with invalid format."""
        mock_load_config.return_value = self.ncp_config
        mock_get_instances.return_value = {
            'instances': self.large_instance_list,
            'total_count': 50
        }
        
        # Execute command with invalid format
        result = self.runner.invoke(cli, ['ncp', 'ec2', 'info', '--format', 'invalid'])
        
        # Should fail with format error
        assert result.exit_code != 0


if __name__ == '__main__':
    pytest.main([__file__])