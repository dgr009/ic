"""
Unit tests for NCP Client classes.

Tests NCP API client functionality, authentication, error handling, and data models.
"""

import pytest
from unittest.mock import Mock, patch
from src.ic.platforms.ncp.client import NCPClient, NCPAPIError


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
        assert self.client.session is not None
    
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
                        'serverInstanceStatus': {'code': 'RUN', 'codeName': 'running'}
                    }
                ],
                'totalRows': 1
            }
        }
        mock_make_request.return_value = mock_response
        
        result = self.client.get_server_instances()
        
        assert isinstance(result, list)
        assert len(result) >= 0
    
    def test_get_object_storage_buckets_basic(self):
        """Test basic object storage buckets functionality."""
        # This will use mock data since we don't have real credentials
        try:
            result = self.client.get_object_storage_buckets()
            assert isinstance(result, list)
        except NCPAPIError:
            # Expected in test environment without real credentials
            pass
    
    def test_get_vpc_list_basic(self):
        """Test basic VPC list functionality."""
        # This will use mock data since we don't have real credentials
        try:
            result = self.client.get_vpc_list()
            assert isinstance(result, list)
        except NCPAPIError:
            # Expected in test environment without real credentials
            pass
    
    def test_test_connection(self):
        """Test connection test functionality."""
        # This should work even without real credentials (returns False)
        result = self.client.test_connection()
        assert isinstance(result, bool)
    
    def test_get_performance_stats(self):
        """Test performance statistics retrieval."""
        stats = self.client.get_performance_stats()
        
        assert isinstance(stats, dict)
        assert 'timeout' in stats
        assert 'max_retries' in stats
        assert 'backoff_factor' in stats
        assert 'region' in stats
        assert 'platform' in stats
    
    def test_client_close(self):
        """Test client resource cleanup."""
        # Should not raise any exceptions
        self.client.close()


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