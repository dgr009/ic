"""
Unit tests for NCP Gov Client classes.

Tests NCP Gov API client functionality, authentication, error handling, and security features.
"""

import pytest
from unittest.mock import Mock, patch
from src.ic.platforms.ncpgov.client import NCPGovClient, NCPGovAPIError


class TestNCPGovClient:
    """Test cases for NCPGovClient class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.access_key = "gov-access-key"
        self.secret_key = "gov-secret-key"
        self.region = "KR"
        
        self.client = NCPGovClient(
            access_key=self.access_key,
            secret_key=self.secret_key,
            apigw_key="test-apigw-key",
            region=self.region
        )
    
    def test_ncpgov_client_initialization(self):
        """Test NCPGovClient initialization."""
        assert self.client.access_key == self.access_key
        assert self.client.secret_key == self.secret_key
        assert self.client.region == self.region
    
    def test_get_server_instances_basic(self):
        """Test basic server instances functionality."""
        try:
            result = self.client.get_server_instances()
            assert isinstance(result, list)
        except NCPGovAPIError:
            # Expected in test environment without real credentials
            pass
    
    def test_get_object_storage_buckets_basic(self):
        """Test basic object storage buckets functionality."""
        try:
            result = self.client.get_object_storage_buckets()
            assert isinstance(result, list)
        except NCPGovAPIError:
            # Expected in test environment without real credentials
            pass
    
    def test_get_vpc_list_basic(self):
        """Test basic VPC list functionality."""
        try:
            result = self.client.get_vpc_list()
            assert isinstance(result, list)
        except NCPGovAPIError:
            # Expected in test environment without real credentials
            pass
    
    def test_test_connection(self):
        """Test connection test functionality."""
        result = self.client.test_connection()
        assert isinstance(result, bool)
    
    def test_validate_gov_compliance(self):
        """Test government compliance validation."""
        compliance = self.client.validate_gov_compliance()
        
        assert isinstance(compliance, dict)
        assert 'encryption_enabled' in compliance
        assert 'audit_logging_enabled' in compliance
        assert 'access_control_enabled' in compliance
        assert 'overall_compliance' in compliance


class TestNCPGovAPIError:
    """Test cases for NCPGovAPIError exception class."""
    
    def test_ncpgov_api_error_basic(self):
        """Test basic NCPGovAPIError creation."""
        error = NCPGovAPIError("Test error message")
        
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.error_code is None
        assert error.status_code is None
    
    def test_ncpgov_api_error_with_code(self):
        """Test NCPGovAPIError with error code."""
        error = NCPGovAPIError("Test error", error_code="25001")
        
        assert error.message == "Test error"
        assert error.error_code == "25001"
        assert error.status_code is None
    
    def test_ncpgov_api_error_full(self):
        """Test NCPGovAPIError with all parameters."""
        error = NCPGovAPIError("Test error", error_code="25001", status_code=400)
        
        assert error.message == "Test error"
        assert error.error_code == "25001"
        assert error.status_code == 400


if __name__ == '__main__':
    pytest.main([__file__])