#!/usr/bin/env python3
"""
Unit tests for GCP Google Kubernetes Engine (GKE) service integration.

Tests both MCP and direct API access methods, output formatting,
and error handling scenarios.
"""

import unittest
from unittest.mock import patch, MagicMock, Mock, call
import json
from google.api_core import exceptions as gcp_exceptions

# Import modules to test
from gcp.gke.info import (
    fetch_gke_clusters_via_mcp,
    fetch_gke_clusters_direct,
    collect_cluster_details,
    get_node_pool_details,
    format_table_output,
    format_tree_output,
    format_output
)
from mcp.gcp_connector import MCPResponse


class TestFetchGKEClustersViaMCP(unittest.TestCase):
    """Test MCP-based GKE clusters fetching."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_connector = Mock()
        self.project_id = "test-project"
        self.zone_filter = "us-central1-a"
    
    def test_fetch_clusters_success(self):
        """Test successful GKE clusters fetching via MCP."""
        mock_clusters = [
            {
                "name": "test-cluster-1",
                "location": "us-central1-a",
                "status": "RUNNING",
                "current_master_version": "1.27.3-gke.100",
                "node_pools": [
                    {
                        "name": "default-pool",
                        "initial_node_count": 3,
                        "config": {
                            "machine_type": "e2-medium",
                            "disk_size_gb": 100
                        }
                    }
                ],
                "network": "projects/test-project/global/networks/default",
                "subnetwork": "projects/test-project/regions/us-central1/subnetworks/default"
            },
            {
                "name": "test-cluster-2",
                "location": "us-central1",
                "status": "PROVISIONING",
                "current_master_version": "1.27.3-gke.100",
                "node_pools": [],
                "network": "projects/test-project/global/networks/custom-vpc",
                "subnetwork": "projects/test-project/regions/us-central1/subnetworks/custom-subnet"
            }
        ]
        
        self.mock_connector.execute_gcp_query.return_value = MCPResponse(
            success=True,
            data={"clusters": mock_clusters}
        )
        
        result = fetch_gke_clusters_via_mcp(
            self.mock_connector,
            self.project_id,
            self.zone_filter
        )
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "test-cluster-1")
        self.assertEqual(result[1]["name"], "test-cluster-2")
        
        self.mock_connector.execute_gcp_query.assert_called_once_with(
            'gke',
            'list_clusters',
            {
                'project_id': self.project_id,
                'zone_filter': self.zone_filter
            }
        )
    
    def test_fetch_clusters_mcp_failure(self):
        """Test MCP failure handling."""
        self.mock_connector.execute_gcp_query.return_value = MCPResponse(
            success=False,
            error="MCP server error"
        )
        
        result = fetch_gke_clusters_via_mcp(
            self.mock_connector,
            self.project_id
        )
        
        self.assertEqual(result, [])
    
    def test_fetch_clusters_exception(self):
        """Test exception handling during MCP call."""
        self.mock_connector.execute_gcp_query.side_effect = Exception("Connection error")
        
        result = fetch_gke_clusters_via_mcp(
            self.mock_connector,
            self.project_id
        )
        
        self.assertEqual(result, [])


class TestFetchGKEClustersDirect(unittest.TestCase):
    """Test direct API GKE clusters fetching."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.zone_filter = "us-central1-a"
    
    @patch('gcp.gke.info.create_gcp_client')
    @patch('gcp.gke.info.GCPAuthManager')
    def test_fetch_clusters_success(self, mock_auth_manager, mock_create_client):
        """Test successful direct API GKE clusters fetching."""
        # Mock authentication
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = Mock()
        
        # Mock container client
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        # Mock cluster response
        mock_cluster = Mock()
        mock_cluster.name = "test-cluster"
        mock_cluster.location = "us-central1-a"
        mock_cluster.status = "RUNNING"
        mock_cluster.current_master_version = "1.27.3-gke.100"
        mock_cluster.network = "projects/test-project/global/networks/default"
        mock_cluster.subnetwork = "projects/test-project/regions/us-central1/subnetworks/default"
        mock_cluster.cluster_ipv4_cidr = "10.0.0.0/14"
        mock_cluster.services_ipv4_cidr = "10.4.0.0/19"
        mock_cluster.initial_cluster_version = "1.27.3-gke.100"
        mock_cluster.endpoint = "34.123.45.67"
        mock_cluster.create_time = Mock()
        mock_cluster.create_time.seconds = 1672531200  # 2023-01-01
        
        # Mock node pools
        mock_node_pool = Mock()
        mock_node_pool.name = "default-pool"
        mock_node_pool.initial_node_count = 3
        mock_node_pool.config = Mock()
        mock_node_pool.config.machine_type = "e2-medium"
        mock_node_pool.config.disk_size_gb = 100
        mock_node_pool.config.oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        mock_node_pool.autoscaling = Mock()
        mock_node_pool.autoscaling.enabled = True
        mock_node_pool.autoscaling.min_node_count = 1
        mock_node_pool.autoscaling.max_node_count = 10
        mock_node_pool.status = "RUNNING"
        
        mock_cluster.node_pools = [mock_node_pool]
        
        # Mock addons config
        mock_cluster.addons_config = Mock()
        mock_cluster.addons_config.http_load_balancing = Mock()
        mock_cluster.addons_config.http_load_balancing.disabled = False
        mock_cluster.addons_config.horizontal_pod_autoscaling = Mock()
        mock_cluster.addons_config.horizontal_pod_autoscaling.disabled = False
        
        mock_client.list_clusters.return_value = Mock(clusters=[mock_cluster])
        
        result = fetch_gke_clusters_direct(self.project_id, self.zone_filter)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "test-cluster")
        self.assertEqual(result[0]["status"], "RUNNING")
        self.assertEqual(len(result[0]["node_pools"]), 1)
    
    @patch('gcp.gke.info.create_gcp_client')
    @patch('gcp.gke.info.GCPAuthManager')
    def test_fetch_clusters_auth_failure(self, mock_auth_manager, mock_create_client):
        """Test authentication failure handling."""
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = None
        
        result = fetch_gke_clusters_direct(self.project_id)
        
        self.assertEqual(result, [])
    
    @patch('gcp.gke.info.create_gcp_client')
    @patch('gcp.gke.info.GCPAuthManager')
    def test_fetch_clusters_api_exception(self, mock_auth_manager, mock_create_client):
        """Test API exception handling."""
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = Mock()
        
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.list_clusters.side_effect = gcp_exceptions.PermissionDenied("Access denied")
        
        result = fetch_gke_clusters_direct(self.project_id)
        
        self.assertEqual(result, [])


