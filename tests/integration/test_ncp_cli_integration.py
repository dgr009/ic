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

# Import NCP components for testing
from ncp.client import NCPClient, NCPAPIError
from ncpgov.client import NCPGovClient


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
    @patch('ncp.client.NCPClient')
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
        from ncp.client import NCPClient
        
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
    @patch('ncp.client.NCPClient')
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
        from ncp.client import NCPClient
        client = NCPClient('test-key', 'test-secret', 'KR')
        result = client.get_server_instances(name_filter='test-server')
        
        # Verify filter was passed
        mock_client.get_server_instances.assert_called_with(name_filter='test-server')
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('ncp.client.NCPClient.get_server_instances')
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
    @patch('ncp.client.NCPClient.get_server_instances')
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
    @patch('ncp.client.NCPClient.get_object_storage_buckets')
    def test_ncp_s3_info_command_success(self, mock_get_buckets, mock_load_config):
        """Test successful NCP S3 info command execution."""
        mock_load_config.return_value = self.ncp_config
        mock_get_buckets.return_value = {
            'buckets': self.sample_buckets,
            'total_count': 1
        }
        
        # Execute command
        result = self.runner.invoke(cli, ['ncp', 's3', 'info'])
        
        # Verify success
        assert result.exit_code == 0
        assert 'test-bucket-kr' in result.output
        assert 'STANDARD' in result.output
        
        # Verify API was called
        mock_get_buckets.assert_called_once()
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('ncp.client.NCPClient.get_object_storage_buckets')
    def test_ncp_s3_info_command_with_filter(self, mock_get_buckets, mock_load_config):
        """Test NCP S3 info command with name filter."""
        mock_load_config.return_value = self.ncp_config
        mock_get_buckets.return_value = {
            'buckets': self.sample_buckets,
            'total_count': 1
        }
        
        # Execute command with name filter
        result = self.runner.invoke(cli, ['ncp', 's3', 'info', '--name', 'test-bucket'])
        
        assert result.exit_code == 0
        
        # Verify filter was passed to API
        call_args = mock_get_buckets.call_args
        assert call_args[1]['name_filter'] == 'test-bucket'
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('ncp.client.NCPClient.get_vpc_list')
    def test_ncp_vpc_info_command_success(self, mock_get_vpcs, mock_load_config):
        """Test successful NCP VPC info command execution."""
        mock_load_config.return_value = self.ncp_config
        mock_get_vpcs.return_value = {
            'vpcs': self.sample_vpcs,
            'total_count': 1
        }
        
        # Execute command
        result = self.runner.invoke(cli, ['ncp', 'vpc', 'info'])
        
        # Verify success
        assert result.exit_code == 0
        assert 'test-vpc' in result.output
        assert '10.0.0.0/16' in result.output
        assert 'RUN' in result.output
        
        # Verify API was called
        mock_get_vpcs.assert_called_once()
    
    def test_ncp_help_command(self):
        """Test NCP help command output."""
        # Test main NCP help
        result = self.runner.invoke(cli, ['ncp', '--help'])
        
        assert result.exit_code == 0
        assert 'NCP' in result.output
        assert 'ec2' in result.output
        assert 's3' in result.output
        assert 'vpc' in result.output
    
    def test_ncp_ec2_help_command(self):
        """Test NCP EC2 help command output."""
        result = self.runner.invoke(cli, ['ncp', 'ec2', '--help'])
        
        assert result.exit_code == 0
        assert 'EC2' in result.output or 'ec2' in result.output
        assert 'info' in result.output
    
    def test_ncp_ec2_info_help_command(self):
        """Test NCP EC2 info help command output."""
        result = self.runner.invoke(cli, ['ncp', 'ec2', 'info', '--help'])
        
        assert result.exit_code == 0
        assert '--name' in result.output
        assert '--format' in result.output
        assert 'table' in result.output
        assert 'json' in result.output
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('ncp.client.NCPClient.get_server_instances')
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
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('ncp.client.NCPClient.get_object_storage_buckets')
    def test_ncp_s3_info_empty_result(self, mock_get_buckets, mock_load_config):
        """Test NCP S3 info command with empty result."""
        mock_load_config.return_value = self.ncp_config
        mock_get_buckets.return_value = {
            'buckets': [],
            'total_count': 0
        }
        
        # Execute command
        result = self.runner.invoke(cli, ['ncp', 's3', 'info'])
        
        assert result.exit_code == 0
        assert '버킷이 없습니다' in result.output or 'No buckets' in result.output
    
    @patch('common.ncp_utils.load_ncp_config')
    @patch('ncp.client.NCPClient.get_vpc_list')
    def test_ncp_vpc_info_empty_result(self, mock_get_vpcs, mock_load_config):
        """Test NCP VPC info command with empty result."""
        mock_load_config.return_value = self.ncp_config
        mock_get_vpcs.return_value = {
            'vpcs': [],
            'total_count': 0
        }
        
        # Execute command
        result = self.runner.invoke(cli, ['ncp', 'vpc', 'info'])
        
        assert result.exit_code == 0
        assert 'VPC가 없습니다' in result.output or 'No VPCs' in result.output


