#!/usr/bin/env python3
"""
Unit tests for MCP GCP Connector.

Tests MCP server integration, fallback mechanisms, and error handling.
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import os
import json
from dataclasses import asdict

from mcp.gcp_connector import MCPGCPConnector, MCPResponse, MCPGCPService, create_mcp_connector


class TestMCPResponse(unittest.TestCase):
    """Test MCPResponse dataclass."""
    
    def test_mcp_response_creation(self):
        """Test MCPResponse creation with all fields."""
        response = MCPResponse(
            success=True,
            data={"test": "data"},
            error=None,
            metadata={"source": "test"}
        )
        
        self.assertTrue(response.success)
        self.assertEqual(response.data, {"test": "data"})
        self.assertIsNone(response.error)
        self.assertEqual(response.metadata, {"source": "test"})
    
    def test_mcp_response_error(self):
        """Test MCPResponse creation with error."""
        response = MCPResponse(
            success=False,
            data=None,
            error="Test error",
            metadata={"fallback_required": True}
        )
        
        self.assertFalse(response.success)
        self.assertIsNone(response.data)
        self.assertEqual(response.error, "Test error")
        self.assertTrue(response.metadata["fallback_required"])


class TestMCPGCPConnector(unittest.TestCase):
    """Test MCP GCP Connector functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear environment variables for clean testing
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()
        
        self.connector = MCPGCPConnector()
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.env_patcher.stop()
    
    def test_init_default_values(self):
        """Test connector initialization with default values."""
        connector = MCPGCPConnector()
        
        self.assertEqual(connector.mcp_endpoint, 'http://localhost:8080/gcp')
        self.assertEqual(connector.timeout, 30)
        self.assertTrue(connector.enabled)
        self.assertTrue(connector.prefer_mcp)
        self.assertFalse(connector._connection_validated)
    
    @patch.dict(os.environ, {
        'MCP_GCP_ENDPOINT': 'http://test:9000/gcp',
        'MCP_GCP_ENABLED': 'false',
        'GCP_PREFER_MCP': 'false'
    })
    def test_init_with_env_vars(self):
        """Test connector initialization with environment variables."""
        connector = MCPGCPConnector()
        
        self.assertEqual(connector.mcp_endpoint, 'http://test:9000/gcp')
        self.assertFalse(connector.enabled)
        self.assertFalse(connector.prefer_mcp)
    
    def test_init_with_custom_values(self):
        """Test connector initialization with custom values."""
        connector = MCPGCPConnector(
            mcp_endpoint='http://custom:8080/gcp',
            timeout=60
        )
        
        self.assertEqual(connector.mcp_endpoint, 'http://custom:8080/gcp')
        self.assertEqual(connector.timeout, 60)
    
    def test_is_available_disabled(self):
        """Test is_available when MCP is disabled."""
        self.connector.enabled = False
        
        result = self.connector.is_available()
        
        self.assertFalse(result)
    
    def test_is_available_prefer_mcp_false(self):
        """Test is_available when prefer_mcp is False."""
        self.connector.prefer_mcp = False
        
        result = self.connector.is_available()
        
        self.assertFalse(result)
    
    def test_is_available_already_validated(self):
        """Test is_available when connection already validated."""
        self.connector._connection_validated = True
        
        result = self.connector.is_available()
        
        self.assertTrue(result)
    
    @patch.object(MCPGCPConnector, '_make_request')
    def test_is_available_health_check_success(self, mock_make_request):
        """Test is_available with successful health check."""
        mock_make_request.return_value = MCPResponse(success=True, data={"status": "healthy"})
        
        result = self.connector.is_available()
        
        self.assertTrue(result)
        self.assertTrue(self.connector._connection_validated)
        mock_make_request.assert_called_once_with('health', 'check', {})
    
    @patch.object(MCPGCPConnector, '_make_request')
    def test_is_available_health_check_failure(self, mock_make_request):
        """Test is_available with failed health check."""
        mock_make_request.return_value = MCPResponse(success=False, error="Server error")
        
        result = self.connector.is_available()
        
        self.assertFalse(result)
        self.assertFalse(self.connector._connection_validated)
    
    @patch.object(MCPGCPConnector, '_make_request')
    def test_is_available_exception(self, mock_make_request):
        """Test is_available with exception during health check."""
        mock_make_request.side_effect = Exception("Connection error")
        
        result = self.connector.is_available()
        
        self.assertFalse(result)
    
    @patch.object(MCPGCPConnector, 'is_available')
    def test_execute_gcp_query_not_available(self, mock_is_available):
        """Test execute_gcp_query when MCP is not available."""
        mock_is_available.return_value = False
        
        result = self.connector.execute_gcp_query('compute', 'list', {'project': 'test'})
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "MCP server not available")
        self.assertTrue(result.metadata["fallback_required"])
    
    @patch.object(MCPGCPConnector, 'is_available')
    @patch.object(MCPGCPConnector, '_make_request')
    def test_execute_gcp_query_success(self, mock_make_request, mock_is_available):
        """Test execute_gcp_query with successful response."""
        mock_is_available.return_value = True
        mock_response = MCPResponse(success=True, data={"instances": []})
        mock_make_request.return_value = mock_response
        
        result = self.connector.execute_gcp_query('compute', 'list', {'project': 'test'})
        
        self.assertTrue(result.success)
        self.assertEqual(result.data, {"instances": []})
        mock_make_request.assert_called_once_with('compute/list', 'POST', {'project': 'test'})
    
    @patch.object(MCPGCPConnector, 'is_available')
    @patch.object(MCPGCPConnector, '_make_request')
    def test_execute_gcp_query_exception(self, mock_make_request, mock_is_available):
        """Test execute_gcp_query with exception."""
        mock_is_available.return_value = True
        mock_make_request.side_effect = Exception("Request failed")
        
        result = self.connector.execute_gcp_query('compute', 'list', {'project': 'test'})
        
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Request failed")
        self.assertTrue(result.metadata["fallback_required"])
    
    def test_get_projects(self):
        """Test get_projects method."""
        with patch.object(self.connector, 'execute_gcp_query') as mock_execute:
            mock_response = MCPResponse(success=True, data={"projects": []})
            mock_execute.return_value = mock_response
            
            result = self.connector.get_projects()
            
            self.assertEqual(result, mock_response)
            mock_execute.assert_called_once_with('projects', 'list', {})
    
    @patch.object(MCPGCPConnector, 'is_available')
    def test_validate_connection_not_available(self, mock_is_available):
        """Test validate_connection when MCP is not available."""
        mock_is_available.return_value = False
        
        result = self.connector.validate_connection()
        
        self.assertFalse(result)
    
    @patch.object(MCPGCPConnector, 'is_available')
    @patch.object(MCPGCPConnector, 'execute_gcp_query')
    def test_validate_connection_health_check_fails(self, mock_execute, mock_is_available):
        """Test validate_connection when health check fails."""
        mock_is_available.return_value = True
        mock_execute.return_value = MCPResponse(success=False, error="Health check failed")
        
        result = self.connector.validate_connection()
        
        self.assertFalse(result)
    
    @patch.object(MCPGCPConnector, 'is_available')
    @patch.object(MCPGCPConnector, 'execute_gcp_query')
    @patch.object(MCPGCPConnector, 'get_projects')
    def test_validate_connection_success(self, mock_get_projects, mock_execute, mock_is_available):
        """Test validate_connection with successful validation."""
        mock_is_available.return_value = True
        mock_execute.return_value = MCPResponse(success=True, data={"status": "healthy"})
        mock_get_projects.return_value = MCPResponse(success=True, data={"projects": []})
        
        result = self.connector.validate_connection()
        
        self.assertTrue(result)
    
    @patch.object(MCPGCPConnector, 'is_available')
    @patch.object(MCPGCPConnector, 'execute_gcp_query')
    def test_validate_connection_exception(self, mock_execute, mock_is_available):
        """Test validate_connection with exception."""
        mock_is_available.return_value = True
        mock_execute.side_effect = Exception("Validation error")
        
        result = self.connector.validate_connection()
        
        self.assertFalse(result)
    
    def test_make_request_health_check(self):
        """Test _make_request for health check endpoint."""
        result = self.connector._make_request('health/check', 'GET', {})
        
        self.assertTrue(result.success)
        self.assertEqual(result.data, {"status": "healthy"})
    
    def test_make_request_projects_list(self):
        """Test _make_request for projects list endpoint."""
        result = self.connector._make_request('projects/list', 'GET', {})
        
        self.assertTrue(result.success)
        self.assertIn("projects", result.data)
        self.assertEqual(len(result.data["projects"]), 2)
    
    def test_make_request_other_endpoint(self):
        """Test _make_request for other endpoints."""
        result = self.connector._make_request('compute/list', 'POST', {'project': 'test'})
        
        self.assertTrue(result.success)
        self.assertEqual(result.data, {})


