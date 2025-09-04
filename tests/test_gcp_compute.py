#!/usr/bin/env python3
"""
Unit tests for GCP Compute Engine service integration.

Tests both MCP and direct API access methods, output formatting,
and error handling scenarios.
"""

import unittest
from unittest.mock import patch, MagicMock, Mock, call
import json
from google.api_core import exceptions as gcp_exceptions
from google.cloud.compute_v1.types import Instance, Zone

# Import modules to test
from gcp.compute.info import (
    fetch_compute_instances_via_mcp,
    fetch_compute_instances_direct,
    collect_instance_details,
    get_instance_metadata,
    format_table_output,
    format_tree_output,
    format_output
)
from mcp.gcp_connector import MCPResponse


class TestFetchComputeInstancesViaMCP(unittest.TestCase):
    """Test MCP-based compute instance fetching."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_connector = Mock()
        self.project_id = "test-project"
        self.zone_filter = "us-central1-a"
    
    def test_fetch_instances_success(self):
        """Test successful instance fetching via MCP."""
        mock_instances = [
            {
                "name": "instance-1",
                "zone": "us-central1-a",
                "machine_type": "n1-standard-1",
                "status": "RUNNING"
            },
            {
                "name": "instance-2", 
                "zone": "us-central1-b",
                "machine_type": "n1-standard-2",
                "status": "STOPPED"
            }
        ]
        
        self.mock_connector.execute_gcp_query.return_value = MCPResponse(
            success=True,
            data={"instances": mock_instances}
        )
        
        result = fetch_compute_instances_via_mcp(
            self.mock_connector,
            self.project_id,
            self.zone_filter
        )
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "instance-1")
        self.assertEqual(result[1]["name"], "instance-2")
        
        self.mock_connector.execute_gcp_query.assert_called_once_with(
            'compute',
            'list_instances',
            {
                'project_id': self.project_id,
                'zone_filter': self.zone_filter
            }
        )
    
    def test_fetch_instances_mcp_failure(self):
        """Test MCP failure handling."""
        self.mock_connector.execute_gcp_query.return_value = MCPResponse(
            success=False,
            error="MCP server error"
        )
        
        result = fetch_compute_instances_via_mcp(
            self.mock_connector,
            self.project_id
        )
        
        self.assertEqual(result, [])
    
    def test_fetch_instances_exception(self):
        """Test exception handling during MCP call."""
        self.mock_connector.execute_gcp_query.side_effect = Exception("Connection error")
        
        result = fetch_compute_instances_via_mcp(
            self.mock_connector,
            self.project_id
        )
        
        self.assertEqual(result, [])


class TestFetchComputeInstancesDirect(unittest.TestCase):
    """Test direct API compute instance fetching."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.zone_filter = "us-central1-a"
    
    @patch('gcp.compute.info.create_gcp_client')
    @patch('gcp.compute.info.GCPAuthManager')
    def test_fetch_instances_success(self, mock_auth_manager, mock_create_client):
        """Test successful direct API instance fetching."""
        # Mock authentication
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = Mock()
        
        # Mock instances client
        mock_instances_client = Mock()
        mock_zones_client = Mock()
        
        def client_side_effect(service_name, version, project_id):
            if service_name == 'compute' and 'instances' in str(version):
                return mock_instances_client
            elif service_name == 'compute' and 'zones' in str(version):
                return mock_zones_client
            return Mock()
        
        mock_create_client.side_effect = client_side_effect
        
        # Mock zones response
        mock_zone = Mock()
        mock_zone.name = "us-central1-a"
        mock_zones_client.list.return_value = [mock_zone]
        
        # Mock instances response
        mock_instance = Mock()
        mock_instance.name = "test-instance"
        mock_instance.zone = "zones/us-central1-a"
        mock_instance.machine_type = "machine-types/n1-standard-1"
        mock_instance.status = "RUNNING"
        mock_instance.network_interfaces = []
        mock_instance.disks = []
        mock_instance.labels = {}
        mock_instance.metadata = Mock()
        mock_instance.metadata.items = []
        mock_instance.creation_timestamp = "2023-01-01T00:00:00Z"
        
        mock_instances_client.list.return_value = [mock_instance]
        
        result = fetch_compute_instances_direct(self.project_id, self.zone_filter)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "test-instance")
        self.assertEqual(result[0]["status"], "RUNNING")
    
    @patch('gcp.compute.info.create_gcp_client')
    @patch('gcp.compute.info.GCPAuthManager')
    def test_fetch_instances_auth_failure(self, mock_auth_manager, mock_create_client):
        """Test authentication failure handling."""
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = None
        
        result = fetch_compute_instances_direct(self.project_id)
        
        self.assertEqual(result, [])
    
    @patch('gcp.compute.info.create_gcp_client')
    @patch('gcp.compute.info.GCPAuthManager')
    def test_fetch_instances_api_exception(self, mock_auth_manager, mock_create_client):
        """Test API exception handling."""
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = Mock()
        
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.list.side_effect = gcp_exceptions.PermissionDenied("Access denied")
        
        result = fetch_compute_instances_direct(self.project_id)
        
        self.assertEqual(result, [])


