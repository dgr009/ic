#!/usr/bin/env python3
"""
Example usage of the MCP Manager for querying different cloud platforms.

This example demonstrates how to use the MCPManager to query AWS, Azure,
Terraform, and GitHub MCP servers for documentation and best practices.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Import with fallback for compatibility
try:
    from src.ic.core.mcp_manager import MCPManager, create_default_mcp_config
    from src.ic.config.security import SecurityManager
except ImportError:
    from ic.core.mcp_manager import MCPManager, create_default_mcp_config
    from ic.config.security import SecurityManager


def main():
    """Demonstrate MCP Manager functionality."""
    print("=== MCP Manager Example ===\n")
    
    # Initialize security manager and MCP manager
    security_manager = SecurityManager()
    mcp_manager = MCPManager(security_manager=security_manager)
    
    # List available servers
    print("1. Available MCP Servers:")
    servers = mcp_manager.list_servers(mask_sensitive=True)
    for name, config in servers.items():
        status = "enabled" if not config['disabled'] else "disabled"
        print(f"   - {name}: {status}")
    print()
    
    # Query AWS best practices
    print("2. AWS Best Practices Query:")
    aws_result = mcp_manager.query_aws_best_practices('s3', 'create-bucket')
    if aws_result.success:
        print(f"   ✓ Query successful via {aws_result.server_name}")
        print(f"   Service: {aws_result.data['service']}")
        print(f"   Operation: {aws_result.data['operation']}")
        print("   Recommendations:")
        for rec in aws_result.data.get('recommendations', [])[:3]:
            print(f"     • {rec}")
    else:
        print(f"   ✗ Query failed: {aws_result.error}")
        print("   Using fallback data:")
        for rec in aws_result.data.get('recommendations', [])[:3]:
            print(f"     • {rec}")
    print()
    
    # Query Terraform modules
    print("3. Terraform Module Query:")
    tf_result = mcp_manager.query_terraform_module('aws', 's3')
    if tf_result.success:
        print(f"   ✓ Query successful via {tf_result.server_name}")
        print(f"   Provider: {tf_result.data['provider']}")
        print(f"   Service: {tf_result.data['service']}")
        modules = tf_result.data.get('recommended_modules', [])
        if modules:
            print("   Recommended modules:")
            for module in modules[:2]:
                print(f"     • {module['name']}: {module['description']}")
    else:
        print(f"   ✗ Query failed: {tf_result.error}")
    print()
    
    # Query Azure documentation
    print("4. Azure Documentation Query:")
    azure_result = mcp_manager.query_azure_documentation('vm', 'documentation')
    if azure_result.success:
        print(f"   ✓ Query successful via {azure_result.server_name}")
        print(f"   Service: {azure_result.data['service']}")
        print(f"   Intent: {azure_result.data['intent']}")
        service_info = azure_result.data.get('service_info', {})
        print(f"   Description: {service_info.get('description', 'N/A')}")
    else:
        print(f"   ✗ Query failed: {azure_result.error}")
    print()
    
    # Query GitHub operations
    print("5. GitHub Operations Query:")
    github_result = mcp_manager.query_github_operations('list_issues', 'owner/repo')
    if github_result.success:
        print(f"   ✓ Query successful via {github_result.server_name}")
        print(f"   Operation: {github_result.data['operation']}")
        print(f"   Repository: {github_result.data['repository']}")
        op_info = github_result.data.get('operation_info', {})
        print(f"   Description: {op_info.get('description', 'N/A')}")
    else:
        print(f"   ✗ Query failed: {github_result.error}")
    print()
    
    # Security summary
    print("6. Security Summary:")
    security_summary = mcp_manager.get_security_summary()
    print(f"   Total servers: {security_summary['total_servers']}")
    print(f"   Enabled servers: {security_summary['enabled_servers']}")
    print(f"   Servers with env vars: {security_summary['servers_with_env_vars']}")
    
    if security_summary['security_warnings']:
        print("   Security warnings:")
        for server, warnings in security_summary['security_warnings'].items():
            print(f"     {server}: {len(warnings)} warning(s)")
    else:
        print("   ✓ No security warnings")
    print()
    
    # Show default configuration
    print("7. Default MCP Configuration:")
    default_config = create_default_mcp_config()
    print("   Available server types:")
    for server_name in default_config['mcp']['servers']:
        server_config = default_config['mcp']['servers'][server_name]
        status = "disabled" if server_config.get('disabled') else "enabled"
        print(f"     • {server_name}: {status}")
    print()
    
    print("=== Example Complete ===")


if __name__ == '__main__':
    main()