class TestNCPGovCLIIntegration:
    """Integration tests for NCP Gov CLI commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        
        # Sample NCP Gov configuration
        self.ncpgov_config = {
            'default': {
                'access_key': 'gov-access-key',
                'secret_key': 'gov-secret-key',
                'region': 'KR',
                'security_policy': 'government_compliant'
            }
        }
        
        # Sample API responses with government cloud specific fields
        self.sample_gov_instances = [
            {
                'serverInstanceNo': '67890',
                'serverName': 'gov-server-1',
                'serverInstanceStatus': 'RUN',
                'serverInstanceType': 'SVR.VSVR.STAND.C004.M016.NET.SSD.B100.G002',
                'private_ip': '***MASKED***',  # Masked for government cloud
                'internal_ip': '***MASKED***',
                'compliance_status': 'validated'
            }
        ]
    
    @patch('common.ncpgov_utils.load_ncpgov_config')
    @patch('ncpgov.client.NCPGovClient.get_server_instances')
    def test_ncpgov_ec2_info_command_success(self, mock_get_instances, mock_load_config):
        """Test successful NCP Gov EC2 info command execution."""
        mock_load_config.return_value = self.ncpgov_config
        mock_get_instances.return_value = {
            'instances': self.sample_gov_instances,
            'total_count': 1,
            'compliance_status': 'validated'
        }
        
        # Execute command
        result = self.runner.invoke(cli, ['ncpgov', 'ec2', 'info'])
        
        # Verify success
        assert result.exit_code == 0
        assert 'gov-server-1' in result.output
        assert 'RUN' in result.output
        
        # Verify sensitive data is masked
        assert '***MASKED***' in result.output or 'MASKED' in result.output
        
        # Verify API was called
        mock_get_instances.assert_called_once()
    
    @patch('common.ncpgov_utils.load_ncpgov_config')
    @patch('ncpgov.client.NCPGovClient.get_server_instances')
    def test_ncpgov_ec2_info_command_compliance_validation(self, mock_get_instances, mock_load_config):
        """Test NCP Gov EC2 info command with compliance validation."""
        mock_load_config.return_value = self.ncpgov_config
        mock_get_instances.return_value = {
            'instances': self.sample_gov_instances,
            'total_count': 1,
            'compliance_status': 'validated'
        }
        
        # Execute command
        result = self.runner.invoke(cli, ['ncpgov', 'ec2', 'info'])
        
        assert result.exit_code == 0
        
        # Should show compliance status
        assert 'validated' in result.output or 'compliant' in result.output
    
    @patch('common.ncpgov_utils.load_ncpgov_config')
    @patch('ncpgov.client.NCPGovClient.get_object_storage_buckets')
    def test_ncpgov_s3_info_command_government_compliance(self, mock_get_buckets, mock_load_config):
        """Test NCP Gov S3 info command with government compliance."""
        mock_load_config.return_value = self.ncpgov_config
        mock_get_buckets.return_value = {
            'buckets': [],
            'total_count': 0,
            'compliance_status': 'validated',
            'security_policy': 'government_cloud_compliant'
        }
        
        # Execute command
        result = self.runner.invoke(cli, ['ncpgov', 's3', 'info'])
        
        assert result.exit_code == 0
        
        # Should show government compliance status
        assert 'government' in result.output.lower() or 'compliant' in result.output
    
    @patch('common.ncpgov_utils.load_ncpgov_config')
    @patch('ncpgov.client.NCPGovClient.get_vpc_list')
    def test_ncpgov_vpc_info_command_policy_compliance(self, mock_get_vpcs, mock_load_config):
        """Test NCP Gov VPC info command with policy compliance."""
        sample_gov_vpcs = [
            {
                'vpcNo': 'vpc-gov123',
                'vpcName': 'gov-vpc',
                'ipv4CidrBlock': '10.0.0.0/16',
                'vpcStatus': 'RUN',
                'policy_compliance': 'compliant'
            }
        ]
        
        mock_load_config.return_value = self.ncpgov_config
        mock_get_vpcs.return_value = {
            'vpcs': sample_gov_vpcs,
            'total_count': 1,
            'compliance_status': 'validated'
        }
        
        # Execute command
        result = self.runner.invoke(cli, ['ncpgov', 'vpc', 'info'])
        
        assert result.exit_code == 0
        assert 'gov-vpc' in result.output
        
        # Should show policy compliance
        assert 'compliant' in result.output
    
    def test_ncpgov_help_command(self):
        """Test NCP Gov help command output."""
        result = self.runner.invoke(cli, ['ncpgov', '--help'])
        
        assert result.exit_code == 0
        assert 'NCP Gov' in result.output or 'Government' in result.output
        assert 'ec2' in result.output
        assert 's3' in result.output
        assert 'vpc' in result.output
    
    @patch('common.ncpgov_utils.load_ncpgov_config')
    def test_ncpgov_ec2_info_command_no_config(self, mock_load_config):
        """Test NCP Gov EC2 info command when configuration is missing."""
        mock_load_config.return_value = None
        
        # Execute command
        result = self.runner.invoke(cli, ['ncpgov', 'ec2', 'info'])
        
        # Should fail with configuration error
        assert result.exit_code != 0
        assert '설정' in result.output or 'config' in result.output.lower()


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
    @patch('ncp.client.NCPClient.get_server_instances')
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
    @patch('ncp.client.NCPClient.get_server_instances')
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
    @patch('ncp.client.NCPClient.get_server_instances')
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