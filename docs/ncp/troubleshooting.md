# NCP Troubleshooting Guide

This guide helps you diagnose and resolve common issues with NCP (Naver Cloud Platform) integration in the IC CLI tool.

## Quick Diagnostics

### 1. Check Installation

```bash
# Verify IC CLI is installed
ic --version

# Check if NCP commands are available
ic ncp --help
ic ncpgov --help
```

### 2. Verify Configuration

```bash
# Check configuration status
ic config status --platform ncp

# Test connectivity
ic ncp ec2 info --debug
```

### 3. Check Credentials

```bash
# Validate credentials without making API calls
ic config validate --platform ncp

# Test with minimal permissions
ic ncp ec2 info --validate-only
```

## Common Issues and Solutions

### Authentication and Credentials

#### Issue: Authentication Failed
```
Error: Authentication failed - Invalid credentials
```

**Possible Causes:**
- Incorrect access key or secret key
- Expired credentials
- Insufficient permissions

**Solutions:**
1. Verify credentials in NCP Console:
   - Go to My Page → API Key Management
   - Check Access Key and Secret Key
   - Ensure API access is enabled

2. Test credentials manually:
   ```bash
   curl -X GET "https://ncloud.apigw.ntruss.com/server/v2/getServerInstanceList" \
     -H "x-ncp-apigw-timestamp: $(date +%s)000" \
     -H "x-ncp-iam-access-key: YOUR_ACCESS_KEY"
   ```

3. Update configuration:
   ```bash
   ic config set access_key "new_access_key" --platform ncp
   ic config set secret_key "new_secret_key" --platform ncp
   ```

#### Issue: Government Cloud Authentication Failed
```
Error: NCP Gov authentication failed
```

**Solutions:**
1. Verify government cloud access and API Gateway key:
   ```bash
   ic config get ncpgov.apigw_key
   ```

2. Use separate configuration for government cloud:
   ```yaml
   # ~/.ncpgov/config
   default:
     access_key: "gov-access-key"
     secret_key: "gov-secret-key"
     region: "KR"
     compliance_mode: true
   ```

### Configuration Issues

#### Issue: Configuration File Not Found
```
Error: Configuration file not found
```

**Solutions:**
1. Initialize configuration:
   ```bash
   ic config init --platform ncp
   ```

2. Create configuration manually:
   ```bash
   mkdir -p ~/.ncp ~/.ncpgov
   touch ~/.ncp/config ~/.ncpgov/config
   chmod 600 ~/.ncp/config ~/.ncpgov/config
   ```

#### Issue: Invalid Configuration Format
```
Error: Invalid configuration format
```

**Solutions:**
1. Validate YAML syntax:
   ```bash
   ic config validate --platform ncp
   ```

2. Example correct format:
   ```yaml
   default:
     access_key: "your-access-key"
     secret_key: "your-secret-key"
     region: "KR"
   ```

### Network and Connectivity

#### Issue: Connection Timeout
```
Error: Connection timeout
```

**Solutions:**
1. Check network connectivity:
   ```bash
   ping ncloud.apigw.ntruss.com
   ```

2. Increase timeout:
   ```bash
   ic ncp ec2 info --timeout 60
   ```

3. Check firewall and proxy settings

#### Issue: Rate Limiting
```
Error: Rate limit exceeded
```

**Solutions:**
1. Add delay between requests:
   ```bash
   export NCP_REQUEST_DELAY=1.0
   ```

2. Use pagination:
   ```bash
   ic ncp ec2 info --limit 50
   ```

### Service-Specific Issues

#### Issue: VPC Services Not Available
```
Error: VPC services not available on Classic platform
```

**Solutions:**
1. This is expected behavior - switch to VPC platform:
   ```bash
   ic config set ncp.platform "VPC"
   ic ncp vpc info
   ```

#### Issue: No Resources Found
```
Error: No EC2 instances found
```

**Solutions:**
1. Check region configuration:
   ```bash
   ic config get ncp.region
   ic ncp ec2 info --region KR
   ```

2. Check status filter:
   ```bash
   ic ncp ec2 info --status all
   ```

## Debug Mode and Logging

### Enable Debug Mode

```bash
# Enable debug for single command
ic ncp ec2 info --debug

# Enable debug globally
export IC_DEBUG=true
export NCP_DEBUG=true
```

### Log Analysis

```bash
# View recent logs
tail -f ~/.ic/logs/ncp.log

# Search for specific errors
grep "ERROR" ~/.ic/logs/ncp.log

# Filter by timestamp
grep "$(date +%Y-%m-%d)" ~/.ic/logs/ncp.log
```

