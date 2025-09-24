"""
Unit tests for NCP Client classes.

Tests NCP API client functionality, authentication, error handling, and data models.
"""

import os
import time
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import requests

# Import NCP client classes
from ncp.client import NCPClient, NCPAPIError, NCPInstance, NCPBucket, NCPVPC


class TestNCPClient:
    """Test cases for NCPClient class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.access_key = "test-access-key"
        self.secret_key = "test-secret-key"
        self.region = "KR"
        
        self.client = NCPClient(
            access_key=self.access_key,
            secret_key=self.secret_key,
            region=self.region
        )
    
    def test_ncp_client_initialization(self):
        """Test NCPClient initialization."""
        assert self.client.access_key == self.access_key
        assert self.client.secret_key == self.secret_key
        assert self.client.region == self.region
        assert self.client.base_url == 'https://ncloud.apigw.ntruss.com'
        assert self.client.session is not None
        
        # Test headers
        assert self.client.session.headers['Content-Type'] == 'application/json'
        assert self.client.session.headers['x-ncp-iam-access-key'] == self.access_key
    
    def test_get_base_url(self):
        """Test base URL generation for different regions."""
        # Test KR region
        kr_client = NCPClient("key", "secret", "KR")
        assert kr_client.base_url == 'https://ncloud.apigw.ntruss.com'
        
        # Test US region
        us_client = NCPClient("key", "secret", "US")
        assert us_client.base_url == 'https://ncloud.apigw.ntruss.com'
        
        # Test JP region
        jp_client = NCPClient("key", "secret", "JP")
        assert jp_client.base_url == 'https://ncloud.apigw.ntruss.com'
        
        # Test unknown region (should default to KR)
        unknown_client = NCPClient("key", "secret", "UNKNOWN")
        assert unknown_client.base_url == 'https://ncloud.apigw.ntruss.com'
    
    def test_generate_signature(self):
        """Test NCP API signature generation."""
        method = "GET"
        uri = "/vserver/v2/getServerInstanceList"
        timestamp = "1234567890000"
        
        signature = self.client._generate_signature(method, uri, timestamp)
        
        # Signature should be base64 encoded
        assert isinstance(signature, str)
        assert len(signature) > 0
        
        # Same inputs should produce same signature
        signature2 = self.client._generate_signature(method, uri, timestamp)
        assert signature == signature2
    
    @patch('requests.Session.request')
    def test_make_request_success(self, mock_request):
        """Test successful API request."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'getServerInstanceListResponse': {
                'serverInstanceList': [],
                'totalRows': 0
            }
        }
        mock_request.return_value = mock_response
        
        result = self.client._make_request('GET', '/getServerInstanceList')
        
        assert result is not None
        assert 'getServerInstanceListResponse' in result
        mock_request.assert_called_once()
    
    @patch('requests.Session.request')
    def test_make_request_api_error(self, mock_request):
        """Test API request with error response."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'responseError': {
                'returnCode': '25001',
                'returnMessage': 'Invalid parameter'
            }
        }
        mock_request.return_value = mock_response
        
        with pytest.raises(NCPAPIError) as exc_info:
            self.client._make_request('GET', '/getServerInstanceList')
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == '25001'
        assert 'Invalid parameter' in exc_info.value.message
    
    @patch('requests.Session.request')
    def test_make_request_network_error(self, mock_request):
        """Test API request with network error."""
        # Mock network error
        mock_request.side_effect = requests.exceptions.ConnectionError("Network error")
        
        with pytest.raises(NCPAPIError) as exc_info:
            self.client._make_request('GET', '/getServerInstanceList')
        
        assert '네트워크 오류' in exc_info.value.message
    
    @patch('requests.Session.request')
    def test_make_request_timeout(self, mock_request):
        """Test API request with timeout."""
        # Mock timeout error
        mock_request.side_effect = requests.exceptions.Timeout("Request timeout")
        
        with pytest.raises(NCPAPIError) as exc_info:
            self.client._make_request('GET', '/getServerInstanceList', timeout=5.0)
        
        assert '네트워크 오류' in exc_info.value.message
    
    @patch.object(NCPClient, '_make_request')
    def test_get_server_instances_success(self, mock_make_request):
        """Test successful server instances retrieval."""
        # Mock API response
        mock_response = {
            'getServerInstanceListResponse': {
                'serverInstanceList': [
                    {
                        'serverInstanceNo': '12345',
                        'serverName': 'test-server',
                        'serverInstanceStatus': 'RUN',
                        'serverInstanceType': 'SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002'
                    }
                ],
                'totalRows': 1
            }
        }
        mock_make_request.return_value = mock_response
        
        result = self.client.get_server_instances()
        
        assert result['total_count'] == 1
        assert len(result['instances']) == 1
        assert result['instances'][0]['serverName'] == 'test-server'
        
        # Verify request parameters
        mock_make_request.assert_called_once_with(
            'GET', '/getServerInstanceList', 
            params={'responseFormatType': 'json'}, 
            timeout=30.0
        )
    
    @patch.object(NCPClient, '_make_request')
    def test_get_server_instances_with_filter(self, mock_make_request):
        """Test server instances retrieval with name filter."""
        mock_response = {
            'getServerInstanceListResponse': {
                'serverInstanceList': [],
                'totalRows': 0
            }
        }
        mock_make_request.return_value = mock_response
        
        self.client.get_server_instances(name_filter='test-server')
        
        # Verify filter parameter was passed
        call_args = mock_make_request.call_args
        assert call_args[1]['params']['serverName'] == 'test-server'
    
    @patch.object(NCPClient, '_make_request')
    def test_get_server_instances_error(self, mock_make_request):
        """Test server instances retrieval with error."""
        mock_make_request.side_effect = NCPAPIError("API Error")
        
        with pytest.raises(NCPAPIError):
            self.client.get_server_instances()
    
    def test_get_object_storage_buckets_success(self):
        """Test successful object storage buckets retrieval."""
        result = self.client.get_object_storage_buckets()
        
        assert 'buckets' in result
        assert 'total_count' in result
        assert isinstance(result['buckets'], list)
        assert result['total_count'] >= 0
    
    def test_get_object_storage_buckets_with_filter(self):
        """Test object storage buckets retrieval with name filter."""
        result = self.client.get_object_storage_buckets(name_filter='test')
        
        assert 'buckets' in result
        # All returned buckets should contain 'test' in name
        for bucket in result['buckets']:
            assert 'test' in bucket['bucketName'].lower()
    
    def test_generate_mock_bucket_data(self):
        """Test mock bucket data generation."""
        buckets = self.client._generate_mock_bucket_data()
        
        assert isinstance(buckets, list)
        assert len(buckets) > 0
        
        # Verify bucket structure
        for bucket in buckets:
            assert 'bucketName' in bucket
            assert 'region' in bucket
            assert 'creationDate' in bucket
            assert 'storageClass' in bucket
            assert bucket['region'] == self.region
    
    def test_get_vpc_list_success(self):
        """Test successful VPC list retrieval."""
        result = self.client.get_vpc_list()
        
        assert 'vpcs' in result
        assert 'total_count' in result
        assert isinstance(result['vpcs'], list)
        assert result['total_count'] >= 0
    
    def test_get_vpc_list_with_filter(self):
        """Test VPC list retrieval with name filter."""
        result = self.client.get_vpc_list(name_filter='main')
        
        assert 'vpcs' in result
        # All returned VPCs should contain 'main' in name
        for vpc in result['vpcs']:
            assert 'main' in vpc['vpcName'].lower()
    
    def test_generate_mock_vpc_data(self):
        """Test mock VPC data generation."""
        vpcs = self.client._generate_mock_vpc_data()
        
        assert isinstance(vpcs, list)
        assert len(vpcs) > 0
        
        # Verify VPC structure
        for vpc in vpcs:
            assert 'vpcNo' in vpc
            assert 'vpcName' in vpc
            assert 'ipv4CidrBlock' in vpc
            assert 'vpcStatus' in vpc
            assert 'regionCode' in vpc
            assert vpc['regionCode'] == self.region
    
    @patch.object(NCPClient, 'get_server_instances')
    def test_test_connection_success(self, mock_get_instances):
        """Test successful connection test."""
        mock_get_instances.return_value = {'instances': [], 'total_count': 0}
        
        result = self.client.test_connection()
        
        assert result is True
        mock_get_instances.assert_called_once_with(page_size=1)
    
    @patch.object(NCPClient, 'get_server_instances')
    def test_test_connection_failure(self, mock_get_instances):
        """Test connection test failure."""
        mock_get_instances.side_effect = NCPAPIError("Connection failed")
        
        result = self.client.test_connection()
        
        assert result is False


class TestNCPDataModels:
    """Test cases for NCP data model classes."""
    
    def test_ncp_instance_model(self):
        """Test NCPInstance data model."""
        instance = NCPInstance(
            instance_id="i-12345",
            instance_name="test-server",
            instance_status="RUN",
            instance_type="SVR.VSVR.STAND.C002.M008.NET.SSD.B050.G002",
            cpu_count=2,
            memory_size=8589934592,
            platform_type="LNX64",
            public_ip="123.456.789.10",
            private_ip="10.0.1.100",
            vpc_name="test-vpc",
            subnet_name="test-subnet",
            region="KR",
            created_date="2024-01-01T00:00:00+0900"
        )
        
        assert instance.instance_id == "i-12345"
        assert instance.instance_name == "test-server"
        assert instance.cpu_count == 2
        assert instance.region == "KR"
    
    def test_ncp_bucket_model(self):
        """Test NCPBucket data model."""
        bucket = NCPBucket(
            bucket_name="test-bucket",
            region="KR",
            creation_date="2024-01-01T00:00:00+0900",
            object_count=100,
            bucket_size=1073741824,
            storage_class="STANDARD",
            access_control="private"
        )
        
        assert bucket.bucket_name == "test-bucket"
        assert bucket.region == "KR"
        assert bucket.object_count == 100
        assert bucket.storage_class == "STANDARD"
    
    def test_ncp_vpc_model(self):
        """Test NCPVPC data model."""
        vpc = NCPVPC(
            vpc_id="vpc-12345",
            vpc_name="test-vpc",
            ipv4_cidr_block="10.0.0.0/16",
            status="RUN",
            region="KR",
            subnet_count=2,
            subnets=[],
            route_tables=[]
        )
        
        assert vpc.vpc_id == "vpc-12345"
        assert vpc.vpc_name == "test-vpc"
        assert vpc.ipv4_cidr_block == "10.0.0.0/16"
        assert vpc.subnet_count == 2


class TestNCPAPIError:
    """Test cases for NCPAPIError exception class."""
    
    def test_ncp_api_error_basic(self):
        """Test basic NCPAPIError creation."""
        error = NCPAPIError("Test error message")
        
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.error_code is None
        assert error.status_code is None
    
    def test_ncp_api_error_with_code(self):
        """Test NCPAPIError with error code."""
        error = NCPAPIError("Test error", error_code="25001")
        
        assert error.message == "Test error"
        assert error.error_code == "25001"
        assert error.status_code is None
    
    def test_ncp_api_error_with_status_code(self):
        """Test NCPAPIError with status code."""
        error = NCPAPIError("Test error", status_code=400)
        
        assert error.message == "Test error"
        assert error.error_code is None
        assert error.status_code == 400
    
    def test_ncp_api_error_full(self):
        """Test NCPAPIError with all parameters."""
        error = NCPAPIError("Test error", error_code="25001", status_code=400)
        
        assert error.message == "Test error"
        assert error.error_code == "25001"
        assert error.status_code == 400


if __name__ == '__main__':
    pytest.main([__file__])