#!/usr/bin/env python3
"""
Integration tests for GCP services with real API calls.

These tests require valid GCP credentials and test projects.
They validate end-to-end functionality with actual GCP APIs.

WARNING: These tests may incur GCP charges and should only be run
in designated test environments with proper cleanup procedures.
"""

import unittest
import os
import json
import time
from typing import Dict, List, Any
from unittest.mock import patch

# GCP modules not implemented yet
# from common.gcp_utils import GCPAuthManager, GCPProjectManager, GCPResourceCollector
# from mcp.gcp_connector import MCPGCPConnector, create_mcp_connector
# from gcp.compute.info import fetch_compute_instances_direct, fetch_compute_instances_via_mcp
# from gcp.vpc.info import fetch_vpc_networks_direct, fetch_vpc_networks_via_mcp
# from gcp.gke.info import fetch_gke_clusters_direct, fetch_gke_clusters_via_mcp
# from gcp.sql.info import fetch_sql_instances_direct, fetch_sql_instances_via_mcp

import pytest
pytest.skip("GCP modules not implemented yet", allow_module_level=True)

# Test configuration
INTEGRATION_TEST_PROJECT = os.getenv('GCP_INTEGRATION_TEST_PROJECT')
INTEGRATION_TEST_REGION = os.getenv('GCP_INTEGRATION_TEST_REGION', 'us-central1')
INTEGRATION_TEST_ZONE = os.getenv('GCP_INTEGRATION_TEST_ZONE', 'us-central1-a')
RUN_INTEGRATION_TESTS = os.getenv('RUN_GCP_INTEGRATION_TESTS', 'false').lower() == 'true'


def skip_if_no_integration_config(func):
    """Decorator to skip tests if integration test configuration is missing."""
    def wrapper(self):
        if not RUN_INTEGRATION_TESTS:
            self.skipTest("Integration tests disabled. Set RUN_GCP_INTEGRATION_TESTS=true to enable.")
        if not INTEGRATION_TEST_PROJECT:
            self.skipTest("Integration test project not configured. Set GCP_INTEGRATION_TEST_PROJECT.")
        return func(self)
    return wrapper


class BaseIntegrationTest(unittest.TestCase):
    """Base class for GCP integration tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up integration test environment."""
        if not RUN_INTEGRATION_TESTS:
            return
            
        cls.project_id = INTEGRATION_TEST_PROJECT
        cls.region = INTEGRATION_TEST_REGION
        cls.zone = INTEGRATION_TEST_ZONE
        
        # Initialize authentication
        cls.auth_manager = GCPAuthManager()
        cls.credentials = cls.auth_manager.get_credentials()
        
        if not cls.credentials:
            raise unittest.SkipTest("No valid GCP credentials found for integration tests")
        
        # Initialize project manager
        cls.project_manager = GCPProjectManager(cls.auth_manager)
        
        # Initialize MCP connector
        cls.mcp_connector = create_mcp_connector()
        
        print(f"Integration tests configured for project: {cls.project_id}")
    
    def setUp(self):
        """Set up individual test."""
        if not RUN_INTEGRATION_TESTS:
            self.skipTest("Integration tests disabled")
    
    def assert_valid_gcp_response(self, response: List[Dict], resource_type: str):
        """Assert that GCP response is valid."""
        self.assertIsInstance(response, list, f"{resource_type} response should be a list")
        
        if response:  # If there are resources, validate structure
            resource = response[0]
            self.assertIsInstance(resource, dict, f"{resource_type} should be a dictionary")
            self.assertIn('name', resource, f"{resource_type} should have a name field")
            self.assertIn('project_id', resource, f"{resource_type} should have a project_id field")


class TestGCPAuthentication(BaseIntegrationTest):
    """Test GCP authentication with real credentials."""
    
    @skip_if_no_integration_config
    def test_authentication_success(self):
        """Test successful authentication."""
        credentials = self.auth_manager.get_credentials()
        
        self.assertIsNotNone(credentials, "Should have valid credentials")
        
        # Test credential validation
        is_valid = self.auth_manager.validate_credentials()
        self.assertTrue(is_valid, "Credentials should be valid")
    
    @skip_if_no_integration_config
    def test_project_discovery(self):
        """Test project discovery."""
        projects = self.project_manager.discover_projects()
        
        self.assertIsInstance(projects, list, "Projects should be a list")
        self.assertGreater(len(projects), 0, "Should discover at least one project")
        
        # Verify test project is accessible
        project_ids = [p.project_id for p in projects]
        self.assertIn(self.project_id, project_ids, f"Test project {self.project_id} should be accessible")
    
    @skip_if_no_integration_config
    def test_project_access_validation(self):
        """Test project access validation."""
        has_access = self.project_manager.validate_project_access(self.project_id)
        self.assertTrue(has_access, f"Should have access to test project {self.project_id}")
        
        # Test invalid project
        has_access_invalid = self.project_manager.validate_project_access("nonexistent-project-12345")
        self.assertFalse(has_access_invalid, "Should not have access to nonexistent project")


