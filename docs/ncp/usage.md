# NCP Usage Guide

This guide covers how to use NCP (Naver Cloud Platform) commands and features with the IC CLI tool.

## Command Structure

All NCP commands follow this general structure:

```bash
ic ncp <service> <action> [options]
ic ncpgov <service> <action> [options]  # For Government Cloud
```

## Available Services

- **EC2**: Compute instances management
- **S3**: Object storage operations
- **VPC**: Virtual Private Cloud networking
- **SG**: Security Groups management
- **RDS**: Relational Database Service

## Common Commands

### Getting Information

```bash
# Get general NCP information
ic ncp info

# Get service-specific information
ic ncp ec2 info
ic ncp s3 info
ic ncp vpc info
ic ncp sg info
ic ncp rds info

# Government Cloud equivalents
ic ncpgov ec2 info
ic ncpgov s3 info
```

### Output Formats

The IC CLI supports multiple output formats:

```bash
# Table format (default)
ic ncp ec2 info

# JSON format
ic ncp ec2 info --output json

# YAML format
ic ncp ec2 info --output yaml
```

## Service-Specific Usage

### EC2 (Compute Instances)

```bash
# List all EC2 instances
ic ncp ec2 info

# Filter by instance name
ic ncp ec2 info --name "web-server"

# Filter by status
ic ncp ec2 info --status running

# Get detailed information
ic ncp ec2 info --verbose

# Specify region
ic ncp ec2 info --region KR
```

**Available Information:**
- Instance ID, name, and status
- Instance type and specifications
- Network information (VPC, subnet, IP addresses)
- Security group associations
- Creation time and platform type

### S3 (Object Storage)

```bash
# List all S3 buckets
ic ncp s3 info

# Filter by bucket name
ic ncp s3 info --name "my-bucket"

# Get bucket details with size information
ic ncp s3 info --verbose

# Skip size calculation for faster response
ic ncp s3 info --no-size
```

**Available Information:**
- Bucket name and creation date
- Bucket size and object count
- Region and access permissions
- Encryption status

### VPC (Virtual Private Cloud)

```bash
# List all VPCs (VPC platform only)
ic ncp vpc info

# Filter by VPC name
ic ncp vpc info --name "production-vpc"

# Get detailed subnet information
ic ncp vpc info --verbose

# Specify region
ic ncp vpc info --region KR
```

**Available Information:**
- VPC ID, name, and CIDR block
- Subnet details and availability zones
- Route table information
- Internet Gateway status

**Note**: VPC services are only available on VPC platform, not Classic platform.

### Security Groups

```bash
# List all security groups
ic ncp sg info

# Filter by security group name
ic ncp sg info --name "web-sg"

# Get detailed rule information
ic ncp sg info --verbose

# Show inbound/outbound rules
ic ncp sg info --rules all
```

**Available Information:**
- Security group ID and name
- Inbound and outbound rules
- Associated resources
- Rule details (ports, protocols, sources)

### RDS (Relational Database Service)

```bash
# List all RDS instances
ic ncp rds info

# Filter by database name
ic ncp rds info --name "production-db"

# Get detailed database information
ic ncp rds info --verbose

# Filter by status
ic ncp rds info --status running
```

**Available Information:**
- Database instance ID and name
- Engine type and version
- Instance class and storage
- Connection endpoint and port
- Backup and maintenance information

## Global Options

All NCP commands support these global options:

| Option | Description | Example |
|--------|-------------|---------|
| `--output` | Output format (table/json/yaml) | `--output json` |
| `--debug` | Enable debug logging | `--debug` |
| `--help` | Show command help | `--help` |
| `--region` | Override default region | `--region US` |
| `--verbose` | Show detailed information | `--verbose` |
| `--timeout` | Request timeout in seconds | `--timeout 60` |

## Filtering and Searching

### Basic Filtering

```bash
# Filter by name pattern
ic ncp ec2 info --name "web*"

# Filter by status
ic ncp ec2 info --status running

# Filter by region
ic ncp s3 info --region KR
```

### Advanced Filtering

```bash
# Multiple filters
ic ncp ec2 info --name "prod*" --status running

# Case-insensitive matching
ic ncp s3 info --name "BUCKET" --ignore-case
```

## Working with Multiple Resources

### Batch Operations

```bash
# Process all resources
ic ncp ec2 info --all

# Limit results
ic ncp ec2 info --limit 50

# Use pagination
ic ncp s3 info --page-size 25
```

## Platform-Specific Usage

### VPC Platform

```bash
# Set platform to VPC (default)
ic config set ncp.platform "VPC"

# VPC platform provides full feature access:
ic ncp ec2 info    # Full instance details with VPC info
ic ncp vpc info    # VPC and subnet information
ic ncp sg info     # Advanced security group features
ic ncp rds info    # Full database features
```

### Classic Platform

```bash
# Set platform to Classic
ic config set ncp.platform "Classic"

# Classic platform limitations:
ic ncp ec2 info    # Basic instance information
ic ncp s3 info     # Object storage (available)
ic ncp vpc info    # NOT available on Classic platform
ic ncp sg info     # Basic security group features
ic ncp rds info    # Limited database features
```

