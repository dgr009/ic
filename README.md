# IC CLI Tool

[![Tests](https://github.com/dgr009/ic/workflows/Tests/badge.svg)](https://github.com/dgr009/ic/actions)
[![PyPI version](https://badge.fury.io/py/ic-code.svg)](https://badge.fury.io/py/ic-code)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive Infrastructure Command Line Interface tool for managing cloud services and infrastructure components across multiple platforms. IC CLI provides unified access to AWS, Oracle Cloud Infrastructure (OCI), CloudFlare, and SSH server management with rich progress indicators and secure configuration management.

## ✨ Features

- **🚀 Multi-Cloud Support**: AWS, OCI, CloudFlare, SSH server management
- **📊 Rich Progress Bars**: Real-time progress indicators for all long-running operations
- **🔒 Secure Configuration**: YAML-based configuration with separate secrets management
- **🌍 Multi-Account/Multi-Region**: Support for multiple cloud accounts and regions
- **🎨 Beautiful Output**: Rich terminal output with tables, colors, and formatting
- **⚡ High Performance**: Optimized for speed with concurrent operations
- **🛡️ Security First**: Built-in security validation and credential protection

### Supported Services

#### AWS Services (Production Ready)
- **Compute**: EC2 instances, ECS services, EKS clusters, Fargate
- **Storage**: S3 buckets, RDS databases
- **Networking**: VPC, Load Balancers, Security Groups, VPN
- **Other**: CloudFront distributions, MSK clusters, CodePipeline

#### Oracle Cloud Infrastructure (Production Ready)
- **Compute**: VM instances, Container Instances
- **Networking**: VCN, Load Balancers, Network Security Groups
- **Storage**: Block volumes, Object storage
- **Management**: Compartments, Policies, Cost analysis

#### CloudFlare (Production Ready)
- **DNS**: Zone and record management with filtering

#### SSH Management (Production Ready)
- **Server Discovery**: Automatic server registration and information gathering
- **Security**: Built-in security filtering and connection management

#### Development Status
- **⚠️ Azure**: In development - usable but may contain bugs
- **⚠️ GCP**: In development - usable but may contain bugs

## 📦 Installation

### Prerequisites

- **Python**: 3.9 or higher (3.11.13 recommended)
- **Operating System**: macOS, Linux, or Windows
- **Dependencies**: All dependencies are automatically installed via pip

### From PyPI (Recommended)

```bash
# Install the latest stable version
pip install ic-code

# Verify installation
ic --help
```

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/dgr009/ic.git
cd ic

# Create and activate virtual environment
python -m venv ic-env
source ic-env/bin/activate  # On Windows: ic-env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Verify installation
ic --help
```

### Dependency Validation

IC CLI automatically validates all required dependencies on startup and provides clear error messages for missing packages. The tool supports **Python 3.9-3.12** with **Python 3.11.13** recommended for optimal performance.

#### Automatic Validation
```bash
# IC CLI validates dependencies automatically
ic --help  # Will show dependency errors if any exist

# Manual dependency validation
python scripts/validate_dependencies.py

# Comprehensive compatibility testing
python scripts/test_dependency_compatibility.py --report
```

#### Troubleshooting Dependencies
```bash
# Check Python version compatibility
python --version  # Should be 3.9+ to 3.12

# Install/update all dependencies
pip install --upgrade -r requirements.txt

# Install missing dependencies automatically
python scripts/validate_dependencies.py --install-missing

# Test requirements.txt installation
python scripts/validate_dependencies.py --test-requirements

# Validate specific platform dependencies
python scripts/validate_dependencies.py --platforms aws oci
```

#### Supported Python Versions
- **Python 3.9**: Minimum supported version
- **Python 3.10**: Fully supported
- **Python 3.11**: Recommended (tested with 3.11.13)
- **Python 3.12**: Fully supported
- **Python 3.13+**: Not yet tested (may work but not guaranteed)

## ⚙️ Configuration

IC CLI uses a modern, secure YAML-based configuration system that separates default settings from sensitive credentials.

### Quick Setup

The fastest way to get started is using the built-in configuration initializer:

```bash
# Initialize configuration with guided setup
ic config init

# This creates:
# - ~/.ic/config/default.yaml (default settings)
# - ~/.ic/config/secrets.yaml.example (template for secrets)
# - Updates .gitignore for security
```

### Configuration Structure

IC CLI uses a two-file configuration system for security:

```
~/.ic/config/
├── default.yaml        # Non-sensitive default settings
└── secrets.yaml        # Your sensitive credentials (create from example)
```

### Step-by-Step Configuration

#### 1. Initialize Configuration

```bash
# Create configuration directory and files
ic config init

# For specific cloud platforms
ic config init --template aws      # AWS-focused setup
ic config init --template multi-cloud  # All platforms
```

#### 2. Configure Credentials

Copy the example secrets file and add your credentials:

```bash
# Copy the example file
cp ~/.ic/config/secrets.yaml.example ~/.ic/config/secrets.yaml

# Edit with your actual credentials
vim ~/.ic/config/secrets.yaml
```

#### 3. Example Secrets Configuration

```yaml
# ~/.ic/config/secrets.yaml
# AWS Configuration
aws:
  accounts:
    - "123456789012"  # Your AWS account IDs
    - "987654321098"
  profiles:
    default: "your-aws-profile-name"
  regions:
    - "ap-northeast-2"
    - "us-east-1"

# Oracle Cloud Infrastructure
oci:
  config_file: "~/.oci/config"
  profile: "DEFAULT"
  compartments:
    - "ocid1.compartment.oc1..example"

# CloudFlare Configuration  
cloudflare:
  email: "your-email@example.com"
  api_token: "your-cloudflare-api-token"
  accounts: ["account1", "account2"]  # Filter specific accounts
  zones: ["example.com", "test.com"]  # Filter specific zones

# SSH Configuration
ssh:
  key_dir: "~/aws-keys"
  timeout: 30
  skip_prefixes:  # Skip servers with these prefixes for security
    - "git"
    - "bastion"
    - "jump"
    - "proxy"
```

#### 4. Platform-Specific Setup

**AWS Credentials:**
```bash
# Configure AWS CLI (if not already done)
aws configure

# Or use specific profiles
aws configure --profile production
aws configure --profile development
```

**OCI Configuration:**
```bash
# Install OCI CLI and configure
oci setup config

# Verify configuration
oci iam user get --user-id $(oci iam user list --query 'data[0].id' --raw-output)
```

**CloudFlare API Token:**
1. Go to CloudFlare Dashboard → My Profile → API Tokens
2. Create token with Zone:Read permissions
3. Add token to secrets.yaml

### Configuration Management Commands

```bash
# Validate configuration
ic config validate

# Show current configuration (sensitive data masked)
ic config show

# Show only AWS configuration
ic config show --aws

# Get specific configuration value
ic config get aws.regions

# Set configuration value
ic config set aws.regions '["us-east-1", "ap-northeast-2"]'

# Migrate from old .env configuration
ic config migrate
```

## 🚀 Usage

All IC CLI commands feature rich progress bars that show real-time progress for long-running operations, making it easy to monitor multi-region and multi-account queries.

### AWS Services

#### Compute Services
```bash
# EC2 instances with progress tracking
ic aws ec2 info
ic aws ec2 info --account 123456789012 --regions us-east-1,ap-northeast-2

# ECS services and tasks
ic aws ecs info          # List all ECS clusters and services
ic aws ecs service       # Detailed service information
ic aws ecs task          # Running task information

# EKS clusters and workloads
ic aws eks info          # Cluster information
ic aws eks nodes         # Node group details
ic aws eks pods          # Pod status across clusters
ic aws eks addons       # EKS add-on information
ic aws eks fargate      # Fargate profile details

# Fargate services
ic aws fargate info      # Fargate service information
```

#### Storage Services
```bash
# S3 buckets with tag management
ic aws s3 list_tags      # List all S3 buckets with tags
ic aws s3 tag_check      # Validate S3 bucket tagging compliance
ic aws s3 info           # Detailed S3 bucket information

# RDS databases
ic aws rds info          # RDS instance and cluster information
ic aws rds list_tags     # RDS resource tags
ic aws rds tag_check     # RDS tagging compliance
```

#### Networking Services
```bash
# VPC and networking
ic aws vpc info          # VPC, subnet, and gateway information
ic aws vpc list_tags     # VPC resource tags
ic aws vpc tag_check     # VPC tagging compliance

# Load Balancers
ic aws lb info           # Load balancer details
ic aws lb list_tags      # Load balancer tags
ic aws lb tag_check      # Load balancer tagging compliance

# Security Groups
ic aws sg info           # Security group rules and associations

# VPN connections
ic aws vpn info          # VPN gateway and connection information
```

#### Other AWS Services
```bash
# CloudFront distributions
ic aws cloudfront info   # CloudFront distribution details

# MSK (Managed Streaming for Kafka)
ic aws msk info          # MSK cluster information
ic aws msk broker        # Kafka broker details

# CodePipeline
ic aws codepipeline build   # Build pipeline status
ic aws codepipeline deploy  # Deployment pipeline information
```

### Oracle Cloud Infrastructure (OCI)

#### Compute and Containers
```bash
# VM instances across compartments
ic oci vm info           # VM instances with detailed information
ic oci vm info --compartment-name "Production"

# Container instances
ic oci aci info          # Container instance details
```

#### Networking
```bash
# Virtual Cloud Networks
ic oci vcn info          # VCN, subnet, and routing information

# Load Balancers
ic oci lb info           # Load balancer configurations

# Network Security Groups
ic oci nsg info          # NSG rules and associations
```

#### Storage and Management
```bash
# Block and object storage
ic oci volume info       # Block volume details
ic oci obj info          # Object storage bucket information

# Identity and policies
ic oci policy info       # IAM policies and permissions
ic oci policy search     # Search policies by criteria

# Cost management
ic oci cost usage        # Usage and cost analysis
ic oci cost credit       # Credit and billing information

# Compartment management
ic oci compartment info  # Compartment hierarchy and details
```

### CloudFlare DNS Management

```bash
# DNS records (automatically filtered by configured accounts/zones)
ic cf dns info                    # All DNS records
ic cf dns info --account prod     # Specific account
ic cf dns info --zone example.com # Specific zone

# The command respects your configuration filters for security
```

### SSH Server Management

```bash
# Server information with security filtering
ic ssh info              # Information about all registered servers

# Auto-discovery (respects skip_prefixes in configuration)
ic ssh reg               # Discover and register new SSH servers
```

### Configuration Management

```bash
# Configuration setup and validation
ic config init           # Initialize configuration
ic config validate       # Validate current configuration
ic config show           # Display current configuration (masked)
ic config show --aws     # Show only AWS configuration

# Configuration migration
ic config migrate        # Migrate from .env to YAML configuration

# Configuration management
ic config get aws.regions              # Get specific value
ic config set aws.regions '["us-east-1"]'  # Set specific value
```

### Multi-Account and Multi-Region Examples

```bash
# Query multiple AWS accounts and regions
ic aws ec2 info --account 123456789012,987654321098 --regions us-east-1,ap-northeast-2,eu-west-1

# OCI multi-compartment queries
ic oci vm info --compartment-name "Production,Development,Testing"

# All commands show progress bars for long-running operations
```

## 📋 Command Structure

IC CLI follows a consistent, intuitive command structure across all platforms:

```
ic <platform> <service> <command> [options]
```

### Command Components

- **platform**: `aws`, `oci`, `cf` (CloudFlare), `ssh`, `config`
- **service**: `ec2`, `s3`, `ecs`, `eks`, `rds`, `vm`, `lb`, `dns`, etc.
- **command**: `info`, `list_tags`, `tag_check`, etc.
- **options**: `--account`, `--regions`, `--compartment-name`, etc.

### Common Options

Most commands support these common options:

```bash
# AWS-specific options
--account ACCOUNT_ID     # Target specific AWS account(s)
--regions REGION_LIST    # Target specific AWS region(s)
--profile PROFILE_NAME   # Use specific AWS profile

# OCI-specific options
--compartment-name NAME  # Target specific OCI compartment(s)
--region REGION_NAME     # Target specific OCI region

# CloudFlare-specific options
--account ACCOUNT_NAME   # Target specific CloudFlare account
--zone ZONE_NAME         # Target specific DNS zone

# Output options (available on most commands)
--output json           # JSON output format
--output table          # Table output format (default)
--verbose              # Detailed output
--quiet                # Minimal output
```

## 💡 Advanced Examples

### Multi-Cloud Infrastructure Audit

```bash
# AWS infrastructure overview
ic aws ec2 info --regions us-east-1,ap-northeast-2
ic aws rds info --account 123456789012
ic aws s3 tag_check

# OCI infrastructure overview  
ic oci vm info --compartment-name "Production"
ic oci lb info
ic oci cost usage

# CloudFlare DNS audit
ic cf dns info --zone production-domain.com
```

### Security and Compliance Checks

```bash
# AWS tagging compliance
ic aws ec2 tag_check     # Check EC2 instance tagging
ic aws s3 tag_check      # Check S3 bucket tagging
ic aws rds tag_check     # Check RDS tagging
ic aws lb tag_check      # Check Load Balancer tagging
ic aws vpc tag_check     # Check VPC resource tagging

# OCI policy and security review
ic oci policy info       # Review IAM policies
ic oci nsg info          # Review network security groups
```

### Cost and Resource Management

```bash
# AWS resource inventory
ic aws ec2 info --regions all    # All EC2 instances across regions
ic aws rds info --account all    # All RDS instances across accounts
ic aws s3 info                   # All S3 buckets

# OCI cost analysis
ic oci cost usage               # Usage and cost breakdown
ic oci cost credit              # Credit and billing status
ic oci compartment info         # Resource organization
```

### Development Status Examples

⚠️ **Note**: Azure and GCP features are in development. While usable, they may contain bugs:

```bash
# Azure (Development - may have issues)
ic azure --help                # Shows development warning
ic azure vm info               # Basic VM information
ic azure aks info              # AKS cluster details

# GCP (Development - may have issues)  
ic gcp --help                  # Shows development warning
ic gcp compute info            # Compute Engine instances
ic gcp gke info                # GKE cluster information
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### Installation Issues

**Problem**: `pip install ic-code` fails with dependency conflicts
```bash
# Solution: Use a virtual environment
python -m venv ic-env
source ic-env/bin/activate  # On Windows: ic-env\Scripts\activate
pip install --upgrade pip
pip install ic-code
```

**Problem**: Python version compatibility issues
```bash
# Check Python version (3.9+ required, 3.11.13 recommended)
python --version

# Install compatible Python version using pyenv (recommended)
pyenv install 3.11.13
pyenv local 3.11.13
```

#### Configuration Issues

**Problem**: `ic config validate` shows validation errors
```bash
# Check configuration file syntax
ic config show --verbose

# Reinitialize configuration
ic config init --force

# Migrate from old .env configuration
ic config migrate
```

**Problem**: AWS credentials not found
```bash
# Configure AWS CLI
aws configure

# Verify AWS credentials
aws sts get-caller-identity

# Check IC configuration
ic config show --aws
```

**Problem**: OCI configuration issues
```bash
# Verify OCI CLI configuration
oci setup config

# Test OCI connectivity
oci iam user get --user-id $(oci iam user list --query 'data[0].id' --raw-output)

# Check IC OCI configuration
ic config get oci.config_file
```

#### Runtime Issues

**Problem**: Commands hang or timeout
```bash
# Check network connectivity
ping aws.amazon.com
ping oracle.com

# Increase timeout in configuration
ic config set aws.timeout 60
ic config set oci.timeout 60
```

**Problem**: Permission denied errors
```bash
# Check file permissions
ls -la ~/.ic/config/

# Fix permissions
chmod 600 ~/.ic/config/secrets.yaml
chmod 755 ~/.ic/config/
```

**Problem**: Progress bars not displaying correctly
```bash
# Check terminal compatibility
echo $TERM

# Force simple output if needed
export IC_SIMPLE_OUTPUT=1
ic aws ec2 info
```

#### Platform-Specific Issues

**AWS Issues:**
- Ensure AWS CLI is configured: `aws configure`
- Check account access: `aws sts get-caller-identity`
- Verify region availability: `aws ec2 describe-regions`

**OCI Issues:**
- Verify OCI CLI setup: `oci setup config`
- Check compartment access: `oci iam compartment list`
- Validate API key: `oci iam user get --user-id <user-id>`

**CloudFlare Issues:**
- Verify API token permissions in CloudFlare dashboard
- Check zone access: Test with CloudFlare API directly
- Ensure account/zone filters are correct in configuration

### Getting Help

```bash
# General help
ic --help

# Platform-specific help
ic aws --help
ic oci --help
ic cf --help

# Service-specific help
ic aws ec2 --help
ic oci vm --help

# Configuration help
ic config --help
```

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Set debug logging level
ic config set logging.level DEBUG

# Run command with verbose output
ic aws ec2 info --verbose

# Check log files
tail -f ~/.ic/logs/ic.log
```

## 🚧 Development Status

### Production Ready Platforms
- ✅ **AWS**: Fully tested and production ready
- ✅ **OCI**: Fully tested and production ready  
- ✅ **CloudFlare**: Fully tested and production ready
- ✅ **SSH**: Fully tested and production ready

### Development Platforms
- ⚠️ **Azure**: In active development
  - Basic functionality implemented
  - May contain bugs or incomplete features
  - Use with caution in production environments
  - Help shows development status warning: `ic azure --help`

- ⚠️ **GCP**: In active development
  - Basic functionality implemented
  - May contain bugs or incomplete features
  - Use with caution in production environments
  - Help shows development status warning: `ic gcp --help`

### Reporting Issues

If you encounter issues with development platforms:

1. Check the help output for known limitations: `ic azure --help` or `ic gcp --help`
2. Enable debug logging: `ic config set logging.level DEBUG`
3. Report issues with detailed logs on [GitHub Issues](https://github.com/dgr009/ic/issues)
4. Include platform, service, and command details in your report

## 🏗️ Development

### Project Structure

```
ic/
├── src/ic/                 # Main package
│   ├── cli.py             # CLI entry point and argument parsing
│   ├── config/            # Configuration management system
│   ├── core/              # Core utilities and logging
│   └── commands/          # Command implementations
├── aws/                   # AWS service modules
├── oci_module/            # Oracle Cloud Infrastructure modules
├── cf/                    # CloudFlare modules
├── ssh/                   # SSH management modules
├── azure_module/          # Azure modules (development)
├── gcp/                   # Google Cloud Platform modules (development)
├── common/                # Shared utilities and progress decorators
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── security/         # Security tests
├── docs/                  # Documentation
├── requirements.txt       # Python dependencies
└── pyproject.toml        # Package configuration
```

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/dgr009/ic.git
cd ic

# Create virtual environment
python -m venv ic-dev
source ic-dev/bin/activate  # On Windows: ic-dev\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install -e .[dev]

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

### Adding New Services

1. **Create service module**: Add new module in appropriate platform directory
2. **Implement progress decorators**: Use `@progress_bar_decorator` for long operations
3. **Add CLI integration**: Update `src/ic/cli.py` with new commands
4. **Add tests**: Create unit and integration tests
5. **Update documentation**: Add usage examples to README

### Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests only
pytest -m security       # Security tests only

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term

# Run performance tests
pytest -m performance
```

## 🤝 Contributing

We welcome contributions! Please see our contribution guidelines:

1. **Fork the repository** on GitHub
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** with appropriate tests
4. **Run the test suite**: `pytest`
5. **Update documentation** as needed
6. **Submit a pull request** with a clear description

### Code Standards

- Follow PEP 8 style guidelines
- Add type hints for new functions
- Include docstrings for public methods
- Add progress bar decorators for long-running operations
- Ensure security best practices for credential handling

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: This README and inline help (`ic --help`)
- **Issues**: [GitHub Issues](https://github.com/dgr009/ic/issues)
- **Discussions**: [GitHub Discussions](https://github.com/dgr009/ic/discussions)
- **Security**: Report security issues privately via GitHub Security Advisories

---

**Made with ❤️ for infrastructure engineers and cloud administrators**$`

