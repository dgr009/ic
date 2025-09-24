# AWS Installation Guide

This guide covers the installation and initial setup of AWS (Amazon Web Services) integration for the IC CLI tool.

## Prerequisites

- Python 3.9 or higher
- IC CLI tool installed
- AWS account with appropriate permissions
- Internet access to AWS APIs

## Installation Steps

### 1. Install Dependencies

```bash
# Install the IC CLI tool if not already installed
pip install ic-code

# Verify AWS support is available
ic aws --help        # Should show AWS commands
```

### 2. Verify Installation

```bash
# Test AWS module imports
python -c "from aws.ec2 import info; print('AWS EC2 module: OK')"
python -c "from aws.s3 import info; print('AWS S3 module: OK')"

# Verify core dependencies
python -c "import boto3, botocore; print('AWS SDK dependencies: OK')"
```

### 3. Initial Configuration

After installation, you'll need to configure your AWS credentials. See the [Configuration Guide](configuration.md) for detailed instructions.

## Platform-Specific Requirements

### System Requirements

- Operating System: Linux, macOS, or Windows
- Memory: Minimum 512MB RAM
- Disk Space: 100MB free space

### AWS Requirements

- Valid AWS account
- IAM user with programmatic access
- Required permissions for services you plan to use
- AWS CLI configured (optional but recommended)

### Core Dependencies

The AWS integration uses the official AWS SDK:

```
boto3>=1.26.0                     # AWS SDK for Python
botocore>=1.29.0                  # Core AWS SDK functionality
requests>=2.28.0                  # HTTP client
```

## AWS CLI Integration

The IC CLI integrates with existing AWS CLI configuration:

```bash
# If you have AWS CLI configured, IC CLI will use the same credentials
aws configure list

# Test AWS connectivity
ic aws ec2 info
```

## Troubleshooting Installation

### Common Issues

#### Issue: Command not found
```bash
ic: aws: command not found
```
**Solution**: Ensure AWS integration is properly installed and in your PATH.

#### Issue: Missing AWS SDK
```bash
ModuleNotFoundError: No module named 'boto3'
```
**Solution**: Install AWS SDK dependencies:
```bash
pip install boto3 botocore
```

#### Issue: AWS credentials not configured
```bash
Error: Unable to locate credentials
```
**Solution**: Configure AWS credentials using the [Configuration Guide](configuration.md).

### Getting Help

If you encounter issues during installation:

1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Verify all prerequisites are met
3. Check AWS CLI configuration: `aws configure list`
4. Check the main project documentation
5. Report issues on the project repository

## Next Steps

After successful installation:

1. Configure your AWS credentials using the [Configuration Guide](configuration.md)
2. Learn how to use AWS commands in the [Usage Guide](usage.md)
3. Test your setup with basic commands:
   ```bash
   ic aws ec2 info
   ic aws s3 info
   ```