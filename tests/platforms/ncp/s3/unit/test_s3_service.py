"""
Unit tests for NCP S3 Service.

Tests NCP S3 service functionality, data models, and output formatting.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import List, Dict, Any

# Import NCP S3 service classes - updated to use consolidated modules
from src.ic.platforms.ncp.s3.info import NCPBucket, fetch_ncp_s3_info, print_ncp_s3_table, format_bucket_size, format_object_count
from src.ic.platforms.ncp.client import NCPClient, NCPAPIError


class TestNCPBucketDataModel:
    """Test cases for NCPBucket data model."""
    
    def test_ncp_bucket_creation(self):
        """Test NCPBucket creation with all fields."""
        bucket = NCPBucket(
            bucket_name="test-bucket",
            region="KR",
            creation_date="2024-01-01T00:00:00+0900",
            object_count=1000,
            bucket_size=1073741824,  # 1GB in bytes
            storage_class="STANDARD",
            access_control="PRIVATE",
            versioning_status="Enabled",
            encryption_status="Disabled"
        )
        
        assert bucket.bucket_name == "test-bucket"
        assert bucket.region == "KR"
        assert bucket.object_count == 1000
        assert bucket.bucket_size == 1073741824
        assert bucket.storage_class == "STANDARD"
        assert bucket.access_control == "PRIVATE"
    
    def test_ncp_bucket_from_api_response(self):
        """Test NCPBucket creation from API response."""
        api_data = {
            'bucketName': 'api-bucket',
            'creationDate': '2024-03-01T08:00:00+0900',
            'objectCount': 5000,
            'bucketSize': 5368709120,  # 5GB in bytes
            'storageClass': 'STANDARD_IA',
            'accessControl': 'PUBLIC_READ',
            'versioningStatus': 'Disabled',
            'encryptionStatus': 'Enabled'
        }
        
        bucket = NCPBucket.from_api_response(api_data, "US")
        
        assert bucket.bucket_name == 'api-bucket'
        assert bucket.region == "US"
        assert bucket.object_count == 5000
        assert bucket.bucket_size == 5368709120
        assert bucket.storage_class == 'STANDARD_IA'
        assert bucket.access_control == 'PUBLIC_READ'


class TestNCPS3Service:
    """Test cases for NCP S3 service functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=NCPClient)
        self.mock_client.region = "KR"
        
        self.sample_buckets_data = [
            {
                'bucketName': 'test-bucket-1',
                'creationDate': '2024-01-01T00:00:00+0900',
                'objectCount': 1000,
                'bucketSize': 1073741824,  # 1GB
                'storageClass': 'STANDARD',
                'accessControl': 'PRIVATE',
                'versioningStatus': 'Enabled',
                'encryptionStatus': 'Disabled'
            },
            {
                'bucketName': 'test-bucket-2',
                'creationDate': '2024-02-01T12:00:00+0900',
                'objectCount': 5000,
                'bucketSize': 5368709120,  # 5GB
                'storageClass': 'STANDARD_IA',
                'accessControl': 'PUBLIC_READ',
                'versioningStatus': 'Disabled',
                'encryptionStatus': 'Enabled'
            }
        ]
    
    def test_fetch_ncp_s3_info_success(self):
        """Test successful S3 bucket information fetching."""
        self.mock_client.get_object_storage_buckets.return_value = self.sample_buckets_data
        
        result = fetch_ncp_s3_info(self.mock_client)
        
        assert len(result) == 2
        assert isinstance(result[0], NCPBucket)
        assert result[0].bucket_name == 'test-bucket-1'
        assert result[1].bucket_name == 'test-bucket-2'
        
        self.mock_client.get_object_storage_buckets.assert_called_once()
    
    def test_fetch_ncp_s3_info_with_name_filter(self):
        """Test S3 bucket fetching with name filter."""
        self.mock_client.get_object_storage_buckets.return_value = self.sample_buckets_data
        
        result = fetch_ncp_s3_info(self.mock_client, name_filter="bucket-1")
        
        assert len(result) == 1
        assert result[0].bucket_name == 'test-bucket-1'
    
    def test_fetch_ncp_s3_info_empty_result(self):
        """Test S3 bucket fetching with empty result."""
        self.mock_client.get_object_storage_buckets.return_value = []
        
        result = fetch_ncp_s3_info(self.mock_client)
        
        assert len(result) == 0
    
    def test_fetch_ncp_s3_info_api_error(self):
        """Test S3 bucket fetching with API error."""
        self.mock_client.get_object_storage_buckets.side_effect = NCPAPIError("API Error")
        
        result = fetch_ncp_s3_info(self.mock_client)
        
        assert len(result) == 0  # Error handler should return empty list
    
    def test_format_bucket_size(self):
        """Test bucket size formatting."""
        # Test bytes
        assert format_bucket_size(512) == "512 B"
        
        # Test KB
        assert format_bucket_size(1024) == "1.0 KB"
        assert format_bucket_size(2048) == "2.0 KB"
        
        # Test MB
        assert format_bucket_size(1048576) == "1.0 MB"
        assert format_bucket_size(104857600) == "100.0 MB"
        
        # Test GB
        assert format_bucket_size(1073741824) == "1.0 GB"
        assert format_bucket_size(5368709120) == "5.0 GB"
        
        # Test TB
        assert format_bucket_size(1099511627776) == "1.0 TB"
        
        # Test zero
        assert format_bucket_size(0) == "0 B"
    
    def test_format_object_count(self):
        """Test object count formatting."""
        # Test small numbers
        assert format_object_count(0) == "0"
        assert format_object_count(100) == "100"
        assert format_object_count(999) == "999"
        
        # Test thousands
        assert format_object_count(1000) == "1.0K"
        assert format_object_count(1500) == "1.5K"
        assert format_object_count(999999) == "1000.0K"
        
        # Test millions
        assert format_object_count(1000000) == "1.0M"
        assert format_object_count(2500000) == "2.5M"
    
    @patch('src.ic.platforms.ncp.s3.info.console')
    def test_print_ncp_s3_table_empty(self, mock_console):
        """Test S3 table printing with empty data."""
        print_ncp_s3_table([])
        
        mock_console.print.assert_called_with("(No Buckets)")
    
    @patch('src.ic.platforms.ncp.s3.info.console')
    def test_print_ncp_s3_table_with_data(self, mock_console):
        """Test S3 table printing with data."""
        buckets = [
            NCPBucket(
                bucket_name="test-bucket",
                region="KR",
                creation_date="2024-01-01T00:00:00+0900",
                object_count=1000,
                bucket_size=1073741824,
                storage_class="STANDARD",
                access_control="PRIVATE",
                versioning_status="Enabled",
                encryption_status="Disabled"
            )
        ]
        
        print_ncp_s3_table(buckets, verbose=False)
        
        # Should call console.print multiple times (header + table)
        assert mock_console.print.call_count >= 2
    
    @patch('src.ic.platforms.ncp.s3.info.console')
    def test_print_ncp_s3_table_verbose(self, mock_console):
        """Test S3 table printing in verbose mode."""
        buckets = [
            NCPBucket(
                bucket_name="test-bucket",
                region="KR",
                creation_date="2024-01-01T00:00:00+0900",
                object_count=1000,
                bucket_size=1073741824,
                storage_class="STANDARD",
                access_control="PRIVATE",
                versioning_status="Enabled",
                encryption_status="Disabled"
            )
        ]
        
        print_ncp_s3_table(buckets, verbose=True)
        
        # Should call console.print multiple times (header + table)
        assert mock_console.print.call_count >= 2


