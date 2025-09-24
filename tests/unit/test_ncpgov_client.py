"""
Unit tests for NCP Gov Client classes.

Tests NCP Government Cloud API client functionality, security validation, 
compliance checks, and enhanced error handling.
"""

import os
import time
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import requests

# Import NCP Gov client classes
from ncpgov.client import NCPGovClient, NCPGovAPIError, NCPGovSecurityValidator


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
            region=self.region
        )
    
    def test_ncpgov_client_initialization(self):
        """Test NCPGovClient initialization."""
        assert self.client.access_key == self.access_key
        assert self.client.secret_key == self.secret_key
        assert self.client.region == self.region
        assert self.client.base_url == 'https://gov-ncloud.apigw.ntruss.com'
        assert self.client.session is not None
        assert self.client.security_validator is not None
        
        # Test government cloud specific headers
        assert self.client.session.headers['Content-Type'] == 'application/json'
        assert self.client.session.headers['x-ncp-iam-access-key'] == self.access_key
        assert self.client.session.headers['x-ncp-gov-compliance'] == 'enabled'
    
    def test_get_base_url_government_cloud(self):
        """Test base URL generation for government cloud."""
        # Test KR region (government cloud)
        kr_client = NCPGovClient("key", "secret", "KR")
        assert kr_client.base_url == 'https://gov-ncloud.apigw.ntruss.com'
        
        # Test unknown region (should default to KR government cloud)
        unknown_client = NCPGovClient("key", "secret", "UNKNOWN")
        assert unknown_client.base_url == 'https://gov-ncloud.apigw.ntruss.com'
    
    def test_generate_signature_government_enhanced(self):
        """Test NCP Gov API signature generation with enhanced security."""
        method = "GET"
        uri = "/gov/vserver/v2/getServerInstanceList"
        timestamp = "1234567890000"
        
        signature = self.client._generate_signature(method, uri, timestamp)
        
        # Signature should be base64 encoded
        assert isinstance(signature, str)
        assert len(signature) > 0
        
        # Government cloud signature should be different from regular NCP
        # due to additional security elements
        from ncp.client import NCPClient
        regular_client = NCPClient("key", "secret", "KR")
        regular_signature = regular_client._generate_signature(method, uri, timestamp)
        
        # Signatures should be different due to gov-compliance addition
        assert signature != regular_signature
    
    @patch('requests.Session.request')
    def test_make_request_success_with_gov_headers(self, mock_request):
        """Test successful API request with government cloud headers."""
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
        
        # Verify government cloud specific headers were sent
        call_args = mock_request.call_args
        headers = call_args[1]['headers']
        assert 'x-ncp-gov-audit' in headers
        assert headers['x-ncp-gov-audit'] == 'enabled'
    
    @patch('requests.Session.request')
    def test_make_request_longer_timeout(self, mock_request):
        """Test API request uses longer timeout for government cloud."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_request.return_value = mock_response
        
        self.client._make_request('GET', '/getServerInstanceList')
        
        # Verify longer timeout was used (45 seconds vs 30 for regular NCP)
        call_args = mock_request.call_args
        assert call_args[1]['timeout'] == 45.0
    
    @patch.object(NCPGovClient, '_make_request')
    def test_get_server_instances_with_masking(self, mock_make_request):
        """Test server instances retrieval with sensitive data masking."""
        # Mock API response with sensitive data
        mock_response = {
            'getServerInstanceListResponse': {
                'serverInstanceList': [
                    {
                        'serverInstanceNo': '12345',
                        'serverName': 'gov-server',
                        'serverInstanceStatus': 'RUN',
                        'private_ip': '10.0.1.100',
                        'internal_ip': '192.168.1.10'
                    }
                ],
                'totalRows': 1
            }
        }
        mock_make_request.return_value = mock_response
        
        result = self.client.get_server_instances()
        
        assert result['total_count'] == 1
        assert result['compliance_status'] == 'validated'
        
        # Verify sensitive data was masked
        instance = result['instances'][0]
        assert instance['private_ip'] == '***MASKED***'
        assert instance['internal_ip'] == '***MASKED***'
        assert instance['serverName'] == 'gov-server'  # Non-sensitive data preserved
    
    @patch.object(NCPGovClient, '_make_request')
    def test_get_server_instances_error_handling(self, mock_make_request):
        """Test server instances retrieval error handling."""
        mock_make_request.side_effect = NCPGovAPIError("Government cloud access denied")
        
        with pytest.raises(NCPGovAPIError) as exc_info:
            self.client.get_server_instances()
        
        assert "Government cloud access denied" in str(exc_info.value)
    
    def test_get_object_storage_buckets_government_compliance(self):
        """Test object storage buckets retrieval with government compliance."""
        result = self.client.get_object_storage_buckets()
        
        assert 'buckets' in result
        assert 'total_count' in result
        assert 'compliance_status' in result
        assert 'security_policy' in result
        assert result['compliance_status'] == 'validated'
        assert result['security_policy'] == 'government_cloud_compliant'
    
    @patch.object(NCPGovClient, '_make_request')
    def test_get_vpc_list_with_policy_compliance(self, mock_make_request):
        """Test VPC list retrieval with policy compliance checking."""
        # Mock API response
        mock_response = {
            'getVpcListResponse': {
                'vpcList': [
                    {
                        'vpcNo': 'vpc-12345',
                        'vpcName': 'gov-vpc',
                        'vpcStatus': 'RUN',
                        'ipv4CidrBlock': '10.0.0.0/16'
                    },
                    {
                        'vpcNo': 'vpc-67890',
                        'vpcName': 'test-vpc',
                        'vpcStatus': 'INIT',
                        'ipv4CidrBlock': '10.1.0.0/16'
                    }
                ],
                'totalRows': 2
            }
        }
        mock_make_request.return_value = mock_response
        
        result = self.client.get_vpc_list()
        
        assert result['total_count'] == 2
        assert result['compliance_status'] == 'validated'
        
        # Verify policy compliance was checked for each VPC
        vpcs = result['vpcs']
        assert vpcs[0]['policy_compliance'] == 'compliant'  # RUN status
        assert vpcs[1]['policy_compliance'] == 'needs_review'  # INIT status
    
    def test_check_network_policy_compliance(self):
        """Test network policy compliance checking."""
        # Test compliant VPC
        compliant_vpc = {'vpcStatus': 'RUN'}
        result = self.client._check_network_policy_compliance(compliant_vpc)
        assert result == 'compliant'
        
        # Test non-compliant VPC
        non_compliant_vpc = {'vpcStatus': 'INIT'}
        result = self.client._check_network_policy_compliance(non_compliant_vpc)
        assert result == 'needs_review'
    
    @patch.object(NCPGovClient, 'get_server_instances')
    def test_test_connection_with_compliance_validation(self, mock_get_instances):
        """Test connection test with compliance validation."""
        # Test successful connection with compliance
        mock_get_instances.return_value = {
            'instances': [],
            'total_count': 0,
            'compliance_status': 'validated'
        }
        
        result = self.client.test_connection()
        assert result is True
        
        # Test connection without compliance validation
        mock_get_instances.return_value = {
            'instances': [],
            'total_count': 0,
            'compliance_status': 'failed'
        }
        
        result = self.client.test_connection()
        assert result is False
    
    @patch.object(NCPGovClient, 'get_server_instances')
    def test_test_connection_failure(self, mock_get_instances):
        """Test connection test failure."""
        mock_get_instances.side_effect = NCPGovAPIError("Government cloud connection failed")
        
        result = self.client.test_connection()
        assert result is False


class TestNCPGovSecurityValidator:
    """Test cases for NCPGovSecurityValidator class."""
    
    def test_validate_government_compliance_success(self):
        """Test successful government compliance validation."""
        compliant_config = {
            'encryption_enabled': True,
            'audit_logging_enabled': True,
            'access_control_enabled': True
        }
        
        result = NCPGovSecurityValidator.validate_government_compliance(compliant_config)
        assert result is True
    
    def test_validate_government_compliance_missing_encryption(self):
        """Test compliance validation with missing encryption."""
        non_compliant_config = {
            'encryption_enabled': False,
            'audit_logging_enabled': True,
            'access_control_enabled': True
        }
        
        result = NCPGovSecurityValidator.validate_government_compliance(non_compliant_config)
        assert result is False
    
    def test_validate_government_compliance_missing_audit_logging(self):
        """Test compliance validation with missing audit logging."""
        non_compliant_config = {
            'encryption_enabled': True,
            'audit_logging_enabled': False,
            'access_control_enabled': True
        }
        
        result = NCPGovSecurityValidator.validate_government_compliance(non_compliant_config)
        assert result is False
    
    def test_validate_government_compliance_missing_access_control(self):
        """Test compliance validation with missing access control."""
        non_compliant_config = {
            'encryption_enabled': True,
            'audit_logging_enabled': True,
            'access_control_enabled': False
        }
        
        result = NCPGovSecurityValidator.validate_government_compliance(non_compliant_config)
        assert result is False
    
    def test_validate_government_compliance_empty_config(self):
        """Test compliance validation with empty config."""
        empty_config = {}
        
        result = NCPGovSecurityValidator.validate_government_compliance(empty_config)
        assert result is False
    
    def test_mask_sensitive_data_basic(self):
        """Test basic sensitive data masking."""
        sensitive_data = {
            'server_name': 'test-server',
            'private_ip': '10.0.1.100',
            'public_ip': '123.456.789.10',
            'access_key': 'AKIA123456789',
            'secret_key': 'secret123456789'
        }
        
        masked_data = NCPGovSecurityValidator.mask_sensitive_data(sensitive_data)
        
        # Non-sensitive data should be preserved
        assert masked_data['server_name'] == 'test-server'
        assert masked_data['public_ip'] == '123.456.789.10'
        
        # Sensitive data should be masked
        assert masked_data['private_ip'] == '***MASKED***'
        assert masked_data['access_key'] == '***MASKED***'
        assert masked_data['secret_key'] == '***MASKED***'
    
    def test_mask_sensitive_data_with_internal_ip(self):
        """Test sensitive data masking including internal IP."""
        sensitive_data = {
            'server_name': 'gov-server',
            'internal_ip': '192.168.1.10',
            'private_ip': '10.0.1.100'
        }
        
        masked_data = NCPGovSecurityValidator.mask_sensitive_data(sensitive_data)
        
        assert masked_data['server_name'] == 'gov-server'
        assert masked_data['internal_ip'] == '***MASKED***'
        assert masked_data['private_ip'] == '***MASKED***'
    
    def test_mask_sensitive_data_no_sensitive_fields(self):
        """Test masking when no sensitive fields are present."""
        non_sensitive_data = {
            'server_name': 'test-server',
            'public_ip': '123.456.789.10',
            'status': 'RUN'
        }
        
        masked_data = NCPGovSecurityValidator.mask_sensitive_data(non_sensitive_data)
        
        # All data should be preserved
        assert masked_data == non_sensitive_data
    
    def test_mask_sensitive_data_preserves_original(self):
        """Test that masking preserves the original data object."""
        original_data = {
            'server_name': 'test-server',
            'private_ip': '10.0.1.100'
        }
        
        masked_data = NCPGovSecurityValidator.mask_sensitive_data(original_data)
        
        # Original should be unchanged
        assert original_data['private_ip'] == '10.0.1.100'
        # Masked should be different
        assert masked_data['private_ip'] == '***MASKED***'


class TestNCPGovAPIError:
    """Test cases for NCPGovAPIError exception class."""
    
    def test_ncpgov_api_error_basic(self):
        """Test basic NCPGovAPIError creation."""
        error = NCPGovAPIError("Government cloud error")
        
        assert str(error) == "Government cloud error"
        assert error.message == "Government cloud error"
        assert error.error_code is None
        assert error.status_code is None
    
    def test_ncpgov_api_error_with_code(self):
        """Test NCPGovAPIError with error code."""
        error = NCPGovAPIError("Access denied", error_code="GOV-25001")
        
        assert error.message == "Access denied"
        assert error.error_code == "GOV-25001"
        assert error.status_code is None
    
    def test_ncpgov_api_error_with_status_code(self):
        """Test NCPGovAPIError with status code."""
        error = NCPGovAPIError("Forbidden", status_code=403)
        
        assert error.message == "Forbidden"
        assert error.error_code is None
        assert error.status_code == 403
    
    def test_ncpgov_api_error_full(self):
        """Test NCPGovAPIError with all parameters."""
        error = NCPGovAPIError(
            "Government compliance violation", 
            error_code="GOV-COMPLIANCE-001", 
            status_code=403
        )
        
        assert error.message == "Government compliance violation"
        assert error.error_code == "GOV-COMPLIANCE-001"
        assert error.status_code == 403


if __name__ == '__main__':
    pytest.main([__file__])