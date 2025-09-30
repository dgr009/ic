"""
MCP (Model Context Protocol) integration package for IC CLI tool.

This package provides centralized backend operations through MCP server
for all cloud platform integrations including AWS, Azure, and GCP.
"""

from .gcp_connector import MCPGCPConnector, MCPGCPService, create_mcp_connector

__all__ = ['MCPGCPConnector', 'MCPGCPService', 'create_mcp_connector']