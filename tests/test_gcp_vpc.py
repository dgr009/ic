#!/usr/bin/env python3
"""
Unit tests for GCP VPC Networks service integration.

Tests both MCP and direct API access methods, output formatting,
and error handling scenarios.
"""

import unittest
from unittest.mock import patch, MagicMock, Mock, call
import json
from google.api_core import exceptions as gcp_exceptions

# Import modules to test
from gcp.vpc.info import (
    fetch_vpc_networks_via_mcp,
    fetch_vpc_networks_direct,
    collect_network_details,
    get_subnet_details,
    get_firewall_rules,
    format_table_output,
    format_tree_output,
    format_output
)
from mcp.gcp_connector import MCPResponse


class TestFetchVPCNetworksViaMCP(unittest.TestCase):
    """Test MCP-based VPC networks fetching."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_connector = Mock()
        self.project_id = "test-project"
        self.region_filter = "us-central1"
    
    def test_fetch_networks_success(self):
        """Test successful VPC networks fetching via MCP."""
        mock_networks = [
            {
                "name": "default",
                "description": "Default network",
                "routing_mode": "REGIONAL",
                "subnets": [
                    {
                        "name": "default-subnet",
                        "ip_cidr_range": "10.0.0.0/24",
                        "region": "us-central1"
                    }
                ],
                "firewall_rules": [
                    {
                        "name": "default-allow-internal",
                        "direction": "INGRESS",
                        "priority": 65534
                    }
                ]
            },
            {
                "name": "custom-vpc",
                "description": "Custom VPC network",
                "routing_mode": "GLOBAL",
                "subnets": [],
                "firewall_rules": []
            }
        ]
        
        self.mock_connector.execute_gcp_query.return_value = MCPResponse(
            success=True,
            data={"networks": mock_networks}
        )
        
        result = fetch_vpc_networks_via_mcp(
            self.mock_connector,
            self.project_id,
            self.region_filter
        )
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "default")
        self.assertEqual(result[1]["name"], "custom-vpc")
        
        self.mock_connector.execute_gcp_query.assert_called_once_with(
            'vpc',
            'list_networks',
            {
                'project_id': self.project_id,
                'region_filter': self.region_filter
            }
        )
    
    def test_fetch_networks_mcp_failure(self):
        """Test MCP failure handling."""
        self.mock_connector.execute_gcp_query.return_value = MCPResponse(
            success=False,
            error="MCP server error"
        )
        
        result = fetch_vpc_networks_via_mcp(
            self.mock_connector,
            self.project_id
        )
        
        self.assertEqual(result, [])
    
    def test_fetch_networks_exception(self):
        """Test exception handling during MCP call."""
        self.mock_connector.execute_gcp_query.side_effect = Exception("Connection error")
        
        result = fetch_vpc_networks_via_mcp(
            self.mock_connector,
            self.project_id
        )
        
        self.assertEqual(result, [])


class TestFetchVPCNetworksDirect(unittest.TestCase):
    """Test direct API VPC networks fetching."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.region_filter = "us-central1"
    
    @patch('gcp.vpc.info.create_gcp_client')
    @patch('gcp.vpc.info.GCPAuthManager')
    def test_fetch_networks_success(self, mock_auth_manager, mock_create_client):
        """Test successful direct API VPC networks fetching."""
        # Mock authentication
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = Mock()
        
        # Mock networks client
        mock_networks_client = Mock()
        mock_subnets_client = Mock()
        mock_firewalls_client = Mock()
        
        def client_side_effect(service_name, version, project_id):
            if 'networks' in str(version):
                return mock_networks_client
            elif 'subnetworks' in str(version):
                return mock_subnets_client
            elif 'firewalls' in str(version):
                return mock_firewalls_client
            return Mock()
        
        mock_create_client.side_effect = client_side_effect
        
        # Mock network response
        mock_network = Mock()
        mock_network.name = "default"
        mock_network.description = "Default network"
        mock_network.routing_config = Mock()
        mock_network.routing_config.routing_mode = "REGIONAL"
        mock_network.auto_create_subnetworks = True
        mock_network.peerings = []
        mock_network.creation_timestamp = "2023-01-01T00:00:00Z"
        
        mock_networks_client.list.return_value = [mock_network]
        
        # Mock subnets response
        mock_subnet = Mock()
        mock_subnet.name = "default-subnet"
        mock_subnet.ip_cidr_range = "10.0.0.0/24"
        mock_subnet.region = "regions/us-central1"
        mock_subnet.network = f"projects/{self.project_id}/global/networks/default"
        
        mock_subnets_client.aggregated_list.return_value = {
            f"regions/{self.region_filter}": Mock(subnetworks=[mock_subnet])
        }
        
        # Mock firewall rules response
        mock_firewall = Mock()
        mock_firewall.name = "default-allow-internal"
        mock_firewall.direction = "INGRESS"
        mock_firewall.priority = 65534
        mock_firewall.network = f"projects/{self.project_id}/global/networks/default"
        
        mock_firewalls_client.list.return_value = [mock_firewall]
        
        result = fetch_vpc_networks_direct(self.project_id, self.region_filter)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "default")
        self.assertEqual(result[0]["routing_mode"], "REGIONAL")
    
    @patch('gcp.vpc.info.create_gcp_client')
    @patch('gcp.vpc.info.GCPAuthManager')
    def test_fetch_networks_auth_failure(self, mock_auth_manager, mock_create_client):
        """Test authentication failure handling."""
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = None
        
        result = fetch_vpc_networks_direct(self.project_id)
        
        self.assertEqual(result, [])
    
    @patch('gcp.vpc.info.create_gcp_client')
    @patch('gcp.vpc.info.GCPAuthManager')
    def test_fetch_networks_api_exception(self, mock_auth_manager, mock_create_client):
        """Test API exception handling."""
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = Mock()
        
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.list.side_effect = gcp_exceptions.PermissionDenied("Access denied")
        
        result = fetch_vpc_networks_direct(self.project_id)
        
        self.assertEqual(result, [])


