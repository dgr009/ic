# IC Configuration Management Guide

This guide covers the configuration system for IC (Infra Resource Management CLI), including setup, customization, and management.

## Table of Contents

- [Overview](#overview)
- [Configuration Hierarchy](#configuration-hierarchy)
- [Configuration Files](#configuration-files)
- [Environment Variables](#environment-variables)
- [Migration from .env](#migration-from-env)
- [Validation and Testing](#validation-and-testing)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)

## Overview

IC uses a modern, hierarchical configuration system that:

- **Separates sensitive and non-sensitive data**
- **Supports multiple configuration sources**
- **Provides automatic validation and security checks**
- **Enables easy migration from legacy .env files**
- **Maintains backward compatibility**

## Configuration Hierarchy

Configuration is loaded in the following order (later sources override earlier ones):

1. **Default Configuration** - Built-in safe defaults
2. **System Configuration** - `/etc/ic/config.yaml` (system-wide)
3. **User Configuration** - `~/.ic/config.yaml` (user-specific)
4. **Project Configuration** - `./ic.yaml` or `.ic/config.yaml` (project-specific)
5. **Environment Variables** - Highest priority (for sensitive data)
6. **Command Line Arguments** - Override specific options

### Example Hierarchy

```
Default Config (built-in)
├── System Config (/etc/ic/config.yaml)
│   └── User Config (~/.ic/config.yaml)
│       └── Project Config (./ic.yaml)
│           └── Environment Variables
│               └── Command Line Args
```

## Configuration Files

### Default Configuration

The default configuration (`.ic/config/default.yaml`) contains safe defaults:

**Note**: IC now uses `.ic/config/` as the preferred configuration directory. Legacy `config/` paths are still supported for backward compatibility.

```yaml
version: "1.0"
logging:
  console_level: "ERROR"
  file_level: "INFO"
  file_path: "logs/ic_{date}.log"
aws:
  regions: ["ap-northeast-2"]
  max_workers: 10
# ... more defaults
```

### User Configuration

Create `~/.ic/config.yaml` for user-specific settings:

```yaml
# User-specific configuration
version: "1.0"

aws:
  accounts: ["123456789012", "987654321098"]
  regions: ["ap-northeast-2", "us-east-1"]

azure:
  subscriptions: ["your-subscription-id"]
  locations: ["Korea Central"]

gcp:
  projects: ["your-project-id"]
  regions: ["asia-northeast3"]

logging:
  console_level: "INFO"  # More verbose for development
```

### Project Configuration

Create `ic.yaml` or `.ic/config.yaml` for project-specific settings:

```yaml
# Project-specific configuration
version: "1.0"

aws:
  accounts: ["123456789012"]  # Only specific accounts for this project
  regions: ["ap-northeast-2"]

logging:
  file_path: "project-logs/ic_{date}.log"
  max_files: 10

mcp:
  servers:
    github:
      enabled: true
      auto_approve: ["list_repositories"]
```

## Environment Variables

Use environment variables for sensitive data and runtime overrides:

### AWS Configuration

```bash
# Profile-based (recommended)
export AWS_PROFILE=your-profile-name
export AWS_DEFAULT_REGION=ap-northeast-2

# Direct credentials
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_SESSION_TOKEN=your-session-token  # For temporary credentials
```

### Azure Configuration

```bash
export AZURE_TENANT_ID=your-tenant-id
export AZURE_CLIENT_ID=your-client-id
export AZURE_CLIENT_SECRET=your-client-secret
export AZURE_SUBSCRIPTION_ID=your-subscription-id
```

### GCP Configuration

```bash
export GCP_PROJECT_ID=your-project-id
export GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/service-account.json
# OR
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### IC-Specific Variables

```bash
# Logging
export IC_LOG_LEVEL=ERROR
export IC_LOG_FILE_LEVEL=INFO
export IC_LOG_FILE_PATH=logs/custom_{date}.log

# Debug mode
export IC_DEBUG=true

# MCP settings
export FASTMCP_LOG_LEVEL=ERROR
```

## Migration from .env

IC provides tools to migrate from legacy .env files to the new configuration system:

### Automatic Migration

```bash
# Migrate .env to YAML configuration
ic config migrate

# Migrate with backup
ic config migrate --backup

# Dry run (show what would be migrated)
ic config migrate --dry-run
```

### Manual Migration

1. **Identify non-sensitive settings** in your `.env` file
2. **Move non-sensitive settings** to `~/.ic/config.yaml`
3. **Keep sensitive settings** in `.env` or environment variables
4. **Validate the migration**:
   ```bash
   ic config validate
   ic config show  # Display merged configuration
   ```

### Migration Example

**Before (.env file):**
```bash
AWS_PROFILE=production
AWS_DEFAULT_REGION=ap-northeast-2
AZURE_SUBSCRIPTION_ID=your-subscription-id
IC_LOG_LEVEL=INFO
IC_MAX_WORKERS=20
```

**After migration:**

**~/.ic/config.yaml** (non-sensitive):
```yaml
version: "1.0"
aws:
  regions: ["ap-northeast-2"]
  max_workers: 20
azure:
  subscriptions: ["your-subscription-id"]
logging:
  console_level: "INFO"
```

**.env** (sensitive only):
```bash
AWS_PROFILE=production
```

## Validation and Testing

### Configuration Validation

```bash
# Validate current configuration
ic config validate

# Validate specific file
ic config validate --file ~/.ic/config.yaml

# Show validation details
ic config validate --verbose
```

### Configuration Display

```bash
# Show merged configuration (with sensitive data masked)
ic config show

# Show configuration sources
ic config sources

# Show raw configuration (be careful with sensitive data)
ic config show --raw
```

### Testing Configuration

```bash
# Test AWS configuration
ic aws ec2 info --dry-run

# Test Azure configuration
ic azure vm info --dry-run

# Test GCP configuration
ic gcp compute info --dry-run
```

## Advanced Configuration

### Custom Configuration Paths

```bash
# Use custom configuration file
ic --config /path/to/custom/config.yaml aws ec2 info

# Set configuration directory
export IC_CONFIG_DIR=/path/to/config/directory
```

### Environment-Specific Configuration

Create environment-specific configurations:

```bash
# Development
~/.ic/config-dev.yaml

# Staging
~/.ic/config-staging.yaml

# Production
~/.ic/config-prod.yaml
```

Use with environment variable:
```bash
export IC_CONFIG_ENV=dev
ic config show  # Uses config-dev.yaml
```

### Configuration Templates

Create reusable configuration templates:

```yaml
# templates/aws-multi-account.yaml
version: "1.0"
aws:
  accounts: 
    - "${AWS_ACCOUNT_PROD}"
    - "${AWS_ACCOUNT_STAGING}"
    - "${AWS_ACCOUNT_DEV}"
  regions: ["${AWS_DEFAULT_REGION}"]
  cross_account_role: "${AWS_CROSS_ACCOUNT_ROLE}"
```

### Dynamic Configuration

Use environment variable substitution:

```yaml
# config.yaml
aws:
  regions: ["${AWS_DEFAULT_REGION:-ap-northeast-2}"]
  max_workers: ${IC_MAX_WORKERS:-10}
logging:
  file_path: "${IC_LOG_PATH:-logs/ic_{date}.log}"
```

## Troubleshooting

### Common Issues

#### Configuration Not Found

```bash
# Check configuration search paths
ic config sources

# Create user configuration
mkdir -p ~/.ic
cp config.example.yaml ~/.ic/config.yaml
```

#### Invalid Configuration Format

```bash
# Validate YAML syntax
ic config validate --file ~/.ic/config.yaml

# Check for common issues
yamllint ~/.ic/config.yaml
```

#### Environment Variables Not Working

```bash
# Check environment variables
env | grep -E "(IC_|AWS_|AZURE_|GCP_)"

# Test variable expansion
ic config show | grep -A5 -B5 "your-variable"
```

#### Permission Issues

```bash
# Check file permissions
ls -la ~/.ic/config.yaml

# Fix permissions
chmod 600 ~/.ic/config.yaml
chmod 700 ~/.ic/
```

### Debug Configuration Loading

Enable debug mode to see configuration loading details:

```bash
export IC_DEBUG=true
ic config show
```

This will show:
- Which configuration files are loaded
- Order of precedence
- Environment variable overrides
- Final merged configuration

### Configuration Backup and Recovery

```bash
# Backup current configuration
ic config backup --output config-backup-$(date +%Y%m%d).tar.gz

# Restore from backup
ic config restore --input config-backup-20240101.tar.gz

# Export configuration for sharing (sensitive data masked)
ic config export --output team-config.yaml
```

### Performance Optimization

For large configurations or slow loading:

```bash
# Cache configuration
export IC_CONFIG_CACHE=true

# Reduce configuration validation
export IC_CONFIG_FAST_LOAD=true

# Profile configuration loading
ic config profile
```

## Configuration Schema

IC uses JSON Schema for configuration validation. The schema is available at:
- `config/schema.json` - Full configuration schema
- Online: `https://github.com/dgr009/ic/blob/main/config/schema.json`

### Custom Schema Validation

```bash
# Validate against custom schema
ic config validate --schema /path/to/custom-schema.json

# Generate schema from configuration
ic config generate-schema --output my-schema.json
```

## Best Practices

1. **Keep sensitive data in environment variables**
2. **Use user configuration for personal settings**
3. **Use project configuration for team settings**
4. **Validate configuration after changes**
5. **Back up configuration before major changes**
6. **Use version control for non-sensitive configuration**
7. **Document custom configuration for your team**
8. **Test configuration in non-production environments first**

## Getting Help

For configuration issues:

1. **Check the validation output**: `ic config validate`
2. **Review the configuration hierarchy**: `ic config sources`
3. **Enable debug mode**: `export IC_DEBUG=true`
4. **Check the logs**: `tail -f logs/ic_$(date +%Y%m%d).log`
5. **Consult the security guide**: [docs/security.md](security.md)

For additional help, create an issue in the repository with:
- Your configuration (with sensitive data removed)
- Error messages
- Steps to reproduce the issue