"""
Unit tests for NCP EC2 Service.

Tests NCP EC2 service functionality, data models, and output formatting.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import List, Dict, Any

# Import NCP EC2 service classes - updated to use consolidated modules
from src.ic.platforms.ncp.ec2.info import NCPInstance, fetch_ncp_ec2_info, print_ncp_ec2_table, format_memory_size, format_instance_type
from src.ic.platforms.ncp.client import NCPClient, NCPAPIError


class TestNCPInstanceDataModel:
    """Test cases for NCPInstance data model."""
    
    def test_ncp_instance_creation(self):
        """Test NCPInstance creation with all fields."""
        instance = NCPInstance(
            server_instance_no="i-12345",
            server_name="test-server",
            server_instance_status="RUN",
            server_instance_type="SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002",
            cpu_count=2,
            memory_size=8589934592,  # 8GB in bytes
            platform_type="LNX64",
            public_ip="123.456.789.10",
            private_ip="10.0.1.100",
            vpc_name="test-vpc",
            subnet_name="test-subnet",
            region="KR",
            zone="KR-1",
            create_date="2024-01-01T00:00:00+0900"
        )
        
        assert instance.server_instance_no == "i-12345"
        assert instance.server_name == "test-server"
        assert instance.server_instance_status == "RUN"
        assert instance.cpu_count == 2
        assert instance.memory_size == 8589934592
        assert instance.region == "KR"
        assert instance.zone == "KR-1"
    
    def test_ncp_instance_from_api_response(self):
        """Test NCPInstance creation from API response."""
        api_data = {
            'serverInstanceNo': 'i-67890',
            'serverName': 'api-server',
            'serverInstanceStatus': {'code': 'STOP'},
            'serverInstanceType': {'code': 'SVR.VSVR.STAND.C004.M016.NET.SSD.B100.G002'},
            'cpuCount': 4,
            'memorySize': 17179869184,  # 16GB in bytes
            'platformType': {'code': 'LNX64'},
            'publicIp': '234.567.890.11',
            'privateIp': '10.0.2.200',
            'vpcName': 'api-vpc',
            'subnetName': 'api-subnet',
            'zone': {'zoneName': 'KR-2'},
            'createDate': '2024-02-01T12:00:00+0900'
        }
        
        instance = NCPInstance.from_api_response(api_data, "KR")
        
        assert instance.server_instance_no == 'i-67890'
        assert instance.server_name == 'api-server'
        assert instance.server_instance_status == 'STOP'
        assert instance.cpu_count == 4
        assert instance.memory_size == 17179869184
        assert instance.region == "KR"
        assert instance.zone == "KR-2"
    
    def test_ncp_instance_from_api_response_missing_fields(self):
        """Test NCPInstance creation from API response with missing fields."""
        api_data = {
            'serverInstanceNo': 'i-minimal',
            'serverName': 'minimal-server'
            # Missing most fields
        }
        
        instance = NCPInstance.from_api_response(api_data, "US")
        
        assert instance.server_instance_no == 'i-minimal'
        assert instance.server_name == 'minimal-server'
        assert instance.server_instance_status == ''  # Default empty string
        assert instance.cpu_count == 0  # Default zero
        assert instance.region == "US"
        assert instance.public_ip == '-'  # Default dash
        assert instance.private_ip == '-'


class TestNCPEC2Service:
    """Test cases for NCP EC2 service functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=NCPClient)
        self.mock_client.region = "KR"
        
        self.sample_instances_data = [
            {
                'serverInstanceNo': 'i-12345',
                'serverName': 'test-server-1',
                'serverInstanceStatus': {'code': 'RUN'},
                'serverInstanceType': {'code': 'SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002'},
                'cpuCount': 2,
                'memorySize': 8589934592,
                'platformType': {'code': 'LNX64'},
                'publicIp': '123.456.789.10',
                'privateIp': '10.0.1.100',
                'vpcName': 'test-vpc',
                'subnetName': 'test-subnet',
                'zone': {'zoneName': 'KR-1'},
                'createDate': '2024-01-01T00:00:00+0900'
            },
            {
                'serverInstanceNo': 'i-67890',
                'serverName': 'test-server-2',
                'serverInstanceStatus': {'code': 'STOP'},
                'serverInstanceType': {'code': 'SVR.VSVR.STAND.C004.M016.NET.SSD.B100.G002'},
                'cpuCount': 4,
                'memorySize': 17179869184,
                'platformType': {'code': 'WIN64'},
                'publicIp': '234.567.890.11',
                'privateIp': '10.0.2.200',
                'vpcName': 'test-vpc-2',
                'subnetName': 'test-subnet-2',
                'zone': {'zoneName': 'KR-2'},
                'createDate': '2024-02-01T12:00:00+0900'
            }
        ]
    
    def test_fetch_ncp_ec2_info_success(self):
        """Test successful EC2 instance information fetching."""
        self.mock_client.get_server_instances.return_value = self.sample_instances_data
        
        result = fetch_ncp_ec2_info(self.mock_client)
        
        assert len(result) == 2
        assert isinstance(result[0], NCPInstance)
        assert result[0].server_name == 'test-server-1'
        assert result[1].server_name == 'test-server-2'
        
        self.mock_client.get_server_instances.assert_called_once()
    
    def test_fetch_ncp_ec2_info_with_name_filter(self):
        """Test EC2 instance fetching with name filter."""
        self.mock_client.get_server_instances.return_value = self.sample_instances_data
        
        result = fetch_ncp_ec2_info(self.mock_client, name_filter="server-1")
        
        assert len(result) == 1
        assert result[0].server_name == 'test-server-1'
    
    def test_fetch_ncp_ec2_info_empty_result(self):
        """Test EC2 instance fetching with empty result."""
        self.mock_client.get_server_instances.return_value = []
        
        result = fetch_ncp_ec2_info(self.mock_client)
        
        assert len(result) == 0
    
    def test_fetch_ncp_ec2_info_api_error(self):
        """Test EC2 instance fetching with API error."""
        self.mock_client.get_server_instances.side_effect = NCPAPIError("API Error")
        
        result = fetch_ncp_ec2_info(self.mock_client)
        
        assert len(result) == 0  # Error handler should return empty list
    
    def test_fetch_ncp_ec2_info_parsing_error(self):
        """Test EC2 instance fetching with data parsing error."""
        # Invalid data that will cause parsing error
        invalid_data = [
            {
                'serverInstanceNo': 'i-invalid',
                # Missing required fields that will cause parsing issues
            }
        ]
        self.mock_client.get_server_instances.return_value = invalid_data
        
        result = fetch_ncp_ec2_info(self.mock_client)
        
        # Should handle parsing errors gracefully and continue with valid data
        assert isinstance(result, list)
    
    def test_format_memory_size(self):
        """Test memory size formatting."""
        # Test bytes to MB
        assert format_memory_size(536870912) == "512MB"  # 512MB
        
        # Test bytes to GB
        assert format_memory_size(1073741824) == "1.0GB"  # 1GB
        assert format_memory_size(8589934592) == "8.0GB"  # 8GB
        assert format_memory_size(17179869184) == "16.0GB"  # 16GB
        
        # Test zero
        assert format_memory_size(0) == "-"
        
        # Test small values
        assert format_memory_size(1048576) == "1MB"  # 1MB
    
    def test_format_instance_type(self):
        """Test instance type formatting."""
        # Test standard NCP instance type
        instance_type = "SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002"
        result = format_instance_type(instance_type)
        assert "C002M008" in result or "C2M8" in result
        
        # Test another instance type
        instance_type2 = "SVR.VSVR.STAND.C004.M016.NET.SSD.B100.G002"
        result2 = format_instance_type(instance_type2)
        assert "C004M016" in result2 or "C4M16" in result2
        
        # Test empty or invalid type
        assert format_instance_type("") == "-"
        assert format_instance_type("-") == "-"
        assert format_instance_type("invalid-type") == "invalid-type"
    
    @patch('src.ic.platforms.ncp.ec2.info.console')
    def test_print_ncp_ec2_table_empty(self, mock_console):
        """Test EC2 table printing with empty data."""
        print_ncp_ec2_table([])
        
        mock_console.print.assert_called_with("(No Instances)")
    
    @patch('src.ic.platforms.ncp.ec2.info.console')
    def test_print_ncp_ec2_table_with_data(self, mock_console):
        """Test EC2 table printing with data."""
        instances = [
            NCPInstance(
                server_instance_no="i-12345",
                server_name="test-server",
                server_instance_status="RUN",
                server_instance_type="SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002",
                cpu_count=2,
                memory_size=8589934592,
                platform_type="LNX64",
                public_ip="123.456.789.10",
                private_ip="10.0.1.100",
                vpc_name="test-vpc",
                subnet_name="test-subnet",
                region="KR",
                zone="KR-1",
                create_date="2024-01-01T00:00:00+0900"
            )
        ]
        
        print_ncp_ec2_table(instances, verbose=False)
        
        # Should call console.print multiple times (header + table)
        assert mock_console.print.call_count >= 2
    
    @patch('src.ic.platforms.ncp.ec2.info.console')
    def test_print_ncp_ec2_table_verbose(self, mock_console):
        """Test EC2 table printing in verbose mode."""
        instances = [
            NCPInstance(
                server_instance_no="i-12345",
                server_name="test-server",
                server_instance_status="RUN",
                server_instance_type="SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002",
                cpu_count=2,
                memory_size=8589934592,
                platform_type="LNX64",
                public_ip="123.456.789.10",
                private_ip="10.0.1.100",
                vpc_name="test-vpc",
                subnet_name="test-subnet",
                region="KR",
                zone="KR-1",
                create_date="2024-01-01T00:00:00+0900"
            )
        ]
        
        print_ncp_ec2_table(instances, verbose=True)
        
        # Should call console.print multiple times (header + table)
        assert mock_console.print.call_count >= 2


class TestNCPEC2ServiceIntegration:
    """Integration tests for NCP EC2 service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=NCPClient)
        self.mock_client.region = "KR"
        self.mock_client.platform = "VPC"
    
    @patch('src.ic.platforms.ncp.ec2.info.load_ncp_config')
    @patch('src.ic.platforms.ncp.ec2.info.NCPClient')
    def test_ec2_service_integration(self, mock_client_class, mock_load_config):
        """Test EC2 service integration with configuration loading."""
        # Mock configuration
        mock_config = {
            'access_key': 'test-key',
            'secret_key': 'test-secret',
            'region': 'KR',
            'platform': 'VPC'
        }
        mock_load_config.return_value = mock_config
        
        # Mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_server_instances.return_value = []
        
        # Test the integration
        result = fetch_ncp_ec2_info(mock_client)
        
        assert isinstance(result, list)
        mock_client.get_server_instances.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])