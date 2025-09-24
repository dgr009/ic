# NCPGOV Installation Guide

This guide covers the installation and initial setup of NCPGOV (Naver Cloud Platform Government) integration for the IC CLI tool.

## Prerequisites

- Python 3.9 or higher (3.11.13 recommended)
- IC CLI tool installed
- NCPGOV account with appropriate permissions
- Internet access to NCPGOV APIs
- Enhanced security clearance for government cloud access

## Installation Steps

### 1. Install Dependencies

```bash
# Install the IC CLI tool if not already installed
pip install ic-code

# Verify NCPGOV support is available (no separate SDK needed)
ic ncpgov --help        # Should show NCPGOV commands
```

### 2. Verify Installation

```bash
# Test NCPGOV module imports
python -c "from ncpgov_module.client import NCPGovClient; print('NCPGOV client: OK')"

# Verify core dependencies
python -c "import requests, yaml, cryptography; print('NCPGOV dependencies: OK')"
```

### 3. Initial Configuration

After installation, you'll need to configure your NCPGOV credentials. See the [Configuration Guide](configuration.md) for detailed instructions.

## Platform-Specific Requirements

### System Requirements

- Operating System: Linux, macOS, or Windows
- Memory: Minimum 512MB RAM
- Disk Space: 100MB free space
- Security: Enhanced security compliance for government cloud

### NCPGOV Requirements

- Valid NCPGOV (Naver Cloud Platform Government) account
- Government cloud access clearance
- API access enabled with enhanced security
- Access Key, Secret Key, and API Gateway Key
- Compliance with government cloud security policies

### Core Dependencies

IC CLI includes built-in NCPGOV support without requiring external SDKs:

```
requests>=2.28.0,<3.0.0           # HTTP client for NCPGOV API calls
PyYAML>=6.0,<=6.0.2               # Configuration file parsing
cryptography>=3.4.8,<42.0.0       # HMAC-SHA256 signature generation
rich>=12.0.0,<15.0.0              # Terminal output formatting
click>=8.0.0,<9.0.0               # CLI framework
```

## Government Cloud Specific Setup

### Enhanced Security Requirements

NCPGOV requires additional security measures:

1. **API Gateway Key**: Required for government cloud API access
2. **Compliance Mode**: Must be enabled for government cloud operations
3. **Audit Logging**: Required for compliance tracking
4. **Data Encryption**: Enhanced encryption for sensitive data
5. **Access Control**: Stricter access control policies

### Security Configuration

```bash
# Enable enhanced security features during installation
export NCPGOV_SECURITY_LEVEL=high
export NCPGOV_COMPLIANCE_MODE=true
export NCPGOV_AUDIT_LOGGING=true
```

## Alternative Installation Methods

### Method 1: Source Installation

```bash
# Clone repository
git clone https://github.com/dgr009/ic.git
cd ic

# Create virtual environment
python -m venv ncpgov-env
source ncpgov-env/bin/activate  # On Windows: ncpgov-env\Scripts\activate

# Install with NCPGOV dependencies
pip install -r requirements.txt
pip install -e .

# Verify installation
ic ncpgov --help
```

### Method 2: Docker Installation

```bash
# Pull IC CLI Docker image (includes NCPGOV support)
docker pull ic-cli:latest

# Run with NCPGOV configuration mounted
docker run -v ~/.ncpgov:/root/.ncpgov ic-cli:latest ic ncpgov ec2 info
```

## Government Cloud Access Setup

### Getting NCPGOV Access

1. **Contact NCP**: Request government cloud access through official channels
2. **Security Clearance**: Complete required security clearance process
3. **Account Setup**: Set up NCPGOV account with enhanced security
4. **API Keys**: Generate API keys with government cloud permissions
5. **API Gateway**: Obtain API Gateway key for government cloud access

### API Key Generation

1. Access NCPGOV Console (URL provided by NCP)
2. Navigate to **Security** → **API Management**
3. Generate **Government API Key** with required permissions
4. Generate **API Gateway Key** for enhanced security
5. Follow government cloud security procedures

## Troubleshooting Installation

### Common Issues

#### Issue: ModuleNotFoundError: No module named 'ncpgov_module'
```bash
# Solution: IC CLI includes built-in NCPGOV support
pip install --upgrade ic-code

# Verify NCPGOV modules are available
python -c "from ncpgov_module.client import NCPGovClient; print('NCPGOV module: OK')"
```

#### Issue: Government cloud access denied
```bash
# Solution: Verify government cloud access and API Gateway key
ic config get ncpgov.apigw_key

# Ensure compliance mode is enabled
ic config set ncpgov.compliance_mode true
```

#### Issue: Enhanced security validation failed
```bash
# Solution: Enable all required security features
ic config set ncpgov.security.encryption_enabled true
ic config set ncpgov.security.audit_logging_enabled true
ic config set ncpgov.security.access_control_enabled true
```

### Security-Specific Issues

#### Issue: Compliance validation failed
```bash
# Solution: Enable compliance mode and security features
ic config set ncpgov.compliance_mode true
ic config set ncpgov.security_level "high"

# Verify compliance settings
ic config validate --platform ncpgov --compliance
```

#### Issue: API Gateway authentication failed
```bash
# Solution: Verify API Gateway key configuration
ic config get ncpgov.apigw_key

# Test API Gateway connectivity
curl -X GET "https://apigw.gov-ntruss.com/health" \
  -H "x-ncp-apigw-api-key: $(ic config get ncpgov.apigw_key)"
```

### Getting Help

If you encounter issues during installation:

1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Verify all prerequisites are met
3. Ensure government cloud access is properly configured
4. Check compliance and security requirements
5. Contact NCPGOV support for government cloud specific issues

## Security and Compliance

### Required Security Settings

After installation, ensure these security settings are configured:

```bash
# Enable compliance mode
ic config set ncpgov.compliance_mode true

# Set high security level
ic config set ncpgov.security_level "high"

# Enable audit logging
ic config set ncpgov.security.audit_logging_enabled true

# Enable data encryption
ic config set ncpgov.security.encryption_enabled true

# Enable access control
ic config set ncpgov.security.access_control_enabled true

# Enable sensitive data masking
ic config set ncpgov.security.mask_sensitive_data true
```

### Verify Security Configuration

```bash
# Validate security configuration
ic config validate --platform ncpgov --security

# Test compliance features
ic ncpgov ec2 info --compliance-check

# Verify audit logging
ic ncpgov s3 info --audit-trail
```

## Next Steps

After successful installation:

1. Configure your NCPGOV credentials using the [Configuration Guide](configuration.md)
2. Learn how to use NCPGOV commands in the [Usage Guide](usage.md)
3. Test your setup with basic commands:
   ```bash
   ic ncpgov ec2 info --compliance-check
   ic ncpgov s3 info --encryption-status
   ```
4. Ensure all security and compliance requirements are met
5. Set up audit logging and monitoring as required