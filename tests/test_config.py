#!/usr/bin/env python3
"""
Test configuration and utilities for GCP services integration tests.

Provides common test configuration, fixtures, and utilities.
"""

import os
import tempfile
import json
from unittest.mock import Mock, patch
from typing import Dict, Any, List
from contextlib import contextmanager

# Test environment configuration
TEST_PROJECT_ID = "test-project-12345"
TEST_REGION = "us-central1"
TEST_ZONE = "us-central1-a"
TEST_BILLING_ACCOUNT = "012345-678901-ABCDEF"

# Mock credentials for testing
MOCK_SERVICE_ACCOUNT_KEY = {
    "type": "service_account",
    "project_id": TEST_PROJECT_ID,
    "private_key_id": "key123",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK_KEY\n-----END PRIVATE KEY-----\n",
    "client_email": f"test@{TEST_PROJECT_ID}.iam.gserviceaccount.com",
    "client_id": "123456789",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
}


class TestEnvironment:
    """Test environment configuration and utilities."""
    
    @staticmethod
    @contextmanager
    def mock_gcp_environment():
        """Context manager for mocking GCP environment variables."""
        env_vars = {
            'GCP_PROJECTS': TEST_PROJECT_ID,
            'GCP_DEFAULT_PROJECT': TEST_PROJECT_ID,
            'GCP_REGIONS': TEST_REGION,
            'GCP_ZONES': TEST_ZONE,
            'GCP_SERVICE_ACCOUNT_KEY': json.dumps(MOCK_SERVICE_ACCOUNT_KEY),
            'MCP_GCP_ENABLED': 'true',
            'MCP_GCP_ENDPOINT': 'http://localhost:8080/gcp',
            'GCP_PREFER_MCP': 'true'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            yield
    
    @staticmethod
    @contextmanager
    def mock_service_account_file():
        """Context manager for creating temporary service account file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(MOCK_SERVICE_ACCOUNT_KEY, f)
            temp_file = f.name
        
        try:
            with patch.dict(os.environ, {'GCP_SERVICE_ACCOUNT_KEY_PATH': temp_file}):
                yield temp_file
        finally:
            os.unlink(temp_file)
    
    @staticmethod
    @contextmanager
    def mock_mcp_disabled():
        """Context manager for testing with MCP disabled."""
        env_vars = {
            'MCP_GCP_ENABLED': 'false',
            'GCP_PREFER_MCP': 'false'
        }
        
        with patch.dict(os.environ, env_vars):
            yield


class MockGCPClients:
    """Factory for creating mock GCP client objects."""
    
    @staticmethod
    def create_mock_compute_client():
        """Create mock Compute Engine client."""
        mock_client = Mock()
        
        # Mock instances client methods
        mock_client.list.return_value = []
        mock_client.get.return_value = Mock()
        mock_client.aggregated_list.return_value = {}
        
        return mock_client
    
    @staticmethod
    def create_mock_container_client():
        """Create mock Container (GKE) client."""
        mock_client = Mock()
        
        # Mock container client methods
        mock_client.list_clusters.return_value = Mock(clusters=[])
        mock_client.get_cluster.return_value = Mock()
        mock_client.list_node_pools.return_value = Mock(node_pools=[])
        
        return mock_client
    
    @staticmethod
    def create_mock_sql_client():
        """Create mock SQL client."""
        mock_client = Mock()
        
        # Mock SQL client methods
        mock_client.list.return_value = Mock(items=[])
        mock_client.get.return_value = Mock()
        mock_client.patch.return_value = Mock()
        
        return mock_client
    
    @staticmethod
    def create_mock_storage_client():
        """Create mock Storage client."""
        mock_client = Mock()
        
        # Mock Storage client methods
        mock_client.list_buckets.return_value = []
        mock_client.get_bucket.return_value = Mock()
        mock_client.bucket.return_value = Mock()
        
        return mock_client
    
    @staticmethod
    def create_mock_functions_client():
        """Create mock Cloud Functions client."""
        mock_client = Mock()
        
        # Mock Functions client methods
        mock_client.list_functions.return_value = Mock(functions=[])
        mock_client.get_function.return_value = Mock()
        
        return mock_client
    
    @staticmethod
    def create_mock_run_client():
        """Create mock Cloud Run client."""
        mock_client = Mock()
        
        # Mock Run client methods
        mock_client.list_services.return_value = Mock(items=[])
        mock_client.get_service.return_value = Mock()
        mock_client.list_revisions.return_value = Mock(items=[])
        
        return mock_client
    
    @staticmethod
    def create_mock_billing_client():
        """Create mock Billing client."""
        mock_client = Mock()
        
        # Mock Billing client methods
        mock_client.list_billing_accounts.return_value = []
        mock_client.get_billing_account.return_value = Mock()
        mock_client.list_project_billing_info.return_value = []
        
        return mock_client


class TestDataFixtures:
    """Common test data fixtures."""
    
    @staticmethod
    def get_sample_projects() -> List[Dict[str, Any]]:
        """Get sample project data."""
        return [
            {
                "project_id": TEST_PROJECT_ID,
                "project_name": "Test Project",
                "project_number": "123456789",
                "lifecycle_state": "ACTIVE",
                "labels": {"env": "test", "team": "backend"}
            },
            {
                "project_id": f"{TEST_PROJECT_ID}-dev",
                "project_name": "Test Project Dev",
                "project_number": "987654321",
                "lifecycle_state": "ACTIVE",
                "labels": {"env": "dev", "team": "backend"}
            }
        ]
    
    @staticmethod
    def get_sample_error_responses() -> Dict[str, Any]:
        """Get sample error responses for testing."""
        return {
            "permission_denied": {
                "code": 403,
                "message": "The caller does not have permission",
                "status": "PERMISSION_DENIED"
            },
            "not_found": {
                "code": 404,
                "message": "The requested resource was not found",
                "status": "NOT_FOUND"
            },
            "quota_exceeded": {
                "code": 429,
                "message": "Quota exceeded",
                "status": "RESOURCE_EXHAUSTED"
            },
            "service_unavailable": {
                "code": 503,
                "message": "Service temporarily unavailable",
                "status": "UNAVAILABLE"
            }
        }


class TestAssertions:
    """Custom test assertions for GCP services."""
    
    @staticmethod
    def assert_valid_gcp_resource(resource: Dict[str, Any], required_fields: List[str]):
        """Assert that a resource has required GCP fields."""
        for field in required_fields:
            assert field in resource, f"Required field '{field}' missing from resource"
            assert resource[field] is not None, f"Required field '{field}' is None"
    
    @staticmethod
    def assert_valid_compute_instance(instance: Dict[str, Any]):
        """Assert that an instance has valid Compute Engine fields."""
        required_fields = [
            "name", "project_id", "zone", "machine_type", "status",
            "internal_ip", "external_ip", "creation_timestamp"
        ]
        TestAssertions.assert_valid_gcp_resource(instance, required_fields)
        
        # Additional Compute Engine specific assertions
        assert instance["status"] in ["RUNNING", "STOPPED", "TERMINATED", "PROVISIONING"]
        assert "." in instance["internal_ip"] or instance["internal_ip"] == "N/A"
    
    @staticmethod
    def assert_valid_vpc_network(network: Dict[str, Any]):
        """Assert that a network has valid VPC fields."""
        required_fields = [
            "name", "project_id", "routing_mode", "auto_create_subnetworks",
            "subnets", "firewall_rules", "peerings"
        ]
        TestAssertions.assert_valid_gcp_resource(network, required_fields)
        
        # Additional VPC specific assertions
        assert network["routing_mode"] in ["REGIONAL", "GLOBAL"]
        assert isinstance(network["subnets"], list)
        assert isinstance(network["firewall_rules"], list)
    
    @staticmethod
    def assert_valid_gke_cluster(cluster: Dict[str, Any]):
        """Assert that a cluster has valid GKE fields."""
        required_fields = [
            "name", "project_id", "location", "status", "current_master_version",
            "network", "subnetwork", "node_pools"
        ]
        TestAssertions.assert_valid_gcp_resource(cluster, required_fields)
        
        # Additional GKE specific assertions
        assert cluster["status"] in ["RUNNING", "PROVISIONING", "STOPPING", "ERROR"]
        assert isinstance(cluster["node_pools"], list)
    
    @staticmethod
    def assert_valid_sql_instance(instance: Dict[str, Any]):
        """Assert that an instance has valid Cloud SQL fields."""
        required_fields = [
            "name", "project_id", "database_version", "tier", "region",
            "status", "ip_addresses", "connection_name"
        ]
        TestAssertions.assert_valid_gcp_resource(instance, required_fields)
        
        # Additional Cloud SQL specific assertions
        assert instance["status"] in ["RUNNABLE", "STOPPED", "SUSPENDED", "PENDING_CREATE"]
        assert isinstance(instance["ip_addresses"], list)


class TestPerformanceMetrics:
    """Performance testing utilities."""
    
    def __init__(self):
        self.metrics = {}
    
    def start_timer(self, operation: str):
        """Start timing an operation."""
        import time
        self.metrics[operation] = {"start": time.time()}
    
    def end_timer(self, operation: str):
        """End timing an operation."""
        import time
        if operation in self.metrics:
            self.metrics[operation]["end"] = time.time()
            self.metrics[operation]["duration"] = (
                self.metrics[operation]["end"] - self.metrics[operation]["start"]
            )
    
    def get_duration(self, operation: str) -> float:
        """Get duration of an operation in seconds."""
        return self.metrics.get(operation, {}).get("duration", 0.0)
    
    def assert_performance_threshold(self, operation: str, max_seconds: float):
        """Assert that an operation completed within threshold."""
        duration = self.get_duration(operation)
        assert duration <= max_seconds, (
            f"Operation '{operation}' took {duration:.2f}s, "
            f"exceeding threshold of {max_seconds}s"
        )


# Global test configuration
TEST_CONFIG = {
    "project_id": TEST_PROJECT_ID,
    "region": TEST_REGION,
    "zone": TEST_ZONE,
    "billing_account": TEST_BILLING_ACCOUNT,
    "performance_thresholds": {
        "api_call": 5.0,  # seconds
        "data_collection": 10.0,  # seconds
        "output_formatting": 2.0  # seconds
    },
    "retry_settings": {
        "max_attempts": 3,
        "initial_delay": 1.0,
        "max_delay": 10.0
    }
}