class TestMCPGCPService(unittest.TestCase):
    """Test MCP GCP Service base class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_connector = Mock(spec=MCPGCPConnector)
        self.service = MCPGCPService('compute', self.mock_connector)
    
    def test_init_with_connector(self):
        """Test service initialization with connector."""
        service = MCPGCPService('compute', self.mock_connector)
        
        self.assertEqual(service.service_name, 'compute')
        self.assertEqual(service.mcp_connector, self.mock_connector)
    
    def test_init_without_connector(self):
        """Test service initialization without connector."""
        with patch('mcp.gcp_connector.MCPGCPConnector') as mock_connector_class:
            mock_instance = Mock()
            mock_connector_class.return_value = mock_instance
            
            service = MCPGCPService('vpc')
            
            self.assertEqual(service.service_name, 'vpc')
            self.assertEqual(service.mcp_connector, mock_instance)
    
    def test_execute_with_fallback_mcp_success(self):
        """Test execute_with_fallback with successful MCP operation."""
        self.mock_connector.is_available.return_value = True
        self.mock_connector.execute_gcp_query.return_value = MCPResponse(
            success=True,
            data={"instances": ["test-instance"]}
        )
        
        fallback_func = Mock()
        
        result = self.service.execute_with_fallback(
            'list',
            {'project': 'test'},
            fallback_func
        )
        
        self.assertEqual(result, {"instances": ["test-instance"]})
        fallback_func.assert_not_called()
    
    def test_execute_with_fallback_mcp_failure(self):
        """Test execute_with_fallback with MCP failure, using fallback."""
        self.mock_connector.is_available.return_value = True
        self.mock_connector.execute_gcp_query.return_value = MCPResponse(
            success=False,
            error="MCP error"
        )
        
        fallback_func = Mock(return_value={"instances": ["fallback-instance"]})
        
        result = self.service.execute_with_fallback(
            'list',
            {'project': 'test'},
            fallback_func
        )
        
        self.assertEqual(result, {"instances": ["fallback-instance"]})
        fallback_func.assert_called_once_with(project='test')
    
    def test_execute_with_fallback_mcp_not_available(self):
        """Test execute_with_fallback when MCP is not available."""
        self.mock_connector.is_available.return_value = False
        
        fallback_func = Mock(return_value={"instances": ["direct-instance"]})
        
        result = self.service.execute_with_fallback(
            'list',
            {'project': 'test'},
            fallback_func
        )
        
        self.assertEqual(result, {"instances": ["direct-instance"]})
        fallback_func.assert_called_once_with(project='test')
    
    def test_should_use_mcp(self):
        """Test should_use_mcp method."""
        self.mock_connector.is_available.return_value = True
        
        result = self.service.should_use_mcp()
        
        self.assertTrue(result)
        self.mock_connector.is_available.assert_called_once()


class TestCreateMCPConnector(unittest.TestCase):
    """Test MCP connector factory function."""
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('mcp.gcp_connector.MCPGCPConnector')
    def test_create_mcp_connector_default(self, mock_connector_class):
        """Test create_mcp_connector with default values."""
        mock_instance = Mock()
        mock_instance.is_available.return_value = True
        mock_connector_class.return_value = mock_instance
        
        result = create_mcp_connector()
        
        mock_connector_class.assert_called_once_with(mcp_endpoint=None, timeout=30)
        self.assertEqual(result, mock_instance)
    
    @patch.dict(os.environ, {
        'MCP_GCP_ENDPOINT': 'http://custom:9000/gcp',
        'MCP_GCP_TIMEOUT': '60'
    })
    @patch('mcp.gcp_connector.MCPGCPConnector')
    def test_create_mcp_connector_with_env(self, mock_connector_class):
        """Test create_mcp_connector with environment variables."""
        mock_instance = Mock()
        mock_instance.is_available.return_value = False
        mock_connector_class.return_value = mock_instance
        
        result = create_mcp_connector()
        
        mock_connector_class.assert_called_once_with(
            mcp_endpoint='http://custom:9000/gcp',
            timeout=60
        )
        self.assertEqual(result, mock_instance)


if __name__ == '__main__':
    unittest.main()