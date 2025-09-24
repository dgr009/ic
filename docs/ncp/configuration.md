# NCP Configuration Guide

This guide explains how to configure NCP (Naver Cloud Platform) credentials and settings for the IC CLI tool.

## Configuration Overview

The IC CLI tool uses a hierarchical configuration system to manage NCP credentials and settings:

1. Project-specific configuration (`./.ic/config/`)
2. User home configuration (`~/.ic/config/`)
3. Platform-specific configuration (`~/.ncp/`, `~/.ncpgov/`)
4. Environment variables
5. Default settings

## Initial Configuration

### 1. Run Configuration Setup

```bash
# Initialize configuration for all platforms
ic config init

# Initialize configuration for NCP only
ic config init --platform ncp
```

This will create the necessary configuration directories and files.

### 2. Configure Credentials

#### Method 1: Configuration File

Edit the configuration file at `~/.ncp/config`:

```yaml
# NCP Configuration
default:
  access_key: "your_ncp_access_key"
  secret_key: "your_ncp_secret_key"
  region: "KR"  # KR (Korea), US (United States), JP (Japan)

production:
  access_key: "prod_access_key"
  secret_key: "prod_secret_key"
  region: "KR"
```

For NCP Government Cloud, edit `~/.ncpgov/config`:

```yaml
# NCPGOV Configuration
default:
  access_key: "your_ncpgov_access_key"
  secret_key: "your_ncpgov_secret_key"
  region: "KR"
  compliance_mode: true
  security_level: "high"
```

#### Method 2: Environment Variables

Set environment variables in your shell or `.env` file:

```bash
# Standard NCP
export NCP_ACCESS_KEY="your_access_key"
export NCP_SECRET_KEY="your_secret_key"
export NCP_REGION="KR"

# Government Cloud
export NCPGOV_ACCESS_KEY="your_gov_access_key"
export NCPGOV_SECRET_KEY="your_gov_secret_key"
export NCPGOV_REGION="KR"
```

### 3. Verify Configuration

```bash
# Test NCP connectivity
ic ncp ec2 info

# Test NCPGOV connectivity
ic ncpgov ec2 info

# Check configuration status
ic config status --platform ncp
```

## Configuration Options

### Credentials

| Setting | Description | Required | Default |
|---------|-------------|----------|---------|
| `access_key` | NCP access key | Yes | - |
| `secret_key` | NCP secret key | Yes | - |
| `region` | Default region (KR/US/JP) | Yes | - |

### Advanced Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `timeout` | Request timeout in seconds | 30 |
| `retry_attempts` | Number of retry attempts | 3 |
| `output_format` | Default output format (table/json/yaml) | table |
| `debug` | Enable debug logging | false |
| `platform` | NCP platform (VPC/Classic) | VPC |

### Government Cloud Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `compliance_mode` | Enable compliance mode | false |
| `security_level` | Security level (high/medium/low) | medium |
| `audit_logging` | Enable audit logging | false |
| `encryption_enabled` | Enable encryption | false |

## Getting NCP API Credentials

### Standard NCP Console

1. Log in to [NCP Console](https://console.ncloud.com/)
2. Go to **My Page** → **API Key Management**
3. Click **Create API Key**
4. Copy **Access Key** and **Secret Key**
5. Add to IC CLI configuration

### Government Cloud Console

1. Access NCP Government Cloud Console (URL provided by NCP)
2. Navigate to **Security** → **API Management**
3. Generate **Government API Key**
4. Follow enhanced security procedures
5. Add to IC CLI NCP Gov configuration

## Security Best Practices

### 1. Credential Storage

- **Never** commit credentials to version control
- Use environment variables for CI/CD environments
- Store credentials in secure configuration files with proper permissions
- Consider using credential management tools

### 2. File Permissions

Set appropriate permissions on configuration files:

```bash
# Secure configuration directory
chmod 700 ~/.ncp/ ~/.ncpgov/
chmod 600 ~/.ncp/config ~/.ncpgov/config
```

### 3. Environment Variables

When using environment variables, ensure they are not exposed in logs or process list.

## Multiple Environments

### Environment-Specific Configuration

You can maintain separate configurations for different environments:

```yaml
# ~/.ncp/config
environments:
  development:
    access_key: "dev_access_key"
    secret_key: "dev_secret_key"
    region: "KR"
  
  production:
    access_key: "prod_access_key"
    secret_key: "prod_secret_key"
    region: "KR"

default_environment: "development"
```

### Using Different Environments

```bash
# Use specific environment
ic ncp ec2 info --env production

# Set default environment
ic config set default_environment production
```

## Regional Configuration

### Supported Regions

| Region Code | Location | Description |
|-------------|----------|-------------|
| KR | Korea | Korea (Seoul) - Primary region |
| US | United States | US (Virginia) - Global region |
| JP | Japan | Japan (Tokyo) - Asia Pacific |

### Multi-Region Setup

```yaml
# ~/.ncp/config - Multi-region configuration
default:
  access_key: "your-access-key"
  secret_key: "your-secret-key"
  region: "KR"

us-region:
  access_key: "us-access-key"
  secret_key: "us-secret-key"
  region: "US"

jp-region:
  access_key: "jp-access-key"
  secret_key: "jp-secret-key"
  region: "JP"
```

## Platform Configuration

### VPC vs Classic Platform

```yaml
# ~/.ncp/config
default:
  access_key: "your-access-key"
  secret_key: "your-secret-key"
  region: "KR"
  platform: "VPC"  # or "Classic"

# VPC platform provides:
# - VPC and subnet information
# - Enhanced security group details
# - Advanced networking features

# Classic platform provides:
# - Basic instance information
# - Legacy networking details
# - Limited security group info
```

## Troubleshooting Configuration

### Common Issues

#### Issue: Invalid credentials
```
Error: Authentication failed
```
**Solution**: Verify your access key and secret key are correct in NCP console.

#### Issue: Configuration file not found
```
Error: Configuration file not found
```
**Solution**: Run `ic config init` to create the configuration structure.

#### Issue: Permission denied
```
Error: Permission denied accessing configuration
```
**Solution**: Check file permissions on configuration directory and files.

### Validation Commands

```bash
# Validate configuration
ic config validate --platform ncp

# Test connectivity
ic ncp ec2 info --debug

# Show current configuration (without sensitive data)
ic config show --platform ncp
```

## Configuration Migration

If you have existing configuration files, you can migrate them:

```bash
# Migrate from old configuration format
ic config migrate --platform ncp

# Import configuration from file
ic config import --platform ncp --file /path/to/config.yaml
```

## Next Steps

After configuring NCP:

1. Test your setup with basic commands from the [Usage Guide](usage.md)
2. Explore available services and features
3. Set up any additional security measures as needed