class TestCollectInstanceDetails(unittest.TestCase):
    """Test instance details collection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.mock_instance = Mock()
        self.mock_instance.name = "test-instance"
        self.mock_instance.zone = "zones/us-central1-a"
        self.mock_instance.machine_type = "machine-types/n1-standard-1"
        self.mock_instance.status = "RUNNING"
        self.mock_instance.creation_timestamp = "2023-01-01T00:00:00Z"
        self.mock_instance.labels = {"env": "test"}
        self.mock_instance.metadata = Mock()
        self.mock_instance.metadata.items = [
            Mock(key="startup-script", value="#!/bin/bash\necho 'Hello'")
        ]
        
        # Mock network interfaces
        mock_network_interface = Mock()
        mock_network_interface.network = "projects/test-project/global/networks/default"
        mock_network_interface.subnetwork = "projects/test-project/regions/us-central1/subnetworks/default"
        mock_access_config = Mock()
        mock_access_config.nat_i_p = "34.123.45.67"
        mock_network_interface.access_configs = [mock_access_config]
        mock_network_interface.network_i_p = "10.0.0.2"
        self.mock_instance.network_interfaces = [mock_network_interface]
        
        # Mock disks
        mock_disk = Mock()
        mock_disk.source = "projects/test-project/zones/us-central1-a/disks/test-disk"
        mock_disk.boot = True
        mock_disk.auto_delete = True
        self.mock_instance.disks = [mock_disk]
    
    def test_collect_instance_details_mcp(self):
        """Test collecting instance details via MCP."""
        mock_data_source = Mock()
        
        result = collect_instance_details(mock_data_source, self.project_id, self.mock_instance)
        
        self.assertEqual(result["name"], "test-instance")
        self.assertEqual(result["project_id"], self.project_id)
        self.assertEqual(result["zone"], "us-central1-a")
        self.assertEqual(result["machine_type"], "n1-standard-1")
        self.assertEqual(result["status"], "RUNNING")
        self.assertEqual(result["labels"], {"env": "test"})
        self.assertEqual(len(result["network_interfaces"]), 1)
        self.assertEqual(len(result["disks"]), 1)
        self.assertEqual(result["external_ip"], "34.123.45.67")
        self.assertEqual(result["internal_ip"], "10.0.0.2")
    
    def test_collect_instance_details_no_external_ip(self):
        """Test collecting instance details without external IP."""
        # Remove external IP
        self.mock_instance.network_interfaces[0].access_configs = []
        
        mock_data_source = Mock()
        
        result = collect_instance_details(mock_data_source, self.project_id, self.mock_instance)
        
        self.assertEqual(result["external_ip"], "N/A")
        self.assertEqual(result["internal_ip"], "10.0.0.2")
    
    def test_collect_instance_details_no_network_interfaces(self):
        """Test collecting instance details without network interfaces."""
        self.mock_instance.network_interfaces = []
        
        mock_data_source = Mock()
        
        result = collect_instance_details(mock_data_source, self.project_id, self.mock_instance)
        
        self.assertEqual(result["external_ip"], "N/A")
        self.assertEqual(result["internal_ip"], "N/A")
        self.assertEqual(len(result["network_interfaces"]), 0)


class TestGetInstanceMetadata(unittest.TestCase):
    """Test instance metadata retrieval."""
    
    @patch('gcp.compute.info.create_gcp_client')
    def test_get_instance_metadata_mcp(self, mock_create_client):
        """Test getting instance metadata via MCP."""
        mock_data_source = Mock()
        mock_data_source.execute_gcp_query.return_value = MCPResponse(
            success=True,
            data={
                "metadata": {
                    "startup-script": "#!/bin/bash\necho 'Hello'",
                    "ssh-keys": "user:ssh-rsa AAAAB3..."
                }
            }
        )
        
        result = get_instance_metadata(
            mock_data_source,
            "test-project",
            "us-central1-a",
            "test-instance"
        )
        
        self.assertEqual(len(result), 2)
        self.assertIn("startup-script", result)
        self.assertIn("ssh-keys", result)
    
    @patch('gcp.compute.info.create_gcp_client')
    def test_get_instance_metadata_direct(self, mock_create_client):
        """Test getting instance metadata via direct API."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_instance = Mock()
        mock_instance.metadata = Mock()
        mock_instance.metadata.items = [
            Mock(key="startup-script", value="#!/bin/bash\necho 'Hello'")
        ]
        
        mock_client.get.return_value = mock_instance
        
        result = get_instance_metadata(
            mock_client,
            "test-project", 
            "us-central1-a",
            "test-instance"
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result["startup-script"], "#!/bin/bash\necho 'Hello'")
    
    @patch('gcp.compute.info.create_gcp_client')
    def test_get_instance_metadata_exception(self, mock_create_client):
        """Test metadata retrieval exception handling."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.get.side_effect = gcp_exceptions.NotFound("Instance not found")
        
        result = get_instance_metadata(
            mock_client,
            "test-project",
            "us-central1-a", 
            "nonexistent-instance"
        )
        
        self.assertEqual(result, {})


class TestOutputFormatting(unittest.TestCase):
    """Test output formatting functions."""
    
    def setUp(self):
        """Set up test data."""
        self.test_instances = [
            {
                "name": "instance-1",
                "project_id": "test-project",
                "zone": "us-central1-a",
                "machine_type": "n1-standard-1",
                "status": "RUNNING",
                "internal_ip": "10.0.0.2",
                "external_ip": "34.123.45.67",
                "creation_timestamp": "2023-01-01T00:00:00Z",
                "labels": {"env": "prod"}
            },
            {
                "name": "instance-2",
                "project_id": "test-project",
                "zone": "us-central1-b", 
                "machine_type": "n1-standard-2",
                "status": "STOPPED",
                "internal_ip": "10.0.0.3",
                "external_ip": "N/A",
                "creation_timestamp": "2023-01-02T00:00:00Z",
                "labels": {"env": "dev"}
            }
        ]
    
    @patch('gcp.compute.info.console')
    def test_format_table_output(self, mock_console):
        """Test table output formatting."""
        format_table_output(self.test_instances)
        
        # Verify console.print was called
        mock_console.print.assert_called()
        
        # Get the table that was printed
        call_args = mock_console.print.call_args_list
        table_calls = [call for call in call_args if len(call[0]) > 0 and hasattr(call[0][0], 'add_row')]
        
        self.assertTrue(len(table_calls) > 0)
    
    @patch('gcp.compute.info.console')
    def test_format_tree_output(self, mock_console):
        """Test tree output formatting."""
        format_tree_output(self.test_instances)
        
        # Verify console.print was called
        mock_console.print.assert_called()
    
    def test_format_output_json(self):
        """Test JSON output formatting."""
        result = format_output(self.test_instances, 'json')
        
        # Should return JSON string
        self.assertIsInstance(result, str)
        
        # Should be valid JSON
        parsed = json.loads(result)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["name"], "instance-1")
    
    def test_format_output_yaml(self):
        """Test YAML output formatting."""
        result = format_output(self.test_instances, 'yaml')
        
        # Should return YAML string
        self.assertIsInstance(result, str)
        self.assertIn("name: instance-1", result)
        self.assertIn("status: RUNNING", result)
    
    @patch('gcp.compute.info.format_table_output')
    def test_format_output_table(self, mock_format_table):
        """Test table output formatting."""
        format_output(self.test_instances, 'table')
        
        mock_format_table.assert_called_once_with(self.test_instances)
    
    @patch('gcp.compute.info.format_tree_output')
    def test_format_output_tree(self, mock_format_tree):
        """Test tree output formatting."""
        format_output(self.test_instances, 'tree')
        
        mock_format_tree.assert_called_once_with(self.test_instances)
    
    def test_format_output_invalid_format(self):
        """Test invalid output format handling."""
        with self.assertRaises(ValueError):
            format_output(self.test_instances, 'invalid')


class TestMCPIntegration(unittest.TestCase):
    """Test MCP integration availability and fallback."""
    
    @patch('gcp.compute.info.MCP_AVAILABLE', True)
    def test_mcp_available(self):
        """Test when MCP is available."""
        # Import should work when MCP_AVAILABLE is True
        from gcp.compute.info import MCP_AVAILABLE
        self.assertTrue(MCP_AVAILABLE)
    
    @patch('gcp.compute.info.MCP_AVAILABLE', False)
    def test_mcp_not_available(self):
        """Test when MCP is not available."""
        from gcp.compute.info import MCP_AVAILABLE
        self.assertFalse(MCP_AVAILABLE)


if __name__ == '__main__':
    unittest.main()