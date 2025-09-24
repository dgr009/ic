# IC Configuration Management Guide

This guide covers the general configuration system for IC (Infra Resource Management CLI), including setup, customization, and management across all platforms.

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

### Platform-Specific Configuration

Each platform has its own configuration directory and files:

- **AWS**: See [AWS Configuration Guide](../aws/configuration.md)
- **Azure**: See [Azure Configuration Guide](../azure/configuration.md)
- **GCP**: See [GCP Configuration Guide](../gcp/configuration.md)
- **NCP**: See [NCP Configuration Guide](../ncp/configuration.md)
- **NCPGOV**: See [NCPGOV Configuration Guide](../ncpgov/configuration.md)
- **OCI**: See [OCI Configuration Guide](../oci/configuration.md)

## Configuration Files

### Default Configuration

The default configuration (`.ic/config/default.yaml`) contains safe defaults:

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

## Environment Variables

Use environment variables for sensitive data and runtime overrides. See platform-specific guides for detailed environment variable configuration.

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
5. **Consult platform-specific guides for detailed configuration**

For additional help, create an issue in the repository with:
- Your configuration (with sensitive data removed)
- Error messages
- Steps to reproduce the issue