## Government Cloud Usage

### NCPGOV Commands

```bash
# Government Cloud equivalents
ic ncpgov ec2 info
ic ncpgov s3 info
ic ncpgov vpc info
ic ncpgov sg info
ic ncpgov rds info

# Enable compliance checking
ic ncpgov ec2 info --compliance-check

# Show encryption status
ic ncpgov s3 info --encryption-status

# Audit trail information
ic ncpgov vpc info --audit-trail
```

### Enhanced Security Features

```bash
# Enable data masking for sensitive information
ic config set ncpgov.security.mask_sensitive_data true

# Enable audit logging
ic config set ncpgov.security.audit_logging_enabled true

# Check compliance status
ic ncpgov ec2 info --compliance-check
```

## Configuration and Credentials

### Using Different Profiles

```bash
# Use specific profile
ic ncp ec2 info --profile production

# Use different region
ic ncp ec2 info --region JP
```

### Environment Variables

You can override configuration using environment variables:

```bash
# Set region for single command
NCP_REGION=US ic ncp ec2 info

# Set debug mode
NCP_DEBUG=true ic ncp ec2 info
```

## Examples and Use Cases

### Example 1: Infrastructure Discovery

```bash
# Discover all NCP resources
ic ncp ec2 info --output json > ec2_instances.json
ic ncp s3 info --output json > s3_buckets.json
ic ncp vpc info --output json > vpc_networks.json
ic ncp sg info --output json > security_groups.json
ic ncp rds info --output json > databases.json
```

### Example 2: Monitoring and Status Checking

```bash
# Check running instances
ic ncp ec2 info --status running

# Monitor database status
ic ncp rds info --status running --verbose

# Check security group configurations
ic ncp sg info --verbose
```

### Example 3: Multi-Region Operations

```bash
# Check resources across regions
ic ncp ec2 info --region KR --output json > kr_instances.json
ic ncp ec2 info --region US --output json > us_instances.json
ic ncp ec2 info --region JP --output json > jp_instances.json
```

### Example 4: Government Cloud Compliance

```bash
# Check compliance across all services
ic ncpgov ec2 info --compliance-check
ic ncpgov s3 info --encryption-status
ic ncpgov vpc info --security-audit
ic ncpgov rds info --compliance-check
```

## Automation and Scripting

### JSON Output for Scripts

```bash
# Get machine-readable output
ic ncp ec2 info --output json | jq '.instances[]'

# Filter running instances
ic ncp ec2 info --output json | jq '.instances[] | select(.status=="running")'

# Extract specific fields
ic ncp s3 info --output json | jq '.buckets[].name'
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

# Check if NCP connection works
if ic ncp ec2 info --quiet; then
    echo "NCP connection successful"
else
    echo "NCP connection failed"
    exit 1
fi

# Process instances
ic ncp ec2 info --output json | jq -r '.instances[] | select(.status=="running") | .name'
```

## Performance and Optimization

### Caching

```bash
# Enable caching for faster repeated queries
export NCP_CACHE_ENABLED=true
export NCP_CACHE_TTL=300

# Clear cache
ic cache clear --platform ncp
```

### Parallel Processing

```bash
# Process multiple regions in parallel
ic ncp ec2 info --regions KR,US,JP --parallel
```

### Large Dataset Handling

```bash
# Use pagination for large results
ic ncp ec2 info --page-size 50 --max-pages 10

# Skip expensive operations
ic ncp s3 info --no-size  # Skip bucket size calculation
```

## Best Practices

### 1. Resource Management

- Use descriptive names and tags for resources
- Regularly review and clean up unused resources
- Monitor resource usage and costs

### 2. Security

- Use least-privilege access principles
- Regularly rotate API credentials
- Enable audit logging for government cloud

### 3. Automation

- Use JSON output for scripting
- Implement proper error handling
- Use configuration files for consistent settings

### 4. Performance

- Enable caching for repeated operations
- Use filtering to reduce data transfer
- Implement pagination for large datasets

## Troubleshooting

### Common Issues

#### Issue: Command not found
```
ic: ncp: command not found
```
**Solution**: Ensure NCP integration is properly installed.

#### Issue: Authentication failed
```
Error: Authentication failed
```
**Solution**: Check your credentials in the [Configuration Guide](configuration.md).

#### Issue: VPC services not available
```
Error: VPC services not available on Classic platform
```
**Solution**: Switch to VPC platform: `ic config set ncp.platform "VPC"`

### Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
ic ncp ec2 info --debug
```

### Getting Help

```bash
# General help
ic ncp --help

# Service-specific help
ic ncp ec2 --help
ic ncp s3 --help

# Command-specific help
ic ncp ec2 info --help
```

## Next Steps

- Explore the [Troubleshooting Guide](troubleshooting.md) for common issues
- Check the main project documentation for advanced features
- Review NCP documentation for service-specific details