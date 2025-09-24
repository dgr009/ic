# {PLATFORM} Configuration Guide

This guide explains how to configure {PLATFORM} credentials and settings for the IC CLI tool.

## Configuration Overview

The IC CLI tool uses a hierarchical configuration system to manage {PLATFORM} credentials and settings:

1. Project-specific configuration (`./.ic/config/`)
2. User home configuration (`~/.ic/config/`)
3. Platform-specific configuration (`~/.{platform_dir}/`)
4. Environment variables
5. Default settings

## Initial Configuration

### 1. Run Configuration Setup

```bash
# Initialize configuration for all platforms
ic config init

# Initialize configuration for {PLATFORM} only
ic config init --platform {platform_name}
```

This will create the necessary configuration directories and files.

### 2. Configure Credentials

#### Method 1: Configuration File

Edit the configuration file at `~/.{platform_dir}/config.yaml`:

```yaml
# {PLATFORM} Configuration
credentials:
  access_key: "your_access_key"
  secret_key: "your_secret_key"
  region: "your_default_region"

# Additional settings
settings:
  timeout: 30
  retry_attempts: 3
  output_format: "table"
```

#### Method 2: Environment Variables

Set environment variables in your shell or `.env` file:

```bash
export {PLATFORM_PREFIX}_ACCESS_KEY="your_access_key"
export {PLATFORM_PREFIX}_SECRET_KEY="your_secret_key"
export {PLATFORM_PREFIX}_REGION="your_default_region"
```

### 3. Verify Configuration

```bash
# Test {PLATFORM} connectivity
ic {platform_command} info

# Check configuration status
ic config status --platform {platform_name}
```

## Configuration Options

### Credentials

| Setting | Description | Required | Default |
|---------|-------------|----------|---------|
| `access_key` | {PLATFORM} access key | Yes | - |
| `secret_key` | {PLATFORM} secret key | Yes | - |
| `region` | Default region | Yes | - |

### Advanced Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `timeout` | Request timeout in seconds | 30 |
| `retry_attempts` | Number of retry attempts | 3 |
| `output_format` | Default output format (table/json/yaml) | table |
| `debug` | Enable debug logging | false |

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
chmod 700 ~/.{platform_dir}/
chmod 600 ~/.{platform_dir}/config.yaml
```

### 3. Environment Variables

When using environment variables, ensure they are not exposed in logs or process lists.

## Multiple Environments

### Environment-Specific Configuration

You can maintain separate configurations for different environments:

```yaml
# ~/.{platform_dir}/config.yaml
environments:
  development:
    access_key: "dev_access_key"
    secret_key: "dev_secret_key"
    region: "dev_region"
  
  production:
    access_key: "prod_access_key"
    secret_key: "prod_secret_key"
    region: "prod_region"

default_environment: "development"
```

### Using Different Environments

```bash
# Use specific environment
ic {platform_command} info --env production

# Set default environment
ic config set default_environment production
```

## Troubleshooting Configuration

### Common Issues

#### Issue: Invalid credentials
```
Error: Authentication failed
```
**Solution**: Verify your access key and secret key are correct.

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
ic config validate --platform {platform_name}

# Test connectivity
ic {platform_command} info --debug

# Show current configuration (without sensitive data)
ic config show --platform {platform_name}
```

## Configuration Migration

If you have existing configuration files, you can migrate them:

```bash
# Migrate from old configuration format
ic config migrate --platform {platform_name}

# Import configuration from file
ic config import --platform {platform_name} --file /path/to/config.yaml
```

## Next Steps

After configuring {PLATFORM}:

1. Test your setup with basic commands from the [Usage Guide](usage.md)
2. Explore available services and features
3. Set up any additional security measures as needed