class TestNCPS3ServiceUtilities:
    """Test cases for NCP S3 service utility functions."""
    
    def test_format_storage_class(self):
        """Test storage class formatting."""
        from src.ic.platforms.ncp.s3.info import format_storage_class
        
        assert format_storage_class('STANDARD') == 'Standard'
        assert format_storage_class('STANDARD_IA') == 'Standard-IA'
        assert format_storage_class('COLD') == 'Cold Storage'
        assert format_storage_class('ARCHIVE') == 'Archive'
        assert format_storage_class('UNKNOWN') == 'UNKNOWN'
    
    def test_format_access_control(self):
        """Test access control formatting."""
        from src.ic.platforms.ncp.s3.info import format_access_control
        
        # Note: These return rich markup, so we check for content
        private_result = format_access_control('PRIVATE')
        assert 'Private' in private_result
        assert '[red]' in private_result
        
        public_read_result = format_access_control('PUBLIC_READ')
        assert 'Public Read' in public_read_result
        assert '[yellow]' in public_read_result
        
        public_rw_result = format_access_control('PUBLIC_READ_WRITE')
        assert 'Public R/W' in public_rw_result
        assert '[red bold]' in public_rw_result
    
    def test_format_feature_status(self):
        """Test feature status formatting."""
        from src.ic.platforms.ncp.s3.info import format_feature_status
        
        # Enabled states
        enabled_result = format_feature_status('enabled')
        assert 'Enabled' in enabled_result
        assert '[green]' in enabled_result
        
        active_result = format_feature_status('active')
        assert 'Enabled' in active_result
        
        # Disabled states
        disabled_result = format_feature_status('disabled')
        assert 'Disabled' in disabled_result
        assert '[dim]' in disabled_result
        
        # Unknown states
        unknown_result = format_feature_status('unknown')
        assert unknown_result == 'unknown'


class TestNCPS3ServiceIntegration:
    """Integration tests for NCP S3 service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=NCPClient)
        self.mock_client.region = "KR"
    
    @patch('src.ic.platforms.ncp.s3.info.load_ncp_config')
    @patch('src.ic.platforms.ncp.s3.info.NCPClient')
    def test_s3_service_integration(self, mock_client_class, mock_load_config):
        """Test S3 service integration with configuration loading."""
        # Mock configuration
        mock_config = {
            'access_key': 'test-key',
            'secret_key': 'test-secret',
            'region': 'KR'
        }
        mock_load_config.return_value = mock_config
        
        # Mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_object_storage_buckets.return_value = []
        
        # Test the integration
        result = fetch_ncp_s3_info(mock_client)
        
        assert isinstance(result, list)
        mock_client.get_object_storage_buckets.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])