class TestCollectClusterDetails(unittest.TestCase):
    """Test cluster details collection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.mock_cluster = Mock()
        self.mock_cluster.name = "test-cluster"
        self.mock_cluster.location = "us-central1-a"
        self.mock_cluster.status = "RUNNING"
        self.mock_cluster.current_master_version = "1.27.3-gke.100"
        self.mock_cluster.network = "projects/test-project/global/networks/default"
        self.mock_cluster.subnetwork = "projects/test-project/regions/us-central1/subnetworks/default"
        self.mock_cluster.cluster_ipv4_cidr = "10.0.0.0/14"
        self.mock_cluster.services_ipv4_cidr = "10.4.0.0/19"
        self.mock_cluster.endpoint = "34.123.45.67"
        self.mock_cluster.create_time = Mock()
        self.mock_cluster.create_time.seconds = 1672531200
        
        # Mock node pools
        mock_node_pool = Mock()
        mock_node_pool.name = "default-pool"
        mock_node_pool.initial_node_count = 3
        mock_node_pool.status = "RUNNING"
        self.mock_cluster.node_pools = [mock_node_pool]
        
        # Mock addons config
        self.mock_cluster.addons_config = Mock()
        self.mock_cluster.addons_config.http_load_balancing = Mock()
        self.mock_cluster.addons_config.http_load_balancing.disabled = False
    
    def test_collect_cluster_details_mcp(self):
        """Test collecting cluster details via MCP."""
        mock_data_source = Mock()
        
        result = collect_cluster_details(mock_data_source, self.project_id, self.mock_cluster)
        
        self.assertEqual(result["name"], "test-cluster")
        self.assertEqual(result["project_id"], self.project_id)
        self.assertEqual(result["location"], "us-central1-a")
        self.assertEqual(result["status"], "RUNNING")
        self.assertEqual(result["current_master_version"], "1.27.3-gke.100")
        self.assertEqual(result["network"], "default")
        self.assertEqual(result["subnetwork"], "default")
        self.assertEqual(result["cluster_ipv4_cidr"], "10.0.0.0/14")
        self.assertEqual(result["endpoint"], "34.123.45.67")
        self.assertEqual(len(result["node_pools"]), 1)
    
    def test_collect_cluster_details_no_node_pools(self):
        """Test collecting cluster details without node pools."""
        self.mock_cluster.node_pools = []
        
        mock_data_source = Mock()
        
        result = collect_cluster_details(mock_data_source, self.project_id, self.mock_cluster)
        
        self.assertEqual(len(result["node_pools"]), 0)
    
    def test_collect_cluster_details_no_addons(self):
        """Test collecting cluster details without addons config."""
        self.mock_cluster.addons_config = None
        
        mock_data_source = Mock()
        
        result = collect_cluster_details(mock_data_source, self.project_id, self.mock_cluster)
        
        self.assertEqual(result["addons_config"], {})


class TestGetNodePoolDetails(unittest.TestCase):
    """Test node pool details retrieval."""
    
    @patch('gcp.gke.info.create_gcp_client')
    def test_get_node_pool_details_mcp(self, mock_create_client):
        """Test getting node pool details via MCP."""
        mock_data_source = Mock()
        mock_data_source.execute_gcp_query.return_value = MCPResponse(
            success=True,
            data={
                "node_pools": [
                    {
                        "name": "default-pool",
                        "initial_node_count": 3,
                        "config": {
                            "machine_type": "e2-medium",
                            "disk_size_gb": 100,
                            "oauth_scopes": ["https://www.googleapis.com/auth/cloud-platform"]
                        },
                        "autoscaling": {
                            "enabled": True,
                            "min_node_count": 1,
                            "max_node_count": 10
                        },
                        "status": "RUNNING"
                    }
                ]
            }
        )
        
        result = get_node_pool_details(
            mock_data_source,
            "test-project",
            "test-cluster"
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "default-pool")
        self.assertEqual(result[0]["initial_node_count"], 3)
        self.assertTrue(result[0]["autoscaling"]["enabled"])
    
    @patch('gcp.gke.info.create_gcp_client')
    def test_get_node_pool_details_direct(self, mock_create_client):
        """Test getting node pool details via direct API."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_node_pool = Mock()
        mock_node_pool.name = "default-pool"
        mock_node_pool.initial_node_count = 3
        mock_node_pool.config = Mock()
        mock_node_pool.config.machine_type = "e2-medium"
        mock_node_pool.config.disk_size_gb = 100
        mock_node_pool.config.oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        mock_node_pool.autoscaling = Mock()
        mock_node_pool.autoscaling.enabled = True
        mock_node_pool.autoscaling.min_node_count = 1
        mock_node_pool.autoscaling.max_node_count = 10
        mock_node_pool.status = "RUNNING"
        
        mock_client.list_node_pools.return_value = Mock(node_pools=[mock_node_pool])
        
        result = get_node_pool_details(
            mock_client,
            "test-project",
            "test-cluster"
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "default-pool")
        self.assertEqual(result[0]["config"]["machine_type"], "e2-medium")
        self.assertEqual(result[0]["status"], "RUNNING")
    
    @patch('gcp.gke.info.create_gcp_client')
    def test_get_node_pool_details_exception(self, mock_create_client):
        """Test node pool details retrieval exception handling."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.list_node_pools.side_effect = gcp_exceptions.NotFound("Cluster not found")
        
        result = get_node_pool_details(
            mock_client,
            "test-project",
            "nonexistent-cluster"
        )
        
        self.assertEqual(result, [])


class TestOutputFormatting(unittest.TestCase):
    """Test output formatting functions."""
    
    def setUp(self):
        """Set up test data."""
        self.test_clusters = [
            {
                "name": "test-cluster-1",
                "project_id": "test-project",
                "location": "us-central1-a",
                "status": "RUNNING",
                "current_master_version": "1.27.3-gke.100",
                "network": "default",
                "subnetwork": "default",
                "cluster_ipv4_cidr": "10.0.0.0/14",
                "services_ipv4_cidr": "10.4.0.0/19",
                "endpoint": "34.123.45.67",
                "node_pools": [
                    {
                        "name": "default-pool",
                        "initial_node_count": 3,
                        "config": {
                            "machine_type": "e2-medium",
                            "disk_size_gb": 100
                        },
                        "autoscaling": {
                            "enabled": True,
                            "min_node_count": 1,
                            "max_node_count": 10
                        },
                        "status": "RUNNING"
                    }
                ],
                "addons_config": {
                    "http_load_balancing": {"disabled": False},
                    "horizontal_pod_autoscaling": {"disabled": False}
                },
                "creation_timestamp": "2023-01-01T00:00:00Z"
            },
            {
                "name": "test-cluster-2",
                "project_id": "test-project",
                "location": "us-central1",
                "status": "PROVISIONING",
                "current_master_version": "1.27.3-gke.100",
                "network": "custom-vpc",
                "subnetwork": "custom-subnet",
                "cluster_ipv4_cidr": "10.8.0.0/14",
                "services_ipv4_cidr": "10.12.0.0/19",
                "endpoint": "35.123.45.67",
                "node_pools": [],
                "addons_config": {},
                "creation_timestamp": "2023-01-02T00:00:00Z"
            }
        ]
    
    @patch('gcp.gke.info.console')
    def test_format_table_output(self, mock_console):
        """Test table output formatting."""
        format_table_output(self.test_clusters)
        
        # Verify console.print was called
        mock_console.print.assert_called()
        
        # Get the table that was printed
        call_args = mock_console.print.call_args_list
        table_calls = [call for call in call_args if len(call[0]) > 0 and hasattr(call[0][0], 'add_row')]
        
        self.assertTrue(len(table_calls) > 0)
    
    @patch('gcp.gke.info.console')
    def test_format_tree_output(self, mock_console):
        """Test tree output formatting."""
        format_tree_output(self.test_clusters)
        
        # Verify console.print was called
        mock_console.print.assert_called()
    
    def test_format_output_json(self):
        """Test JSON output formatting."""
        result = format_output(self.test_clusters, 'json')
        
        # Should return JSON string
        self.assertIsInstance(result, str)
        
        # Should be valid JSON
        parsed = json.loads(result)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["name"], "test-cluster-1")
    
    def test_format_output_yaml(self):
        """Test YAML output formatting."""
        result = format_output(self.test_clusters, 'yaml')
        
        # Should return YAML string
        self.assertIsInstance(result, str)
        self.assertIn("name: test-cluster-1", result)
        self.assertIn("status: RUNNING", result)
    
    @patch('gcp.gke.info.format_table_output')
    def test_format_output_table(self, mock_format_table):
        """Test table output formatting."""
        format_output(self.test_clusters, 'table')
        
        mock_format_table.assert_called_once_with(self.test_clusters)
    
    @patch('gcp.gke.info.format_tree_output')
    def test_format_output_tree(self, mock_format_tree):
        """Test tree output formatting."""
        format_output(self.test_clusters, 'tree')
        
        mock_format_tree.assert_called_once_with(self.test_clusters)
    
    def test_format_output_invalid_format(self):
        """Test invalid output format handling."""
        with self.assertRaises(ValueError):
            format_output(self.test_clusters, 'invalid')


if __name__ == '__main__':
    unittest.main()