class TestCollectNetworkDetails(unittest.TestCase):
    """Test network details collection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.mock_network = Mock()
        self.mock_network.name = "test-network"
        self.mock_network.description = "Test network"
        self.mock_network.routing_config = Mock()
        self.mock_network.routing_config.routing_mode = "GLOBAL"
        self.mock_network.auto_create_subnetworks = False
        self.mock_network.peerings = []
        self.mock_network.creation_timestamp = "2023-01-01T00:00:00Z"
        self.mock_network.self_link = f"projects/{self.project_id}/global/networks/test-network"
    
    def test_collect_network_details_mcp(self):
        """Test collecting network details via MCP."""
        mock_data_source = Mock()
        
        result = collect_network_details(mock_data_source, self.project_id, self.mock_network)
        
        self.assertEqual(result["name"], "test-network")
        self.assertEqual(result["project_id"], self.project_id)
        self.assertEqual(result["description"], "Test network")
        self.assertEqual(result["routing_mode"], "GLOBAL")
        self.assertFalse(result["auto_create_subnetworks"])
        self.assertEqual(len(result["peerings"]), 0)
    
    def test_collect_network_details_with_peerings(self):
        """Test collecting network details with peerings."""
        mock_peering = Mock()
        mock_peering.name = "test-peering"
        mock_peering.network = "projects/other-project/global/networks/other-network"
        mock_peering.state = "ACTIVE"
        
        self.mock_network.peerings = [mock_peering]
        
        mock_data_source = Mock()
        
        result = collect_network_details(mock_data_source, self.project_id, self.mock_network)
        
        self.assertEqual(len(result["peerings"]), 1)
        self.assertEqual(result["peerings"][0]["name"], "test-peering")
        self.assertEqual(result["peerings"][0]["state"], "ACTIVE")


class TestGetSubnetDetails(unittest.TestCase):
    """Test subnet details retrieval."""
    
    @patch('gcp.vpc.info.create_gcp_client')
    def test_get_subnet_details_mcp(self, mock_create_client):
        """Test getting subnet details via MCP."""
        mock_data_source = Mock()
        mock_data_source.execute_gcp_query.return_value = MCPResponse(
            success=True,
            data={
                "subnet": {
                    "name": "test-subnet",
                    "ip_cidr_range": "10.0.0.0/24",
                    "region": "us-central1",
                    "gateway_address": "10.0.0.1",
                    "private_ip_google_access": True
                }
            }
        )
        
        result = get_subnet_details(
            mock_data_source,
            "test-project",
            "us-central1",
            "test-subnet"
        )
        
        self.assertEqual(result["name"], "test-subnet")
        self.assertEqual(result["ip_cidr_range"], "10.0.0.0/24")
        self.assertTrue(result["private_ip_google_access"])
    
    @patch('gcp.vpc.info.create_gcp_client')
    def test_get_subnet_details_direct(self, mock_create_client):
        """Test getting subnet details via direct API."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_subnet = Mock()
        mock_subnet.name = "test-subnet"
        mock_subnet.ip_cidr_range = "10.0.0.0/24"
        mock_subnet.region = "regions/us-central1"
        mock_subnet.gateway_address = "10.0.0.1"
        mock_subnet.private_ip_google_access = True
        
        mock_client.get.return_value = mock_subnet
        
        result = get_subnet_details(
            mock_client,
            "test-project",
            "us-central1",
            "test-subnet"
        )
        
        self.assertEqual(result["name"], "test-subnet")
        self.assertEqual(result["ip_cidr_range"], "10.0.0.0/24")
        self.assertEqual(result["region"], "us-central1")
    
    @patch('gcp.vpc.info.create_gcp_client')
    def test_get_subnet_details_exception(self, mock_create_client):
        """Test subnet details retrieval exception handling."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.get.side_effect = gcp_exceptions.NotFound("Subnet not found")
        
        result = get_subnet_details(
            mock_client,
            "test-project",
            "us-central1",
            "nonexistent-subnet"
        )
        
        self.assertEqual(result, {})


class TestGetFirewallRules(unittest.TestCase):
    """Test firewall rules retrieval."""
    
    @patch('gcp.vpc.info.create_gcp_client')
    def test_get_firewall_rules_mcp(self, mock_create_client):
        """Test getting firewall rules via MCP."""
        mock_data_source = Mock()
        mock_data_source.execute_gcp_query.return_value = MCPResponse(
            success=True,
            data={
                "firewall_rules": [
                    {
                        "name": "allow-internal",
                        "direction": "INGRESS",
                        "priority": 65534,
                        "source_ranges": ["10.0.0.0/8"],
                        "allowed": [{"IPProtocol": "tcp", "ports": ["22", "80"]}]
                    }
                ]
            }
        )
        
        result = get_firewall_rules(
            mock_data_source,
            "test-project",
            "test-network"
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "allow-internal")
        self.assertEqual(result[0]["direction"], "INGRESS")
    
    @patch('gcp.vpc.info.create_gcp_client')
    def test_get_firewall_rules_direct(self, mock_create_client):
        """Test getting firewall rules via direct API."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_rule = Mock()
        mock_rule.name = "allow-internal"
        mock_rule.direction = "INGRESS"
        mock_rule.priority = 65534
        mock_rule.network = "projects/test-project/global/networks/test-network"
        mock_rule.source_ranges = ["10.0.0.0/8"]
        mock_rule.allowed = [Mock(I_p_protocol="tcp", ports=["22", "80"])]
        mock_rule.denied = []
        
        mock_client.list.return_value = [mock_rule]
        
        result = get_firewall_rules(
            mock_client,
            "test-project",
            "test-network"
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "allow-internal")
        self.assertEqual(result[0]["priority"], 65534)
    
    @patch('gcp.vpc.info.create_gcp_client')
    def test_get_firewall_rules_exception(self, mock_create_client):
        """Test firewall rules retrieval exception handling."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.list.side_effect = gcp_exceptions.PermissionDenied("Access denied")
        
        result = get_firewall_rules(
            mock_client,
            "test-project",
            "test-network"
        )
        
        self.assertEqual(result, [])


class TestOutputFormatting(unittest.TestCase):
    """Test output formatting functions."""
    
    def setUp(self):
        """Set up test data."""
        self.test_networks = [
            {
                "name": "default",
                "project_id": "test-project",
                "description": "Default network",
                "routing_mode": "REGIONAL",
                "auto_create_subnetworks": True,
                "subnets": [
                    {
                        "name": "default-subnet",
                        "ip_cidr_range": "10.0.0.0/24",
                        "region": "us-central1"
                    }
                ],
                "firewall_rules": [
                    {
                        "name": "default-allow-internal",
                        "direction": "INGRESS",
                        "priority": 65534
                    }
                ],
                "peerings": [],
                "creation_timestamp": "2023-01-01T00:00:00Z"
            },
            {
                "name": "custom-vpc",
                "project_id": "test-project",
                "description": "Custom VPC network",
                "routing_mode": "GLOBAL",
                "auto_create_subnetworks": False,
                "subnets": [],
                "firewall_rules": [],
                "peerings": [],
                "creation_timestamp": "2023-01-02T00:00:00Z"
            }
        ]
    
    @patch('gcp.vpc.info.console')
    def test_format_table_output(self, mock_console):
        """Test table output formatting."""
        format_table_output(self.test_networks)
        
        # Verify console.print was called
        mock_console.print.assert_called()
        
        # Get the table that was printed
        call_args = mock_console.print.call_args_list
        table_calls = [call for call in call_args if len(call[0]) > 0 and hasattr(call[0][0], 'add_row')]
        
        self.assertTrue(len(table_calls) > 0)
    
    @patch('gcp.vpc.info.console')
    def test_format_tree_output(self, mock_console):
        """Test tree output formatting."""
        format_tree_output(self.test_networks)
        
        # Verify console.print was called
        mock_console.print.assert_called()
    
    def test_format_output_json(self):
        """Test JSON output formatting."""
        result = format_output(self.test_networks, 'json')
        
        # Should return JSON string
        self.assertIsInstance(result, str)
        
        # Should be valid JSON
        parsed = json.loads(result)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["name"], "default")
    
    def test_format_output_yaml(self):
        """Test YAML output formatting."""
        result = format_output(self.test_networks, 'yaml')
        
        # Should return YAML string
        self.assertIsInstance(result, str)
        self.assertIn("name: default", result)
        self.assertIn("routing_mode: REGIONAL", result)
    
    @patch('gcp.vpc.info.format_table_output')
    def test_format_output_table(self, mock_format_table):
        """Test table output formatting."""
        format_output(self.test_networks, 'table')
        
        mock_format_table.assert_called_once_with(self.test_networks)
    
    @patch('gcp.vpc.info.format_tree_output')
    def test_format_output_tree(self, mock_format_tree):
        """Test tree output formatting."""
        format_output(self.test_networks, 'tree')
        
        mock_format_tree.assert_called_once_with(self.test_networks)
    
    def test_format_output_invalid_format(self):
        """Test invalid output format handling."""
        with self.assertRaises(ValueError):
            format_output(self.test_networks, 'invalid')


if __name__ == '__main__':
    unittest.main()