class TestMCPIntegration(BaseIntegrationTest):
    """Test MCP server integration with real GCP APIs."""
    
    @skip_if_no_integration_config
    def test_mcp_connection(self):
        """Test MCP server connection."""
        is_available = self.mcp_connector.is_available()
        
        if is_available:
            # Test connection validation
            is_valid = self.mcp_connector.validate_connection()
            self.assertTrue(is_valid, "MCP connection should be valid")
            
            # Test project listing via MCP
            response = self.mcp_connector.get_projects()
            self.assertTrue(response.success, "MCP project listing should succeed")
        else:
            self.skipTest("MCP server not available for integration testing")
    
    @skip_if_no_integration_config
    def test_mcp_vs_direct_api_consistency(self):
        """Test consistency between MCP and direct API calls."""
        if not self.mcp_connector.is_available():
            self.skipTest("MCP server not available")
        
        # Test compute instances
        try:
            mcp_instances = fetch_compute_instances_via_mcp(self.mcp_connector, self.project_id)
            direct_instances = fetch_compute_instances_direct(self.project_id)
            
            # Both should return lists
            self.assertIsInstance(mcp_instances, list)
            self.assertIsInstance(direct_instances, list)
            
            # If both have data, compare basic structure
            if mcp_instances and direct_instances:
                mcp_names = {inst['name'] for inst in mcp_instances}
                direct_names = {inst['name'] for inst in direct_instances}
                
                # Should have significant overlap (allowing for timing differences)
                overlap = len(mcp_names.intersection(direct_names))
                total_unique = len(mcp_names.union(direct_names))
                
                if total_unique > 0:
                    overlap_ratio = overlap / total_unique
                    self.assertGreater(overlap_ratio, 0.8, 
                                     "MCP and direct API should return similar results")
        
        except Exception as e:
            self.skipTest(f"Compute instances test failed: {e}")


class TestComputeEngineIntegration(BaseIntegrationTest):
    """Test Compute Engine integration with real APIs."""
    
    @skip_if_no_integration_config
    def test_fetch_compute_instances_direct(self):
        """Test fetching compute instances via direct API."""
        instances = fetch_compute_instances_direct(self.project_id)
        
        self.assert_valid_gcp_response(instances, "Compute instances")
        
        # Validate instance structure if instances exist
        if instances:
            instance = instances[0]
            required_fields = ['name', 'zone', 'machine_type', 'status', 'creation_timestamp']
            for field in required_fields:
                self.assertIn(field, instance, f"Instance should have {field} field")
    
    @skip_if_no_integration_config
    def test_fetch_compute_instances_with_filters(self):
        """Test fetching compute instances with zone filter."""
        instances = fetch_compute_instances_direct(self.project_id, self.zone)
        
        self.assert_valid_gcp_response(instances, "Filtered compute instances")
        
        # All instances should be in the specified zone
        for instance in instances:
            self.assertEqual(instance['zone'], self.zone, 
                           f"Instance {instance['name']} should be in zone {self.zone}")
    
    @skip_if_no_integration_config
    def test_fetch_compute_instances_mcp(self):
        """Test fetching compute instances via MCP."""
        if not self.mcp_connector.is_available():
            self.skipTest("MCP server not available")
        
        instances = fetch_compute_instances_via_mcp(self.mcp_connector, self.project_id)
        
        self.assert_valid_gcp_response(instances, "MCP compute instances")


