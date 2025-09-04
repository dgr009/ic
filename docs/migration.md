# IC Configuration Migration Guide

This guide helps you migrate from the legacy `.env` file-based configuration to the new secure YAML-based configuration system.

## Overview

The new configuration system provides:

- **Security**: Sensitive data is kept in environment variables, not in config files
- **Structure**: YAML format with clear hierarchy and validation
- **Flexibility**: Multiple configuration sources with proper precedence
- **Validation**: Built-in configuration and security validation
- **Migration**: Automated migration from `.env` files

## Quick Migration

### 1. Automatic Migration

The easiest way to migrate is using the built-in migration command:

```bash
# Migrate .env to ic.yaml with backup
ic config migrate

# Preview migration without making changes
ic config migrate --dry-run

# Migrate to custom output file
ic config migrate --output my-config.yaml
```

### 2. Manual Migration

If you prefer manual migration, follow these steps:

1. **Initialize new configuration:**
   ```bash
   ic config init --template multi-cloud
   ```

2. **Review generated configuration:**
   ```bash
   ic config show
   ```

3. **Validate configuration:**
   ```bash
   ic config validate --security
   ```

## Migration Process Details

### What Gets Migrated

The migration process converts these `.env` variables to YAML configuration:

#### AWS Configuration
```bash
# .env
AWS_ACCOUNTS=123456789012,987654321098
AWS_REGIONS=ap-northeast-2,us-east-1
AWS_CROSS_ACCOUNT_ROLE=OrganizationAccountAccessRole
AWS_SESSION_DURATION=3600
AWS_MAX_WORKERS=10
```

Becomes:
```yaml
# ic.yaml
aws:
  accounts:
    - "123456789012"
    - "987654321098"
  regions:
    - "ap-northeast-2"
    - "us-east-1"
  cross_account_role: "OrganizationAccountAccessRole"
  session_duration: 3600
  max_workers: 10
```

#### Azure Configuration
```bash
# .env
AZURE_SUBSCRIPTIONS=sub1,sub2
AZURE_LOCATIONS=Korea Central,East US
AZURE_MAX_WORKERS=10
```

Becomes:
```yaml
# ic.yaml
azure:
  subscriptions:
    - "sub1"
    - "sub2"
  locations:
    - "Korea Central"
    - "East US"
  max_workers: 10
```

#### GCP Configuration
```bash
# .env
GCP_PROJECTS=project1,project2
GCP_REGIONS=asia-northeast3,us-central1
GCP_ZONES=asia-northeast3-a,us-central1-a
GCP_MAX_WORKERS=10
```

Becomes:
```yaml
# ic.yaml
gcp:
  projects:
    - "project1"
    - "project2"
  regions:
    - "asia-northeast3"
    - "us-central1"
  zones:
    - "asia-northeast3-a"
    - "us-central1-a"
  max_workers: 10
```

### What Stays in Environment Variables

**Sensitive data remains in environment variables for security:**

```bash
# Keep these in .env or environment
AWS_PROFILE=your-profile
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret

GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/service-account.json
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

CLOUDFLARE_EMAIL=your-email
CLOUDFLARE_API_TOKEN=your-api-token

SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

MCP_GITHUB_TOKEN=your-github-token
```

## Configuration File Locations

The new system supports multiple configuration file locations with proper precedence:

1. **Project Configuration** (highest precedence):
   - `ic.yaml`
   - `.ic/config.yaml`
   - `config/config.yaml`

2. **User Configuration**:
   - `~/.ic/config.yaml`

3. **System Configuration** (lowest precedence):
   - `/etc/ic/config.yaml`

4. **Environment Variables** (override any config file setting)

## Security Best Practices

### 1. Keep Secrets in Environment Variables

❌ **Don't do this:**
```yaml
# ic.yaml - DON'T PUT SECRETS HERE!
aws:
  access_key_id: "AKIAIOSFODNN7EXAMPLE"  # ❌ Security risk!
  secret_access_key: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # ❌ Security risk!
```

✅ **Do this instead:**
```yaml
# ic.yaml - Configuration only
aws:
  accounts:
    - "123456789012"
  regions:
    - "ap-northeast-2"
```

```bash
# .env or environment - Secrets here
AWS_PROFILE=your-profile
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

### 2. Update .gitignore

The migration process automatically updates `.gitignore` to exclude sensitive files:

```gitignore
# IC Configuration - Security
config.yaml
config.yml
.env
*.key
*.pem
**/credentials.json
**/service-account*.json
logs/
.ic/
```

### 3. Use Configuration Validation

Always validate your configuration for security issues:

```bash
# Validate configuration with security checks
ic config validate --security

