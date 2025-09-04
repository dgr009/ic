#!/usr/bin/env python3
"""
Unit tests for GCP Cloud SQL service integration.

Tests both MCP and direct API access methods, output formatting,
and error handling scenarios.
"""

import unittest
from unittest.mock import patch, MagicMock, Mock, call
import json
from google.api_core import exceptions as gcp_exceptions

# Import modules to test
from gcp.sql.info import (
    fetch_sql_instances_via_mcp,
    fetch_sql_instances_direct,
    collect_instance_details,
    get_instance_replicas,
    get_backup_configuration,
    format_table_output,
    format_tree_output,
    format_output
)
from mcp.gcp_connector import MCPResponse


class TestFetchSQLInstancesViaMCP(unittest.TestCase):
    """Test MCP-based SQL instances fetching."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_connector = Mock()
        self.project_id = "test-project"
    
    def test_fetch_instances_success(self):
        """Test successful SQL instances fetching via MCP."""
        mock_instances = [
            {
                "name": "test-instance-1",
                "database_version": "POSTGRES_14",
                "tier": "db-f1-micro",
                "region": "us-central1",
                "status": "RUNNABLE",
                "ip_addresses": [
                    {"type": "PRIMARY", "ip_address": "34.123.45.67"},
                    {"type": "PRIVATE", "ip_address": "10.0.0.5"}
                ],
                "backup_configuration": {
                    "enabled": True,
                    "start_time": "03:00"
                }
            },
            {
                "name": "test-instance-2",
                "database_version": "MYSQL_8_0",
                "tier": "db-n1-standard-1",
                "region": "us-east1",
                "status": "STOPPED",
                "ip_addresses": [
                    {"type": "PRIMARY", "ip_address": "35.123.45.67"}
                ],
                "backup_configuration": {
                    "enabled": False
                }
            }
        ]
        
        self.mock_connector.execute_gcp_query.return_value = MCPResponse(
            success=True,
            data={"instances": mock_instances}
        )
        
        result = fetch_sql_instances_via_mcp(
            self.mock_connector,
            self.project_id
        )
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "test-instance-1")
        self.assertEqual(result[1]["name"], "test-instance-2")
        
        self.mock_connector.execute_gcp_query.assert_called_once_with(
            'sql',
            'list_instances',
            {'project_id': self.project_id}
        )
    
    def test_fetch_instances_mcp_failure(self):
        """Test MCP failure handling."""
        self.mock_connector.execute_gcp_query.return_value = MCPResponse(
            success=False,
            error="MCP server error"
        )
        
        result = fetch_sql_instances_via_mcp(
            self.mock_connector,
            self.project_id
        )
        
        self.assertEqual(result, [])
    
    def test_fetch_instances_exception(self):
        """Test exception handling during MCP call."""
        self.mock_connector.execute_gcp_query.side_effect = Exception("Connection error")
        
        result = fetch_sql_instances_via_mcp(
            self.mock_connector,
            self.project_id
        )
        
        self.assertEqual(result, [])


class TestFetchSQLInstancesDirect(unittest.TestCase):
    """Test direct API SQL instances fetching."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
    
    @patch('gcp.sql.info.create_gcp_client')
    @patch('gcp.sql.info.GCPAuthManager')
    def test_fetch_instances_success(self, mock_auth_manager, mock_create_client):
        """Test successful direct API SQL instances fetching."""
        # Mock authentication
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = Mock()
        
        # Mock SQL client
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        # Mock instance response
        mock_instance = Mock()
        mock_instance.name = "test-instance"
        mock_instance.database_version = "POSTGRES_14"
        mock_instance.tier = "db-f1-micro"
        mock_instance.region = "us-central1"
        mock_instance.state = "RUNNABLE"
        mock_instance.connection_name = f"{self.project_id}:us-central1:test-instance"
        
        # Mock IP addresses
        mock_ip_primary = Mock()
        mock_ip_primary.type = "PRIMARY"
        mock_ip_primary.ip_address = "34.123.45.67"
        mock_ip_private = Mock()
        mock_ip_private.type = "PRIVATE"
        mock_ip_private.ip_address = "10.0.0.5"
        mock_instance.ip_addresses = [mock_ip_primary, mock_ip_private]
        
        # Mock backup configuration
        mock_instance.backup_configuration = Mock()
        mock_instance.backup_configuration.enabled = True
        mock_instance.backup_configuration.start_time = "03:00"
        mock_instance.backup_configuration.point_in_time_recovery_enabled = True
        
        # Mock maintenance window
        mock_instance.maintenance_window = Mock()
        mock_instance.maintenance_window.hour = 4
        mock_instance.maintenance_window.day = 7
        mock_instance.maintenance_window.update_track = "stable"
        
        # Mock settings
        mock_instance.settings = Mock()
        mock_instance.settings.availability_type = "ZONAL"
        mock_instance.settings.pricing_plan = "PER_USE"
        
        mock_client.list.return_value = Mock(items=[mock_instance])
        
        result = fetch_sql_instances_direct(self.project_id)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "test-instance")
        self.assertEqual(result[0]["database_version"], "POSTGRES_14")
        self.assertEqual(result[0]["status"], "RUNNABLE")
    
    @patch('gcp.sql.info.create_gcp_client')
    @patch('gcp.sql.info.GCPAuthManager')
    def test_fetch_instances_auth_failure(self, mock_auth_manager, mock_create_client):
        """Test authentication failure handling."""
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = None
        
        result = fetch_sql_instances_direct(self.project_id)
        
        self.assertEqual(result, [])
    
    @patch('gcp.sql.info.create_gcp_client')
    @patch('gcp.sql.info.GCPAuthManager')
    def test_fetch_instances_api_exception(self, mock_auth_manager, mock_create_client):
        """Test API exception handling."""
        mock_auth = Mock()
        mock_auth_manager.return_value = mock_auth
        mock_auth.get_credentials.return_value = Mock()
        
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.list.side_effect = gcp_exceptions.PermissionDenied("Access denied")
        
        result = fetch_sql_instances_direct(self.project_id)
        
        self.assertEqual(result, [])