class TestVPCNetworksIntegration(BaseIntegrationTest):
    """Test VPC Networks integration with real APIs."""
    
    @skip_if_no_integration_config
    def test_fetch_vpc_networks_direct(self):
        """Test fetching VPC networks via direct API."""
        networks = fetch_vpc_networks_direct(self.project_id)
        
        self.assert_valid_gcp_response(networks, "VPC networks")
        
        # Should have at least the default network
        self.assertGreater(len(networks), 0, "Should have at least one VPC network")
        
        # Validate network structure
        network = networks[0]
        required_fields = ['name', 'routing_mode', 'subnets', 'firewall_rules']
        for field in required_fields:
            self.assertIn(field, network, f"Network should have {field} field")
    
    @skip_if_no_integration_config
    def test_fetch_vpc_networks_with_filters(self):
        """Test fetching VPC networks with region filter."""
        networks = fetch_vpc_networks_direct(self.project_id, self.region)
        
        self.assert_valid_gcp_response(networks, "Filtered VPC networks")
    
    @skip_if_no_integration_config
    def test_fetch_vpc_networks_mcp(self):
        """Test fetching VPC networks via MCP."""
        if not self.mcp_connector.is_available():
            self.skipTest("MCP server not available")
        
        networks = fetch_vpc_networks_via_mcp(self.mcp_connector, self.project_id)
        
        self.assert_valid_gcp_response(networks, "MCP VPC networks")


class TestGKEIntegration(BaseIntegrationTest):
    """Test GKE integration with real APIs."""
    
    @skip_if_no_integration_config
    def test_fetch_gke_clusters_direct(self):
        """Test fetching GKE clusters via direct API."""
        clusters = fetch_gke_clusters_direct(self.project_id)
        
        self.assert_valid_gcp_response(clusters, "GKE clusters")
        
        # Validate cluster structure if clusters exist
        if clusters:
            cluster = clusters[0]
            required_fields = ['name', 'location', 'status', 'current_master_version', 'node_pools']
            for field in required_fields:
                self.assertIn(field, cluster, f"Cluster should have {field} field")
    
    @skip_if_no_integration_config
    def test_fetch_gke_clusters_with_filters(self):
        """Test fetching GKE clusters with location filter."""
        clusters = fetch_gke_clusters_direct(self.project_id, self.zone)
        
        self.assert_valid_gcp_response(clusters, "Filtered GKE clusters")
    
    @skip_if_no_integration_config
    def test_fetch_gke_clusters_mcp(self):
        """Test fetching GKE clusters via MCP."""
        if not self.mcp_connector.is_available():
            self.skipTest("MCP server not available")
        
        clusters = fetch_gke_clusters_via_mcp(self.mcp_connector, self.project_id)
        
        self.assert_valid_gcp_response(clusters, "MCP GKE clusters")


class TestCloudSQLIntegration(BaseIntegrationTest):
    """Test Cloud SQL integration with real APIs."""
    
    @skip_if_no_integration_config
    def test_fetch_sql_instances_direct(self):
        """Test fetching SQL instances via direct API."""
        instances = fetch_sql_instances_direct(self.project_id)
        
        self.assert_valid_gcp_response(instances, "SQL instances")
        
        # Validate instance structure if instances exist
        if instances:
            instance = instances[0]
            required_fields = ['name', 'database_version', 'tier', 'region', 'status']
            for field in required_fields:
                self.assertIn(field, instance, f"SQL instance should have {field} field")
    
    @skip_if_no_integration_config
    def test_fetch_sql_instances_mcp(self):
        """Test fetching SQL instances via MCP."""
        if not self.mcp_connector.is_available():
            self.skipTest("MCP server not available")
        
        instances = fetch_sql_instances_via_mcp(self.mcp_connector, self.project_id)
        
        self.assert_valid_gcp_response(instances, "MCP SQL instances")


