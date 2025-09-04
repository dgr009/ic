# Installation Guide

This guide provides secure installation instructions for IC (Infra Resource Management CLI).

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+** (Python 3.9+ recommended)
- **pip** (latest version)
- **Virtual environment** (recommended)

### Basic Installation

```bash
# Install from PyPI
pip install ic

# Verify installation
ic --version
```

## 🔒 Secure Installation

### 1. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv ic-env

# Activate virtual environment
# On macOS/Linux:
source ic-env/bin/activate
# On Windows:
ic-env\Scripts\activate

# Install IC
pip install ic
```

### 2. Install with Security Dependencies

```bash
# Install with security tools
pip install ic[security]

# Or install with development tools
pip install ic[dev]

# Or install everything
pip install ic[dev,security,test]
```

## 🛠️ Development Installation

### From Source

```bash
# Clone repository
git clone https://github.com/dgr009/ic.git
cd ic

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .[dev]

# Install pre-commit hooks
pre-commit install
```

### Verify Development Installation

```bash
# Run tests
pytest

# Check code formatting
black --check src/

# Run linting
flake8 src/

# Type checking
mypy src/
```

## ⚙️ Initial Configuration

### 1. Initialize Configuration

```bash
# Create initial secure configuration
ic config init

# This creates:
# - config.yaml (your configuration file)
# - .gitignore entries for security
# - Example environment variable file
```

### 2. Set Up Environment Variables

Create a `.env` file or set environment variables:

```bash
# AWS Configuration
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"

# Azure Configuration
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"

# GCP Configuration
export GCP_SERVICE_ACCOUNT_KEY_PATH="/path/to/service-account.json"
# OR
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# OCI Configuration (uses ~/.oci/config by default)
export OCI_CONFIG_FILE="~/.oci/config"

# CloudFlare Configuration
export CLOUDFLARE_EMAIL="your-email@example.com"
export CLOUDFLARE_API_TOKEN="your-api-token"

# Optional: Slack notifications
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

### 3. Configure Cloud Provider CLIs

#### AWS CLI
```bash
# Install AWS CLI
pip install awscli

# Configure AWS CLI
aws configure

# Or use profiles
aws configure --profile production
```

#### Azure CLI
```bash
# Install Azure CLI
pip install azure-cli

# Login to Azure
az login

# Set default subscription
az account set --subscription "your-subscription-id"
```

#### GCP CLI
```bash
# Install Google Cloud SDK
# Follow instructions at: https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login

# Set default project
gcloud config set project your-project-id

# Create service account (for production)
gcloud iam service-accounts create ic-service-account
gcloud iam service-accounts keys create ~/gcp-key/service-account.json \
    --iam-account ic-service-account@your-project.iam.gserviceaccount.com
```

#### OCI CLI
```bash
# Install OCI CLI
pip install oci-cli

# Configure OCI CLI
oci setup config
```

## 🔐 Security Setup

### 1. File Permissions

```bash
# Secure configuration files
chmod 600 config.yaml
chmod 600 .env
chmod 700 ~/.aws/
chmod 600 ~/.aws/credentials
chmod 600 ~/.aws/config
chmod 700 ~/.oci/
chmod 600 ~/.oci/config
```

### 2. Git Security

```bash
# Install pre-commit hooks (if developing)
pre-commit install

# Verify .gitignore includes sensitive files
cat .gitignore | grep -E "(config\.yaml|\.env|\.key|\.pem)"
```

### 3. Validate Security

```bash
# Validate configuration security
ic config validate

# Check for sensitive data in configuration
ic config security-check
```

## 🧪 Verify Installation

### 1. Basic Functionality

```bash
# Check version
ic --version

# List available commands
ic --help

# Test configuration
ic config show
```

### 2. Test Cloud Connections

```bash
# Test AWS connection
ic aws ec2 info --dry-run

# Test Azure connection
ic azure vm info --dry-run

# Test GCP connection
ic gcp compute info --dry-run

# Test OCI connection
ic oci vm info --dry-run
```

### 3. Test Security Features

```bash
# Test sensitive data masking
ic config show --include-sensitive

# Test logging
ic aws ec2 info --verbose
# Check logs in logs/ directory
```

## 🔄 Migration from Previous Versions

### From .env-based Configuration

```bash
# Migrate existing .env configuration
ic config migrate

# Verify migration
ic config validate

# Test migrated configuration
ic config show
```

### Update Existing Scripts

Most existing scripts should work without changes due to backward compatibility. However, consider updating to use the new configuration system:

```python
# Old way (still works)
from ic.cli import main

# New way (recommended)
from ic import ConfigManager, ICLogger

config = ConfigManager()
logger = ICLogger(config)
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Permission Denied
```bash
# Fix file permissions
chmod 600 config.yaml ~/.aws/credentials ~/.oci/config

# Fix directory permissions
chmod 700 ~/.aws ~/.oci ~/.ic
```

#### 2. Missing Dependencies
```bash
# Reinstall with all dependencies
pip install --upgrade ic[dev,security]

# Or install specific cloud SDK
pip install boto3  # AWS
pip install azure-cli  # Azure
pip install google-cloud-sdk  # GCP
```

#### 3. Configuration Errors
```bash
# Validate configuration
ic config validate

# Reset configuration
ic config init --force

# Check environment variables
ic config env-check
```

#### 4. Import Errors
```bash
# Check Python path
python -c "import ic; print(ic.__file__)"

# Reinstall in development mode
pip install -e .
```

### Getting Help

1. **Check logs**: Look in `logs/ic_YYYYMMDD.log`
2. **Validate configuration**: Run `ic config validate`
3. **Check GitHub issues**: [https://github.com/dgr009/ic/issues](https://github.com/dgr009/ic/issues)
4. **Security issues**: Email cruiser594@gmail.com

## 📚 Next Steps

After installation:

1. **Read the [Configuration Guide](configuration.md)** for detailed configuration options
2. **Review [Security Policy](../SECURITY.md)** for security best practices
3. **Check [Migration Guide](migration.md)** if upgrading from older versions
4. **Explore the [README](../README.md)** for usage examples

## 🔄 Updating

### Regular Updates

```bash
# Update to latest version
pip install --upgrade ic

# Check for security updates
pip list --outdated | grep ic
```

### Security Updates

Security updates are released as patch versions. Always update promptly:

```bash
# Update immediately for security patches
pip install --upgrade ic

# Verify security features
ic config security-check
```

---

For more information:
- [Configuration Guide](configuration.md)
- [Security Policy](../SECURITY.md)
- [Migration Guide](migration.md)
- [GitHub Repository](https://github.com/dgr009/ic)