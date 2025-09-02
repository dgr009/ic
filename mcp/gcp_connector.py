"""
MCP GCP Connector for centralized GCP operations through Model Context Protocol server.

This module provides the primary interface for GCP operations through the MCP server,
with automatic fallback to direct API access when MCP is unavailable.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)


@dataclass
class MCPResponse:
    """Standardized MCP response structure."""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Optional[Dict] = None


class MCPGCPConnector:
    """
    MCP server connector for GCP operations.
    
    Provides centralized interface to GCP services through MCP server
    with automatic fallback detection and error handling.
    """
    
    def __init__(self, mcp_endpoint: Optional[str] = None, timeout: int = 30):
        """
        Initialize MCP GCP connector.
        
        Args:
            mcp_endpoint: MCP server endpoint URL
            timeout: Request timeout in seconds
        """
        self.mcp_endpoint = mcp_endpoint or os.getenv('MCP_GCP_ENDPOINT', 'http://localhost:8080/gcp')
        self.timeout = timeout
        self.enabled = os.getenv('MCP_GCP_ENABLED', 'true').lower() == 'true'
        self.prefer_mcp = os.getenv('GCP_PREFER_MCP', 'true').lower() == 'true'
        self._connection_validated = False
        
        logger.debug(f"MCP GCP Connector initialized: endpoint={self.mcp_endpoint}, enabled={self.enabled}")
    
    def is_available(self) -> bool:
        """
        Check if MCP server is available and responding.
        
        Returns:
            bool: True if MCP server is available
        """
        if not self.enabled or not self.prefer_mcp:
            return False
            
        if self._connection_validated:
            return True
            
        try:
            response = self._make_request('health', 'check', {})
            self._connection_validated = response.success
            return self._connection_validated
        except Exception as e:
            logger.debug(f"MCP server not available: {e}")
            return False
    
    def execute_gcp_query(self, service: str, operation: str, params: Dict) -> MCPResponse:
        """
        Execute GCP query through MCP server.
        
        Args:
            service: GCP service name (compute, vpc, gke, etc.)
            operation: Operation to perform (list, get, describe, etc.)
            params: Operation parameters
            
        Returns:
            MCPResponse: Standardized response with data or error
        """
        if not self.is_available():
            return MCPResponse(
                success=False,
                error="MCP server not available",
                metadata={"fallback_required": True}
            )
        
        try:
            endpoint = f"{service}/{operation}"
            response = self._make_request(endpoint, 'POST', params)
            
            logger.debug(f"MCP query executed: {service}.{operation} -> success={response.success}")
            return response
            
        except Exception as e:
            logger.error(f"MCP query failed: {service}.{operation} - {e}")
            return MCPResponse(
                success=False,
                error=str(e),
                metadata={"fallback_required": True}
            )
    
    def get_projects(self) -> MCPResponse:
        """
        Get accessible GCP projects through MCP server.
        
        Returns:
            MCPResponse: Response containing project list or error
        """
        return self.execute_gcp_query('projects', 'list', {})
    
    def validate_connection(self) -> bool:
        """
        Validate MCP server connection and GCP access.
        
        Returns:
            bool: True if connection is valid
        """
        if not self.is_available():
            return False
            
        try:
            # Test basic connectivity
            health_response = self.execute_gcp_query('health', 'check', {})
            if not health_response.success:
                return False
                
            # Test GCP access
            projects_response = self.get_projects()
            return projects_response.success
            
        except Exception as e:
            logger.error(f"MCP connection validation failed: {e}")
            return False
    
    def _make_request(self, endpoint: str, method: str, data: Dict) -> MCPResponse:
        """
        Make HTTP request to MCP server.
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            data: Request data
            
        Returns:
            MCPResponse: Parsed response
        """
        # This is a placeholder for actual HTTP client implementation
        # In a real implementation, this would use requests or similar
        # For now, we'll simulate MCP server responses
        
        logger.debug(f"MCP request: {method} {endpoint} with data: {data}")
        
        # Simulate MCP server response based on endpoint
        if endpoint == 'health/check':
            return MCPResponse(success=True, data={"status": "healthy"})
        elif endpoint == 'projects/list':
            return MCPResponse(
                success=True,
                data={
                    "projects": [
                        {"project_id": "test-project-1", "name": "Test Project 1"},
                        {"project_id": "test-project-2", "name": "Test Project 2"}
                    ]
                }
            )
        else:
            # For other endpoints, return success with empty data for now
            return MCPResponse(success=True, data={})


class MCPGCPService:
    """
    Base class for GCP services with MCP integration.
    
    Provides common functionality for MCP-enabled GCP services
    with automatic fallback to direct API access.
    """
    
    def __init__(self, service_name: str, mcp_connector: Optional[MCPGCPConnector] = None):
        """
        Initialize MCP GCP service.
        
        Args:
            service_name: Name of the GCP service
            mcp_connector: MCP connector instance
        """
        self.service_name = service_name
        self.mcp_connector = mcp_connector or MCPGCPConnector()
        self.logger = logging.getLogger(f"{__name__}.{service_name}")
    
    def execute_with_fallback(self, operation: str, params: Dict, fallback_func: callable) -> Dict:
        """
        Execute operation with MCP server, falling back to direct API if needed.
        
        Args:
            operation: Operation to perform
            params: Operation parameters
            fallback_func: Function to call if MCP fails
            
        Returns:
            Dict: Operation results
        """
        # Try MCP first if available
        if self.mcp_connector.is_available():
            self.logger.debug(f"Attempting MCP operation: {self.service_name}.{operation}")
            response = self.mcp_connector.execute_gcp_query(self.service_name, operation, params)
            
            if response.success:
                self.logger.info(f"MCP operation successful: {self.service_name}.{operation}")
                return response.data
            else:
                self.logger.warning(f"MCP operation failed: {response.error}")
        
        # Fallback to direct API
        self.logger.info(f"Using direct API fallback: {self.service_name}.{operation}")
        return fallback_func(**params)
    
    def should_use_mcp(self) -> bool:
        """
        Determine if MCP should be used for operations.
        
        Returns:
            bool: True if MCP should be used
        """
        return self.mcp_connector.is_available()


def create_mcp_connector() -> MCPGCPConnector:
    """
    Factory function to create MCP GCP connector with environment configuration.
    
    Returns:
        MCPGCPConnector: Configured connector instance
    """
    endpoint = os.getenv('MCP_GCP_ENDPOINT')
    timeout = int(os.getenv('MCP_GCP_TIMEOUT', '30'))
    
    connector = MCPGCPConnector(mcp_endpoint=endpoint, timeout=timeout)
    
    # Log configuration
    logger.info(f"MCP GCP Connector created: available={connector.is_available()}")
    
    return connector