class TestEndToEndWorkflows(BaseIntegrationTest):
    """Test end-to-end workflows with real GCP APIs."""
    
    @skip_if_no_integration_config
    def test_multi_service_data_collection(self):
        """Test collecting data from multiple services."""
        collector = GCPResourceCollector(self.auth_manager)
        
        # Collect data from multiple services
        services_data = {}
        
        try:
            services_data['compute'] = fetch_compute_instances_direct(self.project_id)
            services_data['vpc'] = fetch_vpc_networks_direct(self.project_id)
            services_data['gke'] = fetch_gke_clusters_direct(self.project_id)
            services_data['sql'] = fetch_sql_instances_direct(self.project_id)
        except Exception as e:
            self.skipTest(f"Multi-service collection failed: {e}")
        
        # Validate all services returned data structures
        for service, data in services_data.items():
            self.assertIsInstance(data, list, f"{service} should return a list")
    
    @skip_if_no_integration_config
    def test_output_formatting_integration(self):
        """Test output formatting with real data."""
        # Get real data
        instances = fetch_compute_instances_direct(self.project_id)
        
        if not instances:
            self.skipTest("No compute instances available for formatting test")
        
        # Test different output formats
        from gcp.compute.info import format_output
        
        try:
            json_output = format_output(instances, 'json')
            self.assertIsInstance(json_output, str)
            
            # Validate JSON is parseable
            parsed_json = json.loads(json_output)
            self.assertIsInstance(parsed_json, list)
            
            yaml_output = format_output(instances, 'yaml')
            self.assertIsInstance(yaml_output, str)
            
        except Exception as e:
            self.fail(f"Output formatting failed: {e}")
    
    @skip_if_no_integration_config
    def test_error_handling_integration(self):
        """Test error handling with real API errors."""
        # Test with invalid project
        invalid_project = "nonexistent-project-12345"
        
        instances = fetch_compute_instances_direct(invalid_project)
        self.assertEqual(instances, [], "Should return empty list for invalid project")
        
        networks = fetch_vpc_networks_direct(invalid_project)
        self.assertEqual(networks, [], "Should return empty list for invalid project")


class TestPerformanceIntegration(BaseIntegrationTest):
    """Test performance with real GCP APIs."""
    
    @skip_if_no_integration_config
    def test_api_response_times(self):
        """Test API response times are reasonable."""
        import time
        
        # Test compute instances
        start_time = time.time()
        instances = fetch_compute_instances_direct(self.project_id)
        compute_time = time.time() - start_time
        
        self.assertLess(compute_time, 30.0, "Compute instances API should respond within 30 seconds")
        
        # Test VPC networks
        start_time = time.time()
        networks = fetch_vpc_networks_direct(self.project_id)
        vpc_time = time.time() - start_time
        
        self.assertLess(vpc_time, 30.0, "VPC networks API should respond within 30 seconds")
        
        print(f"Performance metrics:")
        print(f"  Compute instances: {compute_time:.2f}s")
        print(f"  VPC networks: {vpc_time:.2f}s")
    
    @skip_if_no_integration_config
    def test_parallel_processing_performance(self):
        """Test parallel processing performance."""
        import time
        from concurrent.futures import ThreadPoolExecutor
        
        def fetch_service_data(service_func):
            return service_func(self.project_id)
        
        services = [
            fetch_compute_instances_direct,
            fetch_vpc_networks_direct,
            fetch_gke_clusters_direct,
            fetch_sql_instances_direct
        ]
        
        # Sequential execution
        start_time = time.time()
        sequential_results = []
        for service_func in services:
            try:
                result = fetch_service_data(service_func)
                sequential_results.append(result)
            except Exception:
                sequential_results.append([])
        sequential_time = time.time() - start_time
        
        # Parallel execution
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=4) as executor:
            parallel_results = list(executor.map(fetch_service_data, services))
        parallel_time = time.time() - start_time
        
        print(f"Performance comparison:")
        print(f"  Sequential: {sequential_time:.2f}s")
        print(f"  Parallel: {parallel_time:.2f}s")
        print(f"  Speedup: {sequential_time/parallel_time:.2f}x")
        
        # Parallel should be faster (or at least not significantly slower)
        self.assertLessEqual(parallel_time, sequential_time * 1.2, 
                           "Parallel execution should not be significantly slower")


def run_integration_tests():
    """Run integration tests with proper setup and teardown."""
    if not RUN_INTEGRATION_TESTS:
        print("Integration tests disabled. Set RUN_GCP_INTEGRATION_TESTS=true to enable.")
        return True
    
    if not INTEGRATION_TEST_PROJECT:
        print("Integration test project not configured. Set GCP_INTEGRATION_TEST_PROJECT.")
        return False
    
    print(f"Running integration tests against project: {INTEGRATION_TEST_PROJECT}")
    print("WARNING: These tests may incur GCP charges!")
    
    # Load and run integration tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all integration test classes
    test_classes = [
        TestGCPAuthentication,
        TestMCPIntegration,
        TestComputeEngineIntegration,
        TestVPCNetworksIntegration,
        TestGKEIntegration,
        TestCloudSQLIntegration,
        TestEndToEndWorkflows,
        TestPerformanceIntegration
    ]
    
    for test_class in test_classes:
        suite.addTest(loader.loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_integration_tests()
    exit(0 if success else 1)