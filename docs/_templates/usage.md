# {PLATFORM} Usage Guide

This guide covers how to use {PLATFORM} commands and features with the IC CLI tool.

## Command Structure

All {PLATFORM} commands follow this general structure:

```bash
ic {platform_command} <service> <action> [options]
```

## Available Services

{SERVICE_LIST}

## Common Commands

### Getting Information

```bash
# Get general {PLATFORM} information
ic {platform_command} info

# Get service-specific information
ic {platform_command} <service> info

# List resources
ic {platform_command} <service> list
```

### Output Formats

The IC CLI supports multiple output formats:

```bash
# Table format (default)
ic {platform_command} info

# JSON format
ic {platform_command} info --output json

# YAML format
ic {platform_command} info --output yaml
```

## Service-Specific Usage

{SERVICE_SPECIFIC_SECTIONS}

## Global Options

All {PLATFORM} commands support these global options:

| Option | Description | Example |
|--------|-------------|---------|
| `--output` | Output format (table/json/yaml) | `--output json` |
| `--debug` | Enable debug logging | `--debug` |
| `--help` | Show command help | `--help` |
| `--region` | Override default region | `--region us-east-1` |

## Filtering and Searching

### Basic Filtering

```bash
# Filter by name
ic {platform_command} <service> list --name "pattern"

# Filter by status
ic {platform_command} <service> list --status running

# Filter by tags
ic {platform_command} <service> list --tag "key=value"
```

### Advanced Filtering

```bash
# Multiple filters
ic {platform_command} <service> list --name "web*" --status running

# Regular expressions
ic {platform_command} <service> list --name-regex "^prod-.*"
```

## Working with Multiple Resources

### Batch Operations

```bash
# Process multiple resources
ic {platform_command} <service> info --all

# Filter and process
ic {platform_command} <service> list --status stopped --output json
```

### Resource Selection

```bash
# Select by ID
ic {platform_command} <service> info --id resource-123

# Select by name pattern
ic {platform_command} <service> info --name "prod-*"
```

## Configuration and Credentials

### Using Different Profiles

```bash
# Use specific profile
ic {platform_command} info --profile production

# Use different region
ic {platform_command} info --region ap-northeast-2
```

### Environment Variables

You can override configuration using environment variables:

```bash
# Set region for single command
{PLATFORM_PREFIX}_REGION=us-west-2 ic {platform_command} info

# Set debug mode
{PLATFORM_PREFIX}_DEBUG=true ic {platform_command} info
```

## Examples and Use Cases

### Example 1: Basic Resource Discovery

```bash
# Discover all resources
ic {platform_command} info

# Get detailed information about specific service
ic {platform_command} <service> info --output json
```

### Example 2: Monitoring and Status Checking

```bash
# Check service status
ic {platform_command} <service> list --status running

# Monitor specific resources
ic {platform_command} <service> info --name "critical-*"
```

### Example 3: Troubleshooting

```bash
# Debug connection issues
ic {platform_command} info --debug

# Check configuration
ic config status --platform {platform_name}

# Validate credentials
ic {platform_command} info --validate-only
```

## Automation and Scripting

### JSON Output for Scripts

```bash
# Get machine-readable output
ic {platform_command} info --output json | jq '.resources[]'

# Filter and process
ic {platform_command} <service> list --output json | jq '.[] | select(.status=="running")'
```

### Exit Codes

The IC CLI uses standard exit codes:

- `0`: Success
- `1`: General error
- `2`: Configuration error
- `3`: Authentication error
- `4`: Resource not found

### Error Handling in Scripts

```bash
#!/bin/bash

# Check if command succeeded
if ic {platform_command} info --quiet; then
    echo "Connection successful"
else
    echo "Connection failed"
    exit 1
fi
```

## Performance and Optimization

### Caching

```bash
# Enable caching for faster repeated queries
ic {platform_command} info --cache

# Clear cache
ic cache clear --platform {platform_name}
```

### Parallel Processing

```bash
# Process multiple regions in parallel
ic {platform_command} info --regions us-east-1,us-west-2 --parallel
```

## Best Practices

### 1. Resource Management

- Use descriptive names and tags for resources
- Regularly review and clean up unused resources
- Monitor resource usage and costs

### 2. Security

- Use least-privilege access principles
- Regularly rotate credentials
- Enable audit logging where available

### 3. Automation

- Use JSON output for scripting
- Implement proper error handling
- Use configuration files for consistent settings

## Troubleshooting

### Common Issues

#### Issue: Command not found
```
ic: {platform_command}: command not found
```
**Solution**: Ensure {PLATFORM} integration is properly installed.

#### Issue: Authentication failed
```
Error: Authentication failed
```
**Solution**: Check your credentials in the [Configuration Guide](configuration.md).

#### Issue: Resource not found
```
Error: Resource not found
```
**Solution**: Verify the resource exists and you have proper permissions.

### Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
ic {platform_command} info --debug
```

### Getting Help

```bash
# General help
ic {platform_command} --help

# Service-specific help
ic {platform_command} <service> --help

# Command-specific help
ic {platform_command} <service> <action> --help
```

## Next Steps

- Explore the [Troubleshooting Guide](troubleshooting.md) for common issues
- Check the main project documentation for advanced features
- Review {PLATFORM} documentation for service-specific details