## Platform-Specific Issues

### Classic vs VPC Platform

**Issue**: Different service availability between platforms

**Solutions:**
```bash
# Check current platform
ic config get ncp.platform

# Classic platform limitations:
ic ncp ec2 info --platform classic    # Available
ic ncp s3 info --platform classic     # Available
ic ncp vpc info --platform classic    # NOT available (expected)

# VPC platform (full features):
ic ncp ec2 info --platform vpc        # Available (full features)
ic ncp vpc info --platform vpc        # Available
```

### Government Cloud Specific

**Issue**: Government cloud compliance validation failed

**Solutions:**
```bash
# Enable compliance mode
ic config set ncpgov.compliance_mode true

# Enable security features:
ic config set ncpgov.security.encryption_enabled true
ic config set ncpgov.security.audit_logging_enabled true
ic config set ncpgov.security.access_control_enabled true
```

## Performance Issues

### Slow Response Times

**Solutions:**
1. Enable caching:
   ```bash
   export NCP_CACHE_ENABLED=true
   export NCP_CACHE_TTL=300
   ```

2. Use pagination:
   ```bash
   ic ncp ec2 info --limit 50
   ```

3. Enable progress indicators:
   ```bash
   export IC_SHOW_PROGRESS=true
   ```

## Installation Issues

### Module Import Errors

#### Issue: ModuleNotFoundError: No module named 'ncp_module'
```bash
# Solution: IC CLI includes built-in NCP support
pip install --upgrade ic-code

# Verify NCP modules are available
python -c "from ncp_module.client import NCPClient; print('NCP module: OK')"
```

#### Issue: Cryptography dependency errors
```bash
# Install/upgrade cryptography
pip install --upgrade cryptography>=3.4.8

# On Ubuntu/Debian:
sudo apt-get install build-essential libssl-dev libffi-dev python3-dev

# On macOS:
brew install openssl libffi
```

## Automated Diagnostics

### Health Check Script

```bash
#!/bin/bash
# ncp_health_check.sh

echo "=== NCP Health Check ==="

# Check Python version
echo "Python version: $(python --version)"

# Check IC CLI installation
echo "IC CLI version: $(ic --version 2>/dev/null || echo 'Not installed')"

# Check NCP modules
python -c "from ncp_module.client import NCPClient; print('NCP module: OK')" 2>/dev/null || echo "NCP module: MISSING"
python -c "from ncpgov_module.client import NCPGovClient; print('NCP Gov module: OK')" 2>/dev/null || echo "NCP Gov module: MISSING"

# Check configuration files
[ -f ~/.ncp/config ] && echo "NCP config: EXISTS" || echo "NCP config: MISSING"
[ -f ~/.ncpgov/config ] && echo "NCP Gov config: EXISTS" || echo "NCP Gov config: MISSING"

# Test basic connectivity
ic ncp --help >/dev/null 2>&1 && echo "NCP CLI: OK" || echo "NCP CLI: ERROR"
ic ncpgov --help >/dev/null 2>&1 && echo "NCP Gov CLI: OK" || echo "NCP Gov CLI: ERROR"

echo "=== Health Check Complete ==="
```

## Getting Additional Help

### Self-Diagnosis

```bash
# Run comprehensive diagnostics
ic diagnose --platform ncp

# Generate support bundle
ic support bundle --platform ncp
```

### Documentation and Resources

1. Check the [Configuration Guide](configuration.md) for setup issues
2. Review the [Usage Guide](usage.md) for command syntax
3. Consult NCP official documentation
4. Check project GitHub issues

### Reporting Issues

When reporting issues, include:

1. IC CLI version: `ic --version`
2. Platform and OS information
3. Complete error message
4. Steps to reproduce
5. Debug output (with sensitive data removed)

### Support Commands

```bash
# Generate diagnostic report
ic diagnose --platform ncp --output report.txt

# Export configuration (sanitized)
ic config export --platform ncp --sanitize

# Test all functionality
ic test --platform ncp --comprehensive
```

## Prevention and Best Practices

### Regular Maintenance

1. Keep IC CLI updated
2. Rotate credentials regularly
3. Monitor for deprecated features
4. Review and update configurations

### Security

```bash
# Fix file permissions
chmod 600 ~/.ncp/config ~/.ncpgov/config

# Check for credential leaks
grep -r "access_key\|secret_key" ~/.ic/logs/ || echo "No credentials found in logs"
```

### Backup and Recovery

```bash
# Backup configuration
ic config backup --platform ncp

# Restore from backup
ic config restore --platform ncp --file backup.yaml
```