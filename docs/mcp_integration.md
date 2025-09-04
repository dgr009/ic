# MCP Integration Guide

This guide explains how to use the MCP (Model Context Protocol) integration in IC for querying cloud platform documentation and best practices.

## Overview

The MCP Manager provides secure integration with various MCP servers to query:
- AWS documentation and best practices
- Terraform modules and providers
- Azure documentation and CLI examples
- GitHub repository operations

## Configuration

MCP servers are configured in `.kiro/settings/mcp.json`. The system supports both workspace-level and user-level configurations.

### Example Configuration

```json
{
  "mcpServers": {
    "awslabs.aws-documentation-mcp-server": {
      "command": "uvx",
      "args": ["awslabs.aws-documentation-mcp-server@latest"],
      "env": {
        "AWS_DOCUMENTATION_PARTITION": "aws"
      },
      "disabled": false,
      "autoApprove": ["read_documentation", "search_documentation"]
    },
    "terraform": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "hashicorp/terraform-mcp-server"],
      "env": {},
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

## Usage

### Basic Usage

```python
from ic.core.mcp_manager import MCPManager
from ic.config.security import SecurityManager

# Initialize
security_manager = SecurityManager()
mcp_manager = MCPManager(security_manager=security_manager)

# Query AWS best practices
result = mcp_manager.query_aws_best_practices('s3', 'create-bucket')
if result.success:
    print(f"Recommendations: {result.data['recommendations']}")
else:
    print(f"Error: {result.error}")
```

### AWS Documentation Queries

```python
# Query AWS service best practices
result = mcp_manager.query_aws_best_practices('lambda', 'deployment')

# Query specific AWS operation
result = mcp_manager.query_aws_best_practices('ec2', 'launch-instance')

# Custom search phrase
result = mcp_manager.query_aws_best_practices('', '', 'S3 security best practices')
```

### Terraform Module Queries

```python
# Query Terraform modules for AWS S3
result = mcp_manager.query_terraform_module('aws', 's3')

# Query specific module
result = mcp_manager.query_terraform_module('azure', 'vm', 'Azure/compute/azurerm')
```

### Azure Documentation Queries

```python
# Query Azure service documentation
result = mcp_manager.query_azure_documentation('vm', 'documentation')

# Query Azure best practices
result = mcp_manager.query_azure_documentation('storage', 'best-practices', 'create')
```

### GitHub Operations

```python
# Query GitHub operations
result = mcp_manager.query_github_operations('list_issues', 'owner/repo')

# Create pull request
result = mcp_manager.query_github_operations('create_pr', 'owner/repo', 
                                           title='New feature', 
                                           head='feature-branch', 
                                           base='main')
```

## Security Features

### Sensitive Data Masking

The MCP Manager automatically masks sensitive data in configurations and query results:

```python
# Get server config with masking (default)
config = mcp_manager.get_server_config('github', mask_sensitive=True)
# API tokens will be shown as '***MASKED***'

# Get unmasked config (use with caution)
config = mcp_manager.get_server_config('github', mask_sensitive=False)
```

### Security Validation

```python
# Validate server security
warnings = mcp_manager.validate_server_security('github')
for warning in warnings:
    print(f"Security warning: {warning}")

# Get overall security summary
summary = mcp_manager.get_security_summary()
print(f"Total servers: {summary['total_servers']}")
print(f"Security warnings: {len(summary['security_warnings'])}")
```

## Fallback Mechanisms

When MCP servers are unavailable, the system provides fallback data:

```python
result = mcp_manager.query_aws_best_practices('s3', 'create-bucket')
if not result.success:
    # Still provides useful fallback recommendations
    print(f"Fallback recommendations: {result.data['recommendations']}")
```

## Error Handling

```python
try:
    result = mcp_manager.query_aws_best_practices('s3', 'create-bucket')
    if result.success:
        # Process successful result
        process_aws_data(result.data)
    else:
        # Handle query failure with fallback data
        handle_fallback(result.data, result.error)
except Exception as e:
    logger.error(f"MCP query failed: {e}")
```

## Server Management

### List Available Servers

```python
# List all servers
servers = mcp_manager.list_servers()

# List including disabled servers
servers = mcp_manager.list_servers(include_disabled=True)

# Check if specific server is available
if mcp_manager.is_server_available('terraform'):
    print("Terraform server is available")
```

### Default Configuration

```python
from ic.core.mcp_manager import create_default_mcp_config

# Get default MCP configuration
default_config = create_default_mcp_config()
```

## Best Practices

1. **Security**: Always use environment variables for sensitive data like API tokens
2. **Fallback**: Handle cases where MCP servers are unavailable
3. **Masking**: Use sensitive data masking in logs and configurations
4. **Validation**: Regularly validate server configurations for security issues
5. **Error Handling**: Implement proper error handling for MCP queries

## Troubleshooting

### Common Issues

1. **Server Not Available**: Check if the MCP server is properly configured and enabled
2. **Authentication Errors**: Verify environment variables for API tokens
3. **Network Issues**: Check network connectivity to MCP servers
4. **Configuration Errors**: Validate JSON syntax in mcp.json files

### Debug Information

```python
# Enable debug logging
import logging
logging.getLogger('ic.core.mcp_manager').setLevel(logging.DEBUG)

# Get detailed server information
servers = mcp_manager.list_servers(mask_sensitive=False)
for name, config in servers.items():
    print(f"Server {name}: {config}")
```

## Integration with IC CLI

The MCP Manager is integrated into the IC CLI for enhanced functionality:

```bash
# Query AWS best practices (future CLI integration)
ic aws s3 best-practices --operation create-bucket

# Query Terraform modules (future CLI integration)  
ic terraform modules --provider aws --service s3

# Validate MCP security (future CLI integration)
ic mcp security-check
```