class TestCollectInstanceDetails(unittest.TestCase):
    """Test instance details collection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_id = "test-project"
        self.mock_instance = Mock()
        self.mock_instance.name = "test-instance"
        self.mock_instance.database_version = "POSTGRES_14"
        self.mock_instance.tier = "db-f1-micro"
        self.mock_instance.region = "us-central1"
        self.mock_instance.state = "RUNNABLE"
        self.mock_instance.connection_name = f"{self.project_id}:us-central1:test-instance"
        
        # Mock IP addresses
        mock_ip_primary = Mock()
        mock_ip_primary.type = "PRIMARY"
        mock_ip_primary.ip_address = "34.123.45.67"
        self.mock_instance.ip_addresses = [mock_ip_primary]
        
        # Mock backup configuration
        self.mock_instance.backup_configuration = Mock()
        self.mock_instance.backup_configuration.enabled = True
        self.mock_instance.backup_configuration.start_time = "03:00"
        
        # Mock maintenance window
        self.mock_instance.maintenance_window = Mock()
        self.mock_instance.maintenance_window.hour = 4
        self.mock_instance.maintenance_window.day = 7
        
        # Mock settings
        self.mock_instance.settings = Mock()
        self.mock_instance.settings.availability_type = "ZONAL"
    
    def test_collect_instance_details_mcp(self):
        """Test collecting instance details via MCP."""
        mock_data_source = Mock()
        
        result = collect_instance_details(mock_data_source, self.project_id, self.mock_instance)
        
        self.assertEqual(result["name"], "test-instance")
        self.assertEqual(result["project_id"], self.project_id)
        self.assertEqual(result["database_version"], "POSTGRES_14")
        self.assertEqual(result["tier"], "db-f1-micro")
        self.assertEqual(result["region"], "us-central1")
        self.assertEqual(result["status"], "RUNNABLE")
        self.assertEqual(result["connection_name"], f"{self.project_id}:us-central1:test-instance")
        self.assertEqual(len(result["ip_addresses"]), 1)
        self.assertTrue(result["backup_configuration"]["enabled"])
        self.assertFalse(result["high_availability"])  # ZONAL = False
    
    def test_collect_instance_details_high_availability(self):
        """Test collecting instance details with high availability."""
        self.mock_instance.settings.availability_type = "REGIONAL"
        
        mock_data_source = Mock()
        
        result = collect_instance_details(mock_data_source, self.project_id, self.mock_instance)
        
        self.assertTrue(result["high_availability"])  # REGIONAL = True
    
    def test_collect_instance_details_no_backup_config(self):
        """Test collecting instance details without backup configuration."""
        self.mock_instance.backup_configuration = None
        
        mock_data_source = Mock()
        
        result = collect_instance_details(mock_data_source, self.project_id, self.mock_instance)
        
        self.assertEqual(result["backup_configuration"], {})


class TestGetInstanceReplicas(unittest.TestCase):
    """Test instance replicas retrieval."""
    
    @patch('gcp.sql.info.create_gcp_client')
    def test_get_instance_replicas_mcp(self, mock_create_client):
        """Test getting instance replicas via MCP."""
        mock_data_source = Mock()
        mock_data_source.execute_gcp_query.return_value = MCPResponse(
            success=True,
            data={
                "replicas": [
                    {
                        "name": "test-instance-replica-1",
                        "region": "us-east1",
                        "status": "RUNNABLE"
                    },
                    {
                        "name": "test-instance-replica-2",
                        "region": "europe-west1",
                        "status": "RUNNABLE"
                    }
                ]
            }
        )
        
        result = get_instance_replicas(
            mock_data_source,
            "test-project",
            "test-instance"
        )
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "test-instance-replica-1")
        self.assertEqual(result[1]["name"], "test-instance-replica-2")
    
    @patch('gcp.sql.info.create_gcp_client')
    def test_get_instance_replicas_direct(self, mock_create_client):
        """Test getting instance replicas via direct API."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_replica = Mock()
        mock_replica.name = "test-instance-replica-1"
        mock_replica.region = "us-east1"
        mock_replica.state = "RUNNABLE"
        mock_replica.master_instance_name = "test-instance"
        
        mock_client.list.return_value = Mock(items=[mock_replica])
        
        result = get_instance_replicas(
            mock_client,
            "test-project",
            "test-instance"
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "test-instance-replica-1")
        self.assertEqual(result[0]["region"], "us-east1")
    
    @patch('gcp.sql.info.create_gcp_client')
    def test_get_instance_replicas_exception(self, mock_create_client):
        """Test replicas retrieval exception handling."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.list.side_effect = gcp_exceptions.NotFound("Instance not found")
        
        result = get_instance_replicas(
            mock_client,
            "test-project",
            "nonexistent-instance"
        )
        
        self.assertEqual(result, [])


class TestGetBackupConfiguration(unittest.TestCase):
    """Test backup configuration retrieval."""
    
    @patch('gcp.sql.info.create_gcp_client')
    def test_get_backup_configuration_mcp(self, mock_create_client):
        """Test getting backup configuration via MCP."""
        mock_data_source = Mock()
        mock_data_source.execute_gcp_query.return_value = MCPResponse(
            success=True,
            data={
                "backup_configuration": {
                    "enabled": True,
                    "start_time": "03:00",
                    "point_in_time_recovery_enabled": True,
                    "backup_retention_settings": {
                        "retained_backups": 7
                    }
                }
            }
        )
        
        result = get_backup_configuration(
            mock_data_source,
            "test-project",
            "test-instance"
        )
        
        self.assertTrue(result["enabled"])
        self.assertEqual(result["start_time"], "03:00")
        self.assertTrue(result["point_in_time_recovery_enabled"])
        self.assertEqual(result["backup_retention_settings"]["retained_backups"], 7)
    
    @patch('gcp.sql.info.create_gcp_client')
    def test_get_backup_configuration_direct(self, mock_create_client):
        """Test getting backup configuration via direct API."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        mock_instance = Mock()
        mock_instance.backup_configuration = Mock()
        mock_instance.backup_configuration.enabled = True
        mock_instance.backup_configuration.start_time = "03:00"
        mock_instance.backup_configuration.point_in_time_recovery_enabled = True
        
        mock_client.get.return_value = mock_instance
        
        result = get_backup_configuration(
            mock_client,
            "test-project",
            "test-instance"
        )
        
        self.assertTrue(result["enabled"])
        self.assertEqual(result["start_time"], "03:00")
        self.assertTrue(result["point_in_time_recovery_enabled"])
    
    @patch('gcp.sql.info.create_gcp_client')
    def test_get_backup_configuration_exception(self, mock_create_client):
        """Test backup configuration retrieval exception handling."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.get.side_effect = gcp_exceptions.NotFound("Instance not found")
        
        result = get_backup_configuration(
            mock_client,
            "test-project",
            "nonexistent-instance"
        )
        
        self.assertEqual(result, {})


class TestOutputFormatting(unittest.TestCase):
    """Test output formatting functions."""
    
    def setUp(self):
        """Set up test data."""
        self.test_instances = [
            {
                "name": "test-instance-1",
                "project_id": "test-project",
                "database_version": "POSTGRES_14",
                "tier": "db-f1-micro",
                "region": "us-central1",
                "status": "RUNNABLE",
                "ip_addresses": [
                    {"type": "PRIMARY", "ip_address": "34.123.45.67"},
                    {"type": "PRIVATE", "ip_address": "10.0.0.5"}
                ],
                "backup_configuration": {
                    "enabled": True,
                    "start_time": "03:00"
                },
                "maintenance_window": {
                    "hour": 4,
                    "day": 7
                },
                "high_availability": True,
                "read_replicas": ["test-instance-1-replica"],
                "connection_name": "test-project:us-central1:test-instance-1"
            },
            {
                "name": "test-instance-2",
                "project_id": "test-project",
                "database_version": "MYSQL_8_0",
                "tier": "db-n1-standard-1",
                "region": "us-east1",
                "status": "STOPPED",
                "ip_addresses": [
                    {"type": "PRIMARY", "ip_address": "35.123.45.67"}
                ],
                "backup_configuration": {
                    "enabled": False
                },
                "maintenance_window": {
                    "hour": 2,
                    "day": 1
                },
                "high_availability": False,
                "read_replicas": [],
                "connection_name": "test-project:us-east1:test-instance-2"
            }
        ]
    
    @patch('gcp.sql.info.console')
    def test_format_table_output(self, mock_console):
        """Test table output formatting."""
        format_table_output(self.test_instances)
        
        # Verify console.print was called
        mock_console.print.assert_called()
        
        # Get the table that was printed
        call_args = mock_console.print.call_args_list
        table_calls = [call for call in call_args if len(call[0]) > 0 and hasattr(call[0][0], 'add_row')]
        
        self.assertTrue(len(table_calls) > 0)
    
    @patch('gcp.sql.info.console')
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
        self.assertEqual(parsed[0]["name"], "test-instance-1")
    
    def test_format_output_yaml(self):
        """Test YAML output formatting."""
        result = format_output(self.test_instances, 'yaml')
        
        # Should return YAML string
        self.assertIsInstance(result, str)
        self.assertIn("name: test-instance-1", result)
        self.assertIn("database_version: POSTGRES_14", result)
    
    @patch('gcp.sql.info.format_table_output')
    def test_format_output_table(self, mock_format_table):
        """Test table output formatting."""
        format_output(self.test_instances, 'table')
        
        mock_format_table.assert_called_once_with(self.test_instances)
    
    @patch('gcp.sql.info.format_tree_output')
    def test_format_output_tree(self, mock_format_tree):
        """Test tree output formatting."""
        format_output(self.test_instances, 'tree')
        
        mock_format_tree.assert_called_once_with(self.test_instances)
    
    def test_format_output_invalid_format(self):
        """Test invalid output format handling."""
        with self.assertRaises(ValueError):
            format_output(self.test_instances, 'invalid')


if __name__ == '__main__':
    unittest.main()