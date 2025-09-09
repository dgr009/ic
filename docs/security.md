# IC Security Setup Guide

This guide covers security best practices and setup for the IC (Infra Resource Management CLI) tool.

## Table of Contents

- [Security Overview](#security-overview)
- [Configuration Security](#configuration-security)
- [Credential Management](#credential-management)
- [Git Security](#git-security)
- [Environment Setup](#environment-setup)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Security Overview

IC implements a security-first approach to configuration and credential management:

- **No secrets in configuration files**: All sensitive data is stored in environment variables
- **Automatic sensitive data masking**: Logs and outputs automatically mask credentials
- **Git security validation**: Pre-commit hooks prevent accidental credential commits
- **Secure configuration examples**: Template files with placeholders, never real credentials

## Configuration Security

### Safe Configuration Files

IC uses a hierarchical configuration system with security built-in:

```
.ic/config/default.yaml     # Safe defaults, no secrets (preferred)
.ic/config/secrets.yaml.example  # Example with placeholders
config/default.yaml          # Legacy location (still supported)
.env.example                # Environment variable examples
```

### Configuration Hierarchy

1. **Default configuration** (`.ic/config/default.yaml`) - Safe defaults
2. **System configuration** (`/etc/ic/config.yaml`) - System-wide settings
3. **User configuration** (`~/.ic/config.yaml`) - User-specific settings
4. **Project configuration** (`./ic.yaml` or `.ic/config.yaml`) - Project settings
5. **Environment variables** - Highest priority, for sensitive data

### Security Validation

IC automatically validates configurations for security issues:

```bash
# Check configuration security
ic config validate

# Initialize secure configuration
ic config init
```

## Credential Management

### Environment Variables (Recommended)

Store all sensitive data in environment variables:

```bash
# AWS
export AWS_PROFILE=your-profile
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret

# Azure
export AZURE_TENANT_ID=your-tenant-id
export AZURE_CLIENT_ID=your-client-id
export AZURE_CLIENT_SECRET=your-secret

# GCP
export GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/key.json
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json

# CloudFlare
export CLOUDFLARE_EMAIL=your-email
export CLOUDFLARE_API_TOKEN=your-token
```

### .env File Setup

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your actual credentials:
   ```bash
   # Use a secure editor
   nano .env
   ```

3. Verify the file is excluded from Git:
   ```bash
   git status  # .env should not appear
   ```

### Credential Storage Options

#### AWS Credentials

**Option 1: AWS Profile (Recommended)**
```bash
aws configure --profile your-profile
export AWS_PROFILE=your-profile
```

**Option 2: Direct Environment Variables**
```bash
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
```

#### Azure Credentials

**Option 1: Service Principal**
```bash
export AZURE_TENANT_ID=your-tenant-id
export AZURE_CLIENT_ID=your-client-id
export AZURE_CLIENT_SECRET=your-secret
```

**Option 2: Azure CLI**
```bash
az login
# IC will use Azure CLI credentials automatically
```

#### GCP Credentials

**Option 1: Service Account Key**
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

**Option 2: Application Default Credentials**
```bash
gcloud auth application-default login
```

## Git Security

### Automatic Protection

IC automatically protects against credential leaks:

- **Enhanced .gitignore**: Excludes all credential files and patterns
- **Pre-commit hooks**: Scans for secrets before commits
- **Sensitive data detection**: Identifies potential credentials in code

### Install Git Hooks

```bash
# Install pre-commit security hooks
ic security install-hooks

# Manual installation
cp scripts/pre-commit .git/hooks/
chmod +x .git/hooks/pre-commit
```

### Security Scanning

```bash
# Scan staged files for secrets
ic security scan-staged

# Scan entire repository
ic security scan-repo

# Check specific files
ic security scan-files file1.py file2.yaml
```

## Environment Setup

### Initial Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd ic
   ```

2. **Create secure configuration**:
   ```bash
   # Initialize with security prompts
   ic config init

   # Or manually copy examples
   cp config.example.yaml ~/.ic/config.yaml
   cp .env.example .env
   ```

3. **Set up credentials**:
   ```bash
   # Edit your configuration
   nano ~/.ic/config.yaml  # Non-sensitive settings only
   nano .env               # Sensitive credentials
   ```

4. **Validate setup**:
   ```bash
   # Check configuration security
   ic config validate

   # Test credentials
   ic aws ec2 info --dry-run
   ```

### Development Environment

For development, use additional security measures:

```bash
# Install development dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install

# Enable debug logging (be careful with sensitive data)
export IC_DEBUG=true
export IC_LOG_FILE_LEVEL=DEBUG
```

## Best Practices

### Credential Security

1. **Use strong, unique credentials**
   - Generate strong passwords/tokens
   - Use different credentials for different environments
   - Enable MFA/2FA wherever possible

2. **Rotate credentials regularly**
   - Set up automatic rotation where possible
   - Monitor credential age and usage
   - Have a credential rotation schedule

3. **Use least-privilege access**
   - Grant minimum required permissions
   - Use role-based access control
   - Regularly audit permissions

4. **Monitor credential usage**
   - Enable CloudTrail (AWS), Activity Log (Azure), Audit Logs (GCP)
   - Set up alerts for unusual activity
   - Review access logs regularly

### Configuration Security

1. **Never commit secrets**
   - Use environment variables for all sensitive data
   - Validate with `ic security scan-repo`
   - Use placeholder values in examples

2. **Secure file permissions**
   ```bash
   # Secure your configuration files
   chmod 600 ~/.ic/config.yaml
   chmod 600 .env
   chmod 700 ~/.ic/
   ```

3. **Environment separation**
   - Use different credentials for dev/staging/prod
   - Separate configuration files by environment
   - Use environment-specific variable names

### Network Security

1. **Use secure connections**
   - Always use HTTPS/TLS
   - Verify SSL certificates
   - Use VPN for sensitive operations

2. **Network access control**
   - Restrict API access by IP where possible
   - Use private networks for sensitive resources
   - Monitor network access logs

## Troubleshooting

### Common Security Issues

#### Credentials Not Found
```bash
# Check environment variables
env | grep -E "(AWS|AZURE|GCP|CLOUDFLARE)"

# Validate configuration
ic config validate

# Check configuration sources
ic config sources
```

#### Permission Denied
```bash
# Check file permissions
ls -la ~/.ic/config.yaml
ls -la .env

# Fix permissions
chmod 600 ~/.ic/config.yaml .env
```

#### Git Hook Failures
```bash
# Check hook installation
ls -la .git/hooks/pre-commit

# Reinstall hooks
ic security install-hooks

# Test hooks manually
.git/hooks/pre-commit
```

### Security Warnings

#### Sensitive Data in Config
```
WARNING: Sensitive data found in config at 'aws.access_key'
```
**Solution**: Move the sensitive data to environment variables:
```bash
# Remove from config file
# Add to .env file
echo "AWS_ACCESS_KEY_ID=your-key" >> .env
```

#### Potential Secrets in Files
```
WARNING: Potential secrets found in file.py
```
**Solution**: Review the file and remove or mask sensitive data:
```bash
# Review the file
ic security scan-files file.py

# Use environment variables instead
export SENSITIVE_VALUE="actual-value"
```

### Getting Help

If you encounter security issues:

1. **Check the logs**:
   ```bash
   tail -f logs/ic_$(date +%Y%m%d).log
   ```

2. **Validate your setup**:
   ```bash
   ic config validate
   ic security scan-repo
   ```

3. **Review documentation**:
   - [Configuration Guide](configuration.md)
   - [AWS Setup Guide](aws-setup.md)
   - [Azure Setup Guide](azure-setup.md)

4. **Report security issues**:
   - Create an issue in the repository
   - Include sanitized logs (no credentials!)
   - Describe your environment and setup

## Security Policy

For security vulnerabilities, please:

1. **Do not create public issues**
2. **Email security concerns** to the maintainers
3. **Provide detailed information** about the vulnerability
4. **Allow time for fixes** before public disclosure

Remember: Security is everyone's responsibility. When in doubt, err on the side of caution and ask for help.

## Migration Security

### Secure Migration from .env

When migrating from `.env` files to the new YAML configuration system:

```bash
# Preview migration to check for security issues
ic config migrate --dry-run

# Migrate with security validation
ic config migrate --backup

# Validate migrated configuration
ic config validate --security
```

### Post-Migration Security

After migration:

1. **Remove sensitive data from config files:**
   ```bash
   # Check for accidentally included secrets
   ic config validate --security
   
   # Remove sensitive data manually if found
   ic config set aws.secret_access_key ""  # Remove if accidentally added
   ```

2. **Update environment variables:**
   ```bash
   # Keep only sensitive data in .env
   cat > .env << EOF
   AWS_PROFILE=your-profile
   AZURE_CLIENT_SECRET=your-secret
   GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/key.json
   EOF
   ```

3. **Verify .gitignore:**
   ```bash
   # Ensure config files are properly ignored
   git status --ignored | grep config.yaml
   git status --ignored | grep .env
   ```

### Migration Security Checklist

- [ ] Run migration preview: `ic config migrate --dry-run`
- [ ] Validate security: `ic config validate --security`
- [ ] Remove sensitive data from config files
- [ ] Update .env with only secrets
- [ ] Test with new configuration
- [ ] Verify .gitignore effectiveness
- [ ] Update team documentation

### Deprecation Warnings

During the migration period, you may see deprecation warnings:

```bash
⚠️ 'common.log.log_error' is deprecated and will be removed in version 2.0.0
```

These warnings are informational and help identify code that should be updated:

```python
# Old (deprecated)
from common.log import log_error

# New (recommended)
from src.ic.compat import get_logger
logger = get_logger()
logger.log_error("message")
```

### Backward Compatibility Security

The backward compatibility layer maintains security while supporting legacy usage:

- **Automatic .env loading**: Legacy .env files are loaded with deprecation warnings
- **Security validation**: All configuration sources are validated for security issues
- **Sensitive data masking**: Logs continue to mask sensitive data regardless of configuration source
- **Git protection**: Security hooks work with both old and new configuration formats