# Validate specific config file
ic config validate my-config.yaml --security --verbose
```

## Backward Compatibility

### Existing Commands Continue to Work

All existing CLI commands continue to work without modification:

```bash
# These commands work exactly as before
ic aws ec2 info
ic azure vm info
ic gcp compute info
```

### Gradual Migration

You can migrate gradually:

1. **Phase 1**: Keep using `.env` files (with deprecation warnings)
2. **Phase 2**: Create YAML config alongside `.env` (YAML takes precedence)
3. **Phase 3**: Remove `.env` file and use only YAML + environment variables

### Legacy Import Support

Old import patterns continue to work with deprecation warnings:

```python
# Still works but shows deprecation warning
from common.log import log_error
from common.gather_env import gather_env_for_command

# New recommended imports
from src.ic.compat import get_logger
from src.ic.config.manager import ConfigManager
```

## Configuration Templates

### Minimal Template
```bash
ic config init --template minimal
```
Creates basic configuration with logging and security settings only.

### Service-Specific Templates
```bash
# AWS-focused configuration
ic config init --template aws

# Azure-focused configuration  
ic config init --template azure

# GCP-focused configuration
ic config init --template gcp

# Multi-cloud configuration
ic config init --template multi-cloud
```

## Configuration Management Commands

### View Current Configuration
```bash
# Show all configuration
ic config show

# Show specific section
ic config show aws.regions

# Show configuration sources
ic config show --sources

# Show as JSON
ic config show --format json
```

### Modify Configuration
```bash
# Set a simple value
ic config set aws.regions '["ap-northeast-2", "us-east-1"]'

# Set a string value
ic config set logging.console_level ERROR

# Get a value
ic config get aws.regions

# Get with default
ic config get aws.accounts --default "[]"
```

### Validate Configuration
```bash
# Basic validation
ic config validate

# Security validation
ic config validate --security

# Verbose validation
ic config validate --verbose

# Validate specific file
ic config validate my-config.yaml
```

## Troubleshooting

### Migration Issues

**Problem**: Migration fails with "sensitive data found"
```bash
⚠️ Security warning: Sensitive data found in config at aws.secret_access_key
```

**Solution**: Remove sensitive data from `.env` before migration, or use environment variables:
```bash
# Move sensitive data to environment
export AWS_SECRET_ACCESS_KEY="your-secret-key"
unset AWS_SECRET_ACCESS_KEY  # Remove from .env

# Then retry migration
ic config migrate
```

**Problem**: Configuration validation fails
```bash
❌ Configuration missing required section: aws
```

**Solution**: Initialize with appropriate template:
```bash
ic config init --template aws --force
```

### Runtime Issues

**Problem**: Commands can't find configuration
```bash
❌ AWS configuration not found
```

**Solution**: Check configuration and environment variables:
```bash
# Check current configuration
ic config show

# Validate configuration
ic config validate

# Check environment variables
env | grep -E "(AWS|AZURE|GCP)_"
```

**Problem**: Deprecation warnings
```bash
⚠️ 'common.log.log_error' is deprecated and will be removed in version 2.0.0
```

**Solution**: These are informational. Update imports when convenient:
```python
# Old (deprecated)
from common.log import log_error

# New (recommended)
from src.ic.compat import get_logger
logger = get_logger()
logger.log_error("message")
```

## Migration Checklist

- [ ] **Backup existing configuration**
  ```bash
  cp .env .env.backup
  ```

- [ ] **Run migration**
  ```bash
  ic config migrate --dry-run  # Preview first
  ic config migrate             # Actual migration
  ```

- [ ] **Validate new configuration**
  ```bash
  ic config validate --security
  ```

- [ ] **Test existing commands**
  ```bash
  ic aws ec2 info  # Test your most-used commands
  ```

- [ ] **Update environment variables**
  - Move secrets from config file to environment variables
  - Update `.env` file with only sensitive data

- [ ] **Update .gitignore**
  - Ensure sensitive files are excluded
  - Check that `config.yaml` and `.env` are in `.gitignore`

- [ ] **Clean up old files** (optional)
  ```bash
  # After confirming everything works
  rm .env.backup
  ```

## Getting Help

If you encounter issues during migration:

1. **Check the logs**:
   ```bash
   tail -f logs/ic_$(date +%Y%m%d).log
   ```

2. **Validate configuration**:
   ```bash
   ic config validate --security --verbose
   ```

3. **Check compatibility**:
   ```bash
   ic config show --sources
   ```

4. **Reset if needed**:
   ```bash
   # Start over with fresh configuration
   ic config init --template multi-cloud --force
   ```

For additional help, refer to:
- [Configuration Guide](configuration.md)
- [Security Guide](security.md)
- [API Documentation](../README.md)