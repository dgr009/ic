"""
Unit tests for NCP mock data generation and API response handling.

Tests mock data generation, API response parsing, data validation,
and edge cases for NCP services.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Import NCP components
from ncp.client import NCPClient, NCPAPIError
from ncpgov.client import NCPGovClient


class TestNCPMockDataGeneration:
    """Test cases for NCP mock data generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = NCPClient("test-key", "test-secret", "KR")
        self.gov_client = NCPGovClient("gov-key", "gov-secret", "KR")
    
    def test_generate_mock_bucket_data_structure(self):
        """Test mock bucket data structure and content."""
        buckets = self.client._generate_mock_bucket_data()
        
        # Verify basic structure
        assert isinstance(buckets, list)
        assert len(buckets) > 0
        
        # Verify each bucket has required fields
        for bucket in buckets:
            assert 'bucketName' in bucket
            assert 'region' in bucket
            assert 'creationDate' in bucket
            assert 'storageClass' in bucket
            assert 'acl' in bucket
            assert 'versioning' in bucket
            assert 'encryption' in bucket
            
            # Verify data types
            assert isinstance(bucket['bucketName'], str)
            assert isinstance(bucket['region'], str)
            assert isinstance(bucket['creationDate'], str)
            assert isinstance(bucket['storageClass'], str)
            assert isinstance(bucket['acl'], str)
            assert isinstance(bucket['versioning'], str)
            assert isinstance(bucket['encryption'], str)
    
    def test_generate_mock_bucket_data_region_consistency(self):
        """Test that mock bucket data respects region settings."""
        # Test different regions
        regions = ['KR', 'US', 'JP']
        
        for region in regions:
            client = NCPClient("test-key", "test-secret", region)
            buckets = client._generate_mock_bucket_data()
            
            for bucket in buckets:
                assert bucket['region'] == region
                assert region.lower() in bucket['bucketName']
    
    def test_generate_mock_bucket_data_valid_values(self):
        """Test that mock bucket data contains valid values."""
        buckets = self.client._generate_mock_bucket_data()
        
        valid_storage_classes = ['STANDARD', 'STANDARD_IA', 'COLD', 'ARCHIVE']
        valid_acl_types = ['private', 'public-read', 'authenticated-read']
        valid_versioning_states = ['Enabled', 'Disabled', 'Suspended']
        valid_encryption_types = ['None', 'AES256', 'KMS']
        
        for bucket in buckets:
            assert bucket['storageClass'] in valid_storage_classes
            assert bucket['acl'] in valid_acl_types
            assert bucket['versioning'] in valid_versioning_states
            assert bucket['encryption'] in valid_encryption_types
    
    def test_generate_mock_bucket_data_date_format(self):
        """Test that mock bucket data has valid date formats."""
        buckets = self.client._generate_mock_bucket_data()
        
        for bucket in buckets:
            creation_date = bucket['creationDate']
            
            # Should be in ISO format with timezone
            assert '+0900' in creation_date or 'T' in creation_date
            
            # Should be parseable as datetime
            try:
                # Remove timezone for parsing
                date_part = creation_date.replace('+0900', '')
                datetime.strptime(date_part, '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                pytest.fail(f"Invalid date format: {creation_date}")
    
    def test_generate_mock_vpc_data_structure(self):
        """Test mock VPC data structure and content."""
        vpcs = self.client._generate_mock_vpc_data()
        
        # Verify basic structure
        assert isinstance(vpcs, list)
        assert len(vpcs) > 0
        
        # Verify each VPC has required fields
        for vpc in vpcs:
            assert 'vpcNo' in vpc
            assert 'vpcName' in vpc
            assert 'ipv4CidrBlock' in vpc
            assert 'vpcStatus' in vpc
            assert 'regionCode' in vpc
            assert 'isDefault' in vpc
            assert 'createDate' in vpc
            
            # Verify data types
            assert isinstance(vpc['vpcNo'], str)
            assert isinstance(vpc['vpcName'], str)
            assert isinstance(vpc['ipv4CidrBlock'], str)
            assert isinstance(vpc['vpcStatus'], str)
            assert isinstance(vpc['regionCode'], str)
            assert isinstance(vpc['isDefault'], bool)
            assert isinstance(vpc['createDate'], str)
    
    def test_generate_mock_vpc_data_valid_cidr_blocks(self):
        """Test that mock VPC data contains valid CIDR blocks."""
        vpcs = self.client._generate_mock_vpc_data()
        
        valid_cidr_patterns = [
            '10.0.0.0/16', '10.1.0.0/16', '10.2.0.0/16',
            '172.16.0.0/16'
        ]
        
        for vpc in vpcs:
            cidr = vpc['ipv4CidrBlock']
            assert cidr in valid_cidr_patterns
            
            # Verify CIDR format
            assert '/' in cidr
            ip_part, mask_part = cidr.split('/')
            assert '.' in ip_part
            assert mask_part.isdigit()
            assert 0 <= int(mask_part) <= 32
    
    def test_generate_mock_vpc_data_unique_ids(self):
        """Test that mock VPC data generates unique IDs."""
        vpcs = self.client._generate_mock_vpc_data()
        
        vpc_ids = [vpc['vpcNo'] for vpc in vpcs]
        vpc_names = [vpc['vpcName'] for vpc in vpcs]
        
        # IDs should be unique
        assert len(vpc_ids) == len(set(vpc_ids))
        assert len(vpc_names) == len(set(vpc_names))
    
    def test_generate_mock_vpc_data_default_vpc(self):
        """Test that mock VPC data has exactly one default VPC."""
        vpcs = self.client._generate_mock_vpc_data()
        
        default_vpcs = [vpc for vpc in vpcs if vpc['isDefault']]
        assert len(default_vpcs) == 1
        
        # Default VPC should be the first one
        assert vpcs[0]['isDefault'] is True
    
    def test_mock_data_consistency_across_calls(self):
        """Test that mock data is consistent across multiple calls."""
        # Generate data multiple times
        buckets1 = self.client._generate_mock_bucket_data()
        buckets2 = self.client._generate_mock_bucket_data()
        
        vpcs1 = self.client._generate_mock_vpc_data()
        vpcs2 = self.client._generate_mock_vpc_data()
        
        # Should generate same structure but potentially different content
        assert len(buckets1) == len(buckets2)
        assert len(vpcs1) == len(vpcs2)
        
        # Bucket names should be consistent (based on region)
        bucket_names1 = [b['bucketName'] for b in buckets1]
        bucket_names2 = [b['bucketName'] for b in buckets2]
        assert bucket_names1 == bucket_names2
        
        # VPC names should be consistent (based on region)
        vpc_names1 = [v['vpcName'] for v in vpcs1]
        vpc_names2 = [v['vpcName'] for v in vpcs2]
        assert vpc_names1 == vpc_names2


class TestNCPAPIResponseHandling:
    """Test cases for NCP API response handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = NCPClient("test-key", "test-secret", "KR")
    
    def test_parse_server_instance_response_success(self):
        """Test parsing successful server instance API response."""
        mock_response = {
            'getServerInstanceListResponse': {
                'serverInstanceList': [
                    {
                        'serverInstanceNo': '12345',
                        'serverName': 'test-server',
                        'serverInstanceStatus': 'RUN',
                        'serverInstanceType': 'SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002',
                        'cpuCount': 2,
                        'memorySize': 8589934592,
                        'platformType': 'LNX64',
                        'publicIp': '123.456.789.10',
                        'privateIp': '10.0.1.100'
                    }
                ],
                'totalRows': 1
            }
        }
        
        with patch.object(self.client, '_make_request', return_value=mock_response):
            result = self.client.get_server_instances()
        
        assert result['total_count'] == 1
        assert len(result['instances']) == 1
        
        instance = result['instances'][0]
        assert instance['serverInstanceNo'] == '12345'
        assert instance['serverName'] == 'test-server'
        assert instance['serverInstanceStatus'] == 'RUN'
        assert instance['cpuCount'] == 2
    
    def test_parse_server_instance_response_empty(self):
        """Test parsing empty server instance API response."""
        mock_response = {
            'getServerInstanceListResponse': {
                'serverInstanceList': [],
                'totalRows': 0
            }
        }
        
        with patch.object(self.client, '_make_request', return_value=mock_response):
            result = self.client.get_server_instances()
        
        assert result['total_count'] == 0
        assert len(result['instances']) == 0
    
    def test_parse_server_instance_response_malformed(self):
        """Test parsing malformed server instance API response."""
        # Missing required response structure
        mock_response = {
            'unexpectedResponse': {
                'data': []
            }
        }
        
        with patch.object(self.client, '_make_request', return_value=mock_response):
            result = self.client.get_server_instances()
        
        # Should handle gracefully and return empty result
        assert result['total_count'] == 0
        assert len(result['instances']) == 0
    
    def test_parse_server_instance_response_partial_data(self):
        """Test parsing server instance response with partial data."""
        mock_response = {
            'getServerInstanceListResponse': {
                'serverInstanceList': [
                    {
                        'serverInstanceNo': '12345',
                        'serverName': 'test-server',
                        'serverInstanceStatus': 'RUN'
                        # Missing other fields
                    }
                ],
                'totalRows': 1
            }
        }
        
        with patch.object(self.client, '_make_request', return_value=mock_response):
            result = self.client.get_server_instances()
        
        assert result['total_count'] == 1
        assert len(result['instances']) == 1
        
        instance = result['instances'][0]
        assert instance['serverInstanceNo'] == '12345'
        assert instance['serverName'] == 'test-server'
        # Should handle missing fields gracefully
    
    def test_api_error_response_handling(self):
        """Test handling of API error responses."""
        error_response = {
            'responseError': {
                'returnCode': '25001',
                'returnMessage': 'Invalid parameter: serverName'
            }
        }
        
        with patch('requests.Session.request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = error_response
            mock_request.return_value = mock_response
            
            with pytest.raises(NCPAPIError) as exc_info:
                self.client._make_request('GET', '/getServerInstanceList')
            
            assert exc_info.value.error_code == '25001'
            assert 'Invalid parameter' in exc_info.value.message
            assert exc_info.value.status_code == 400
    
    def test_api_network_error_handling(self):
        """Test handling of network errors."""
        import requests
        
        with patch('requests.Session.request') as mock_request:
            mock_request.side_effect = requests.exceptions.ConnectionError("Network unreachable")
            
            with pytest.raises(NCPAPIError) as exc_info:
                self.client._make_request('GET', '/getServerInstanceList')
            
            assert '네트워크 오류' in exc_info.value.message
    
    def test_api_timeout_handling(self):
        """Test handling of request timeouts."""
        import requests
        
        with patch('requests.Session.request') as mock_request:
            mock_request.side_effect = requests.exceptions.Timeout("Request timeout")
            
            with pytest.raises(NCPAPIError) as exc_info:
                self.client._make_request('GET', '/getServerInstanceList', timeout=5.0)
            
            assert '네트워크 오류' in exc_info.value.message


class TestNCPGovMockDataHandling:
    """Test cases for NCP Gov mock data and response handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.gov_client = NCPGovClient("gov-key", "gov-secret", "KR")
    
    @patch.object(NCPGovClient, '_make_request')
    def test_government_cloud_response_masking(self, mock_make_request):
        """Test that government cloud responses are properly masked."""
        mock_response = {
            'getServerInstanceListResponse': {
                'serverInstanceList': [
                    {
                        'serverInstanceNo': '67890',
                        'serverName': 'gov-server',
                        'serverInstanceStatus': 'RUN',
                        'private_ip': '10.0.1.100',
                        'internal_ip': '192.168.1.10',
                        'access_key': 'GOV-AKIA123456789',
                        'security_group_id': 'sg-gov123456'
                    }
                ],
                'totalRows': 1
            }
        }
        
        mock_make_request.return_value = mock_response
        
        result = self.gov_client.get_server_instances()
        
        assert result['total_count'] == 1
        assert result['compliance_status'] == 'validated'
        
        instance = result['instances'][0]
        
        # Sensitive data should be masked
        assert instance['private_ip'] == '***MASKED***'
        assert instance['internal_ip'] == '***MASKED***'
        assert instance['access_key'] == '***MASKED***'
        assert instance['security_group_id'] == '***MASKED***'
        
        # Non-sensitive data should be preserved
        assert instance['serverName'] == 'gov-server'
        assert instance['serverInstanceStatus'] == 'RUN'
    
    @patch.object(NCPGovClient, '_make_request')
    def test_government_cloud_vpc_compliance_checking(self, mock_make_request):
        """Test that government cloud VPC responses include compliance checking."""
        mock_response = {
            'getVpcListResponse': {
                'vpcList': [
                    {
                        'vpcNo': 'vpc-gov123',
                        'vpcName': 'government-vpc',
                        'vpcStatus': 'RUN',
                        'ipv4CidrBlock': '10.0.0.0/16'
                    },
                    {
                        'vpcNo': 'vpc-gov456',
                        'vpcName': 'test-vpc',
                        'vpcStatus': 'INIT',
                        'ipv4CidrBlock': '10.1.0.0/16'
                    }
                ],
                'totalRows': 2
            }
        }
        
        mock_make_request.return_value = mock_response
        
        result = self.gov_client.get_vpc_list()
        
        assert result['total_count'] == 2
        assert result['compliance_status'] == 'validated'
        
        vpcs = result['vpcs']
        
        # First VPC (RUN status) should be compliant
        assert vpcs[0]['policy_compliance'] == 'compliant'
        
        # Second VPC (INIT status) should need review
        assert vpcs[1]['policy_compliance'] == 'needs_review'
    
    def test_government_cloud_object_storage_compliance(self):
        """Test government cloud object storage compliance response."""
        result = self.gov_client.get_object_storage_buckets()
        
        # Should return compliance information even with empty buckets
        assert 'compliance_status' in result
        assert 'security_policy' in result
        assert result['compliance_status'] == 'validated'
        assert result['security_policy'] == 'government_cloud_compliant'


class TestNCPDataValidation:
    """Test cases for NCP data validation and edge cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = NCPClient("test-key", "test-secret", "KR")
    
    def test_handle_null_values_in_response(self):
        """Test handling of null values in API responses."""
        mock_response = {
            'getServerInstanceListResponse': {
                'serverInstanceList': [
                    {
                        'serverInstanceNo': '12345',
                        'serverName': None,  # Null value
                        'serverInstanceStatus': 'RUN',
                        'publicIp': None,  # Null value
                        'privateIp': '10.0.1.100'
                    }
                ],
                'totalRows': 1
            }
        }
        
        with patch.object(self.client, '_make_request', return_value=mock_response):
            result = self.client.get_server_instances()
        
        assert result['total_count'] == 1
        instance = result['instances'][0]
        
        # Should handle null values gracefully
        assert instance['serverInstanceNo'] == '12345'
        assert instance['serverName'] is None
        assert instance['publicIp'] is None
        assert instance['privateIp'] == '10.0.1.100'
    
    def test_handle_missing_fields_in_response(self):
        """Test handling of missing fields in API responses."""
        mock_response = {
            'getServerInstanceListResponse': {
                'serverInstanceList': [
                    {
                        'serverInstanceNo': '12345',
                        'serverInstanceStatus': 'RUN'
                        # Missing many expected fields
                    }
                ],
                'totalRows': 1
            }
        }
        
        with patch.object(self.client, '_make_request', return_value=mock_response):
            result = self.client.get_server_instances()
        
        assert result['total_count'] == 1
        instance = result['instances'][0]
        
        # Should handle missing fields gracefully
        assert instance['serverInstanceNo'] == '12345'
        assert instance['serverInstanceStatus'] == 'RUN'
    
    def test_handle_unexpected_data_types(self):
        """Test handling of unexpected data types in responses."""
        mock_response = {
            'getServerInstanceListResponse': {
                'serverInstanceList': [
                    {
                        'serverInstanceNo': 12345,  # Number instead of string
                        'serverName': 'test-server',
                        'serverInstanceStatus': 'RUN',
                        'cpuCount': '2',  # String instead of number
                        'memorySize': '8589934592'  # String instead of number
                    }
                ],
                'totalRows': '1'  # String instead of number
            }
        }
        
        with patch.object(self.client, '_make_request', return_value=mock_response):
            result = self.client.get_server_instances()
        
        # Should handle type mismatches gracefully
        assert result['total_count'] == 1  # Should convert string to int
        instance = result['instances'][0]
        
        assert instance['serverInstanceNo'] == 12345
        assert instance['cpuCount'] == '2'  # Preserve as received
        assert instance['memorySize'] == '8589934592'
    
    def test_handle_very_large_response(self):
        """Test handling of very large API responses."""
        # Generate a large response
        large_instance_list = []
        for i in range(1000):
            large_instance_list.append({
                'serverInstanceNo': f'i-{i:06d}',
                'serverName': f'large-test-server-{i}',
                'serverInstanceStatus': 'RUN',
                'serverInstanceType': 'SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002'
            })
        
        mock_response = {
            'getServerInstanceListResponse': {
                'serverInstanceList': large_instance_list,
                'totalRows': 1000
            }
        }
        
        with patch.object(self.client, '_make_request', return_value=mock_response):
            result = self.client.get_server_instances()
        
        assert result['total_count'] == 1000
        assert len(result['instances']) == 1000
        
        # Verify first and last instances
        assert result['instances'][0]['serverName'] == 'large-test-server-0'
        assert result['instances'][999]['serverName'] == 'large-test-server-999'


if __name__ == '__main__':
    pytest.main([__file__])