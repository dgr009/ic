# IC CLI Tool

[![Tests](https://github.com/dgr009/ic/workflows/Tests/badge.svg)](https://github.com/dgr009/ic/actions)
[![PyPI version](https://badge.fury.io/py/ic-code.svg)](https://badge.fury.io/py/ic-code)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive Infrastructure Command Line Interface tool for managing cloud services and infrastructure components across multiple platforms. IC CLI provides unified access to AWS, Oracle Cloud Infrastructure (OCI), NCP (Naver Cloud Platform), CloudFlare, and SSH server management with rich progress indicators and secure configuration management.

## ✨ Features

- **🚀 Multi-Cloud Support**: AWS, OCI, NCP (Naver Cloud Platform), CloudFlare, SSH server management
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

#### NCP Services (Production Ready)
- **Compute**: EC2 instances with detailed information and filtering
- **Storage**: S3 buckets with size and object count information
- **Networking**: VPC networks, subnets, and routing information
- **Database**: RDS instances with engine details and configuration
- **Security**: Security Groups with inbound/outbound rules
- **Government Cloud**: NCP Gov support with enhanced security compliance

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
# Install the latest stable version with full platform support
pip install ic-code

# Verify installation and platform support
ic --help
ic ncp --help      # Verify NCP support
ic ncpgov --help   # Verify NCP Government Cloud support

# Test NCP dependencies
python -c "from ncp_module.client import NCPClient; print('NCP support: OK')"
python -c "from ncpgov_module.client import NCPGovClient; print('NCP Gov support: OK')"
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
python scripts/validate_dependencies.py --platforms aws oci ncp
```

#### NCP-Specific Dependencies

IC CLI includes built-in NCP support without requiring separate SDK installation:

```bash
# NCP dependencies are included with IC CLI
pip install ic-code  # Includes all NCP dependencies

# Verify NCP support is available
ic ncp --help        # Should show NCP commands
ic ncpgov --help     # Should show NCP Gov commands

# Test NCP connectivity (requires configuration)
ic ncp ec2 info --dry-run     # Test NCP API connectivity
ic ncpgov ec2 info --dry-run  # Test NCP Gov API connectivity
```

**Core NCP Dependencies (automatically installed):**
- `requests>=2.28.0` - HTTP client for NCP API calls
- `PyYAML>=6.0` - Configuration file parsing
- `cryptography>=3.4.8` - HMAC-SHA256 signature generation
- `rich>=12.0.0` - Terminal output formatting

**Manual NCP Dependency Installation (if needed):**
```bash
# Install NCP-specific dependencies manually
pip install requests>=2.28.0 PyYAML>=6.0 cryptography>=3.4.8

# Verify cryptography installation for NCP signatures
python -c "from cryptography.hazmat.primitives import hashes, hmac; print('NCP crypto support: OK')"

# Test YAML parsing for NCP configuration
python -c "import yaml; print('NCP YAML support: OK')"
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

# NCP (Naver Cloud Platform) Configuration
ncp:
  access_key: "your-ncp-access-key"
  secret_key: "your-ncp-secret-key"
  region: "KR"  # KR (Korea), US (United States), JP (Japan)
  platform: "VPC"  # VPC (recommended) or Classic

# NCP Government Cloud Configuration
ncpgov:
  access_key: "your-ncpgov-access-key"
  secret_key: "your-ncpgov-secret-key"
  apigw_key: "your-ncpgov-apigw-key"  # API Gateway key for government cloud
  region: "KR"
  platform: "VPC"
  security:
    encryption_enabled: true
    audit_logging_enabled: true
    access_control_enabled: true
    mask_sensitive_data: true

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

**NCP Credentials:**
1. Go to NCP Console → My Page → API Key Management
2. Create Access Key and Secret Key
3. Add credentials to secrets.yaml
4. For NCP Gov: Use separate government cloud credentials

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

### NCP (Naver Cloud Platform) Services

NCP services support both **Standard Cloud** and **Government Cloud** environments with comprehensive resource management across compute, storage, networking, database, and security services.

#### NCP Standard Cloud Services

**Compute Services**
```bash
# EC2 instances with detailed information
ic ncp ec2 info                           # All NCP EC2 instances
ic ncp ec2 info --name web-server         # Filter by instance name
ic ncp ec2 info --verbose                 # Detailed instance information
ic ncp ec2 info --format json             # JSON output format
ic ncp ec2 info --region KR               # Specific region (KR, US, JP)

# Examples with filtering
ic ncp ec2 info --name "prod-*"           # Filter by name pattern
ic ncp ec2 info --status running          # Filter by instance status
```

**Storage Services**
```bash
# S3 object storage buckets
ic ncp s3 info                            # All NCP S3 buckets
ic ncp s3 info --name backup-bucket       # Filter by bucket name
ic ncp s3 info --verbose                  # Include size and object count
ic ncp s3 info --format table             # Table output format (default)

# Examples with detailed information
ic ncp s3 info --name "backup-*"          # Filter backup buckets
ic ncp s3 info --format json              # JSON format for automation
```

**Networking Services**
```bash
# VPC networking information
ic ncp vpc info                           # All NCP VPCs and subnets
ic ncp vpc info --name production-vpc     # Filter by VPC name
ic ncp vpc info --verbose                 # Include subnet and route details
ic ncp vpc info --format json             # JSON output

# Note: VPC services are only available on VPC platform
# Classic platform will show appropriate message
```

**Database Services**
```bash
# RDS database instances
ic ncp rds info                           # All NCP RDS instances
ic ncp rds info --name db-server          # Filter by database name
ic ncp rds info --verbose                 # Include engine and configuration details
ic ncp rds info --format json             # JSON output format

# Examples with filtering
ic ncp rds info --name "prod-db-*"        # Filter production databases
ic ncp rds info --engine mysql            # Filter by database engine
```

**Security Services**
```bash
# Security Groups (Access Control Groups)
ic ncp sg info                            # All security groups
ic ncp sg info --name web-sg              # Filter by security group name
ic ncp sg info --verbose                  # Include detailed rules
ic ncp sg info --format json              # JSON output format

# Examples with detailed rules
ic ncp sg info --name "web-*"             # Filter web-related security groups
ic ncp sg info --rules inbound            # Show inbound rules only
```

#### NCP Government Cloud Services

Government cloud services provide enhanced security, compliance features, and audit logging for sensitive workloads.

**Government Cloud Compute**
```bash
# Government cloud EC2 instances (enhanced security)
ic ncpgov ec2 info                        # All NCP Gov EC2 instances
ic ncpgov ec2 info --name secure-server   # Filter by instance name
ic ncpgov ec2 info --verbose              # Detailed info with compliance status
ic ncpgov ec2 info --format json          # JSON with masked sensitive data

# Government cloud specific features
ic ncpgov ec2 info --compliance-check     # Show compliance status
ic ncpgov ec2 info --audit-trail          # Include audit information
```

**Government Cloud Storage**
```bash
# Government cloud S3 storage (compliance features)
ic ncpgov s3 info                         # All NCP Gov S3 buckets
ic ncpgov s3 info --name secure-bucket    # Filter by bucket name
ic ncpgov s3 info --format json           # JSON output with masked sensitive data
ic ncpgov s3 info --compliance-report     # Include compliance information

# Enhanced security features
ic ncpgov s3 info --encryption-status     # Show encryption status
ic ncpgov s3 info --access-audit          # Include access audit logs
```

**Government Cloud Networking**
```bash
# Government cloud VPC (policy compliance)
ic ncpgov vpc info                        # All NCP Gov VPCs with compliance status
ic ncpgov vpc info --name gov-network     # Filter by VPC name
ic ncpgov vpc info --security-audit       # Include security audit information
ic ncpgov vpc info --compliance-check     # Show compliance validation

# Government cloud security features
ic ncpgov vpc info --policy-validation    # Validate against government policies
ic ncpgov vpc info --access-controls      # Show access control settings
```

**Government Cloud Database**
```bash
# Government cloud RDS with enhanced security
ic ncpgov rds info                        # All NCP Gov RDS instances
ic ncpgov rds info --name secure-db       # Filter by database name
ic ncpgov rds info --encryption-audit     # Show encryption and audit status
ic ncpgov rds info --compliance-report    # Include compliance information
```

**Government Cloud Security**
```bash
# Government cloud security groups with enhanced policies
ic ncpgov sg info                         # All government cloud security groups
ic ncpgov sg info --name secure-sg        # Filter by security group name
ic ncpgov sg info --policy-compliance     # Show policy compliance status
ic ncpgov sg info --audit-trail           # Include security audit trail
```

#### Platform Differences: Classic vs VPC

NCP supports two platform types with different capabilities:

**VPC Platform (Recommended)**
```bash
# VPC platform supports all modern services
ic ncp ec2 info --platform vpc            # VPC-based EC2 instances
ic ncp vpc info                           # VPC networking (VPC platform only)
ic ncp rds info --platform vpc            # VPC-based RDS instances
ic ncp sg info --platform vpc             # VPC security groups

# VPC platform features:
# - Modern networking with VPC and subnets
# - Enhanced security groups
# - Load balancers with advanced features
# - Better integration with other services
```

**Classic Platform (Legacy)**
```bash
# Classic platform supports legacy services
ic ncp ec2 info --platform classic       # Classic EC2 instances
ic ncp s3 info --platform classic        # Classic object storage
ic ncp sg info --platform classic        # Classic security groups

# Note: VPC services not available on Classic platform
ic ncp vpc info --platform classic       # Will show "VPC not available" message

# Classic platform limitations:
# - Legacy networking model
# - Limited security group features
# - Some modern services not available
# - Migration to VPC recommended
```

#### NCP Configuration Setup

**Quick Setup**
```bash
# Initialize NCP configuration with guided setup
ic config init                           # Interactive setup includes NCP options

# The setup process:
# 1. Select "NCP (Naver Cloud Platform)"
# 2. Choose "Standard Cloud" or "Government Cloud"
# 3. Enter Access Key and Secret Key
# 4. Select region (KR, US, JP)
# 5. Choose platform (VPC recommended, Classic legacy)

# Files created:
# - ~/.ncp/config (NCP standard cloud credentials)
# - ~/.ncpgov/config (NCP government cloud credentials)
# - Proper file permissions (600) for security
```

**Manual Configuration**
```bash
# Create NCP standard cloud configuration
mkdir -p ~/.ncp
cat > ~/.ncp/config << EOF
default:
  access_key: "your-ncp-access-key"
  secret_key: "your-ncp-secret-key"
  region: "KR"
  platform: "VPC"
EOF
chmod 600 ~/.ncp/config

# Create NCP government cloud configuration
mkdir -p ~/.ncpgov
cat > ~/.ncpgov/config << EOF
default:
  access_key: "your-ncpgov-access-key"
  secret_key: "your-ncpgov-secret-key"
  apigw_key: "your-ncpgov-apigw-key"
  region: "KR"
  platform: "VPC"
  security:
    encryption_enabled: true
    audit_logging_enabled: true
    access_control_enabled: true
    mask_sensitive_data: true
EOF
chmod 600 ~/.ncpgov/config
```

**Configuration Validation**
```bash
# Validate NCP configuration
ic config validate --ncp                 # Validate standard cloud config
ic config validate --ncpgov              # Validate government cloud config
ic config validate                       # Validate all configurations

# Show current configuration (sensitive data masked)
ic config show --ncp                     # Show NCP standard cloud config
ic config show --ncpgov                  # Show NCP government cloud config

# Test connectivity
ic ncp ec2 info --dry-run                # Test NCP API connectivity
ic ncpgov ec2 info --dry-run             # Test NCP Gov API connectivity
```

#### Multi-Region and Multi-Account Examples

**Multi-Region Operations**
```bash
# Query resources across different regions
ic ncp ec2 info --region KR              # Korea region
ic ncp ec2 info --region US              # United States region
ic ncp ec2 info --region JP              # Japan region

# Compare resources across regions
ic ncp s3 info --region KR --format json > kr_buckets.json
ic ncp s3 info --region US --format json > us_buckets.json
```

**Multi-Profile Configuration**
```yaml
# ~/.ncp/config - Multiple profiles
production:
  access_key: "prod-access-key"
  secret_key: "prod-secret-key"
  region: "KR"
  platform: "VPC"

development:
  access_key: "dev-access-key"
  secret_key: "dev-secret-key"
  region: "KR"
  platform: "VPC"

staging:
  access_key: "staging-access-key"
  secret_key: "staging-secret-key"
  region: "US"
  platform: "VPC"
```

```bash
# Use specific profiles
ic ncp ec2 info --profile production      # Use production profile
ic ncp ec2 info --profile development     # Use development profile
ic ncp ec2 info --profile staging         # Use staging profile

# Environment variable method
export NCP_PROFILE=production
ic ncp ec2 info                          # Uses production profile
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

# NCP configuration management
ic config get ncp.region               # Get NCP region
ic config set ncp.region "KR"          # Set NCP region
ic config get ncp.platform             # Get NCP platform (VPC/Classic)
ic config set ncp.platform "VPC"       # Set NCP platform
ic config validate --ncp               # Validate NCP configuration
ic config show --ncp                   # Show NCP configuration (masked)

# NCP Government cloud configuration
ic config get ncpgov.region            # Get NCP Gov region
ic config set ncpgov.region "KR"       # Set NCP Gov region
ic config get ncpgov.security.encryption_enabled  # Get security setting
ic config set ncpgov.security.encryption_enabled true  # Enable encryption
ic config validate --ncpgov            # Validate NCP Gov configuration
ic config show --ncpgov                # Show NCP Gov configuration (masked)

# Multi-profile management
ic config get ncp.production.region    # Get production profile region
ic config set ncp.development.platform "Classic"  # Set dev platform
ic config list-profiles --ncp          # List all NCP profiles
ic config list-profiles --ncpgov       # List all NCP Gov profiles
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

- **platform**: `aws`, `oci`, `ncp`, `ncpgov`, `cf` (CloudFlare), `ssh`, `config`
- **service**: `ec2`, `s3`, `ecs`, `eks`, `rds`, `vm`, `lb`, `vpc`, `dns`, etc.
- **command**: `info`, `list_tags`, `tag_check`, etc.
- **options**: `--account`, `--regions`, `--compartment-name`, `--name`, `--format`, etc.

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

# NCP-specific options
--name NAME_FILTER      # Filter resources by name
--format FORMAT         # Output format (table, json)
--region REGION_NAME    # Target specific NCP region (KR, US, JP)

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

# NCP infrastructure overview
ic ncp ec2 info --format json           # NCP standard cloud instances
ic ncp s3 info --verbose                # NCP object storage with size info
ic ncp vpc info                         # NCP networking information
ic ncp rds info                         # NCP database instances
ic ncp sg info                          # NCP security groups

# NCP Government cloud audit (enhanced security)
ic ncpgov ec2 info --compliance-check   # Government cloud instances with compliance
ic ncpgov s3 info --encryption-status   # Government cloud storage with encryption
ic ncpgov vpc info --security-audit     # Government cloud networking with security audit
ic ncpgov rds info --compliance-report  # Government cloud databases with compliance
ic ncpgov sg info --policy-compliance   # Government cloud security with policy check

# Cross-region NCP audit
ic ncp ec2 info --region KR --format json > ncp_kr_instances.json
ic ncp ec2 info --region US --format json > ncp_us_instances.json
ic ncp ec2 info --region JP --format json > ncp_jp_instances.json

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

## 📚 NCP Platform Guide

### Understanding NCP Platforms: Classic vs VPC

NCP offers two platform types with different capabilities and service availability:

#### VPC Platform (Recommended)

The VPC (Virtual Private Cloud) platform is the modern, recommended platform for new deployments:

**Features:**
- Modern networking with VPC and subnets
- Enhanced security groups with advanced rules
- Load balancers with advanced features
- Better integration with other NCP services
- Support for all modern NCP services

**Supported Services:**
```bash
ic ncp ec2 info --platform vpc     # VPC-based EC2 instances
ic ncp s3 info --platform vpc      # Object storage (available on both platforms)
ic ncp vpc info                    # VPC networking (VPC platform only)
ic ncp rds info --platform vpc     # VPC-based RDS instances
ic ncp sg info --platform vpc      # VPC security groups with advanced features
```

**Configuration Example:**
```yaml
# ~/.ncp/config - VPC Platform
default:
  access_key: "your-access-key"
  secret_key: "your-secret-key"
  region: "KR"
  platform: "VPC"  # Modern platform
```

#### Classic Platform (Legacy)

The Classic platform is the legacy platform maintained for backward compatibility:

**Features:**
- Legacy networking model
- Basic security groups
- Limited load balancer features
- Some modern services not available

**Supported Services:**
```bash
ic ncp ec2 info --platform classic # Classic EC2 instances
ic ncp s3 info --platform classic  # Object storage (available on both platforms)
ic ncp vpc info --platform classic # Will show "VPC not available on Classic" message
ic ncp rds info --platform classic # Classic RDS instances (limited features)
ic ncp sg info --platform classic  # Basic security groups
```

**Configuration Example:**
```yaml
# ~/.ncp/config - Classic Platform
default:
  access_key: "your-access-key"
  secret_key: "your-secret-key"
  region: "KR"
  platform: "Classic"  # Legacy platform
```

#### Migration from Classic to VPC

If you're currently using Classic platform, consider migrating to VPC:

```bash
# Check current platform
ic config get ncp.platform

# Switch to VPC platform
ic config set ncp.platform "VPC"

# Verify VPC services are available
ic ncp vpc info  # Should now show VPC information

# Compare resources between platforms
ic ncp ec2 info --platform classic --format json > classic_instances.json
ic ncp ec2 info --platform vpc --format json > vpc_instances.json
```

**Migration Benefits:**
- Access to modern networking features
- Enhanced security capabilities
- Better performance and reliability
- Support for new NCP services
- Future-proof infrastructure

### NCP Government Cloud Security

NCP Government Cloud provides enhanced security and compliance features:

#### Security Features

**Enhanced Authentication:**
- API Gateway authentication
- Multi-factor authentication support
- Enhanced access controls

**Data Protection:**
- Automatic data encryption
- Sensitive data masking in logs
- Audit trail logging
- Compliance reporting

**Configuration Example:**
```yaml
# ~/.ncpgov/config - Government Cloud Security
default:
  access_key: "your-gov-access-key"
  secret_key: "your-gov-secret-key"
  apigw_key: "your-apigw-key"
  region: "KR"
  platform: "VPC"
  security:
    encryption_enabled: true        # Mandatory for government cloud
    audit_logging_enabled: true     # Required for compliance
    access_control_enabled: true    # Enhanced access controls
    mask_sensitive_data: true       # Protect sensitive information
```

#### Compliance Features

**Audit and Monitoring:**
```bash
# Check compliance status
ic ncpgov ec2 info --compliance-check
ic ncpgov s3 info --encryption-status
ic ncpgov vpc info --security-audit

# Generate compliance reports
ic ncpgov rds info --compliance-report
ic ncpgov sg info --policy-compliance
```

**Security Validation:**
```bash
# Validate security settings
ic config validate --ncpgov --security

# Check encryption status
ic ncpgov s3 info --encryption-audit

# Review access controls
ic ncpgov vpc info --access-controls
```

## 📋 NCP Best Practices

### Security Best Practices

**Configuration Security:**
```bash
# Always use proper file permissions for configuration files
chmod 600 ~/.ncp/config ~/.ncpgov/config

# Verify permissions are correct
ls -la ~/.ncp/config ~/.ncpgov/config
# Should show: -rw------- (600 permissions)

# Never commit configuration files to version control
echo "~/.ncp/config" >> .gitignore
echo "~/.ncpgov/config" >> .gitignore

# Use environment variables in CI/CD instead of files
export NCP_ACCESS_KEY="${{ secrets.NCP_ACCESS_KEY }}"
export NCP_SECRET_KEY="${{ secrets.NCP_SECRET_KEY }}"
```

**API Key Management:**
```bash
# Rotate API keys regularly
# 1. Generate new keys in NCP Console
# 2. Update configuration
# 3. Test new keys
# 4. Revoke old keys

# Use separate keys for different environments
# Production keys should be different from development keys

# Monitor API key usage in NCP Console
# Check for unusual activity or unauthorized access
```

**Government Cloud Security:**
```bash
# Always enable all security features for government cloud
ic config set ncpgov.security.encryption_enabled true
ic config set ncpgov.security.audit_logging_enabled true
ic config set ncpgov.security.access_control_enabled true
ic config set ncpgov.security.mask_sensitive_data true

# Regularly validate compliance
ic ncpgov vpc info --compliance-check
ic ncpgov s3 info --encryption-status
ic ncpgov ec2 info --compliance-check
```

### Performance Best Practices

**Efficient Resource Queries:**
```bash
# Use name filters to reduce data transfer
ic ncp ec2 info --name "prod-*"        # Filter production instances
ic ncp s3 info --name "backup-*"       # Filter backup buckets

# Use appropriate output formats
ic ncp ec2 info --format json > instances.json  # For automation
ic ncp ec2 info --format table                  # For human reading

# Limit results for large datasets
ic ncp ec2 info --limit 50              # Limit to 50 results
ic ncp s3 info --limit 20               # Limit to 20 buckets
```

**Multi-Region Optimization:**
```bash
# Query specific regions instead of all regions
ic ncp ec2 info --region KR             # Korea region only
ic ncp ec2 info --region US             # US region only

# Use parallel queries for multiple regions (in scripts)
ic ncp ec2 info --region KR --format json > kr_instances.json &
ic ncp ec2 info --region US --format json > us_instances.json &
wait  # Wait for both to complete
```

**Caching for Repeated Queries:**
```bash
# Enable caching for repeated queries
export NCP_CACHE_ENABLED=true
export NCP_CACHE_TTL=300  # 5 minutes

# Use cached results for faster subsequent queries
ic ncp ec2 info  # First call - queries API
ic ncp ec2 info  # Second call - uses cache (if within TTL)
```

### Automation Best Practices

**CI/CD Integration:**
```yaml
# GitHub Actions example
name: NCP Infrastructure Check
on: [push, pull_request]
jobs:
  ncp-check:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Setup Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    - name: Install IC CLI
      run: pip install ic-code
    - name: Check NCP Resources
      env:
        NCP_ACCESS_KEY: ${{ secrets.NCP_ACCESS_KEY }}
        NCP_SECRET_KEY: ${{ secrets.NCP_SECRET_KEY }}
      run: |
        ic ncp ec2 info --format json > ncp_instances.json
        ic ncp s3 info --format json > ncp_buckets.json
        ic ncp vpc info --format json > ncp_vpcs.json
```

**Scripting Best Practices:**
```bash
#!/bin/bash
# ncp_audit_script.sh - Example audit script

set -e  # Exit on error

# Set up logging
LOG_FILE="ncp_audit_$(date +%Y%m%d_%H%M%S).log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "Starting NCP infrastructure audit..."

# Check configuration
if ! ic config validate --ncp; then
    echo "ERROR: NCP configuration validation failed"
    exit 1
fi

# Audit all services
echo "Auditing EC2 instances..."
ic ncp ec2 info --format json > ec2_audit.json

echo "Auditing S3 buckets..."
ic ncp s3 info --format json > s3_audit.json

echo "Auditing VPC networks..."
ic ncp vpc info --format json > vpc_audit.json

echo "Auditing RDS databases..."
ic ncp rds info --format json > rds_audit.json

echo "Auditing Security Groups..."
ic ncp sg info --format json > sg_audit.json

echo "NCP audit completed successfully"
```

**Error Handling in Scripts:**
```bash
#!/bin/bash
# ncp_with_error_handling.sh

# Function to handle errors
handle_error() {
    echo "ERROR: $1" >&2
    exit 1
}

# Test NCP connectivity before proceeding
if ! ic ncp ec2 info --dry-run >/dev/null 2>&1; then
    handle_error "NCP API connectivity test failed"
fi

# Use error handling for each command
ic ncp ec2 info --format json > instances.json || handle_error "Failed to get EC2 instances"
ic ncp s3 info --format json > buckets.json || handle_error "Failed to get S3 buckets"

echo "All NCP operations completed successfully"
```

## 🔧 Troubleshooting

### NCP-Specific Troubleshooting

For NCP (Naver Cloud Platform) specific issues:
- **Installation Guide**: [NCP Installation Guide](docs/ncp_installation_guide.md)
- **Troubleshooting**: [NCP Troubleshooting Guide](docs/ncp_troubleshooting_guide.md)

#### Quick NCP Troubleshooting

**Configuration Issues:**
```bash
# Check if NCP configuration exists
ls -la ~/.ncp/config ~/.ncpgov/config

# Validate NCP configuration
ic config validate --ncp
ic config validate --ncpgov

# Show current NCP configuration (masked)
ic config show --ncp
ic config show --ncpgov

# Test NCP API connectivity
ic ncp ec2 info --dry-run
ic ncpgov ec2 info --dry-run
```

**Authentication Issues:**
```bash
# Verify NCP credentials in console
# NCP Console → My Page → API Key Management

# Check file permissions (must be 600)
chmod 600 ~/.ncp/config ~/.ncpgov/config

# Test with environment variables
export NCP_ACCESS_KEY="your-key"
export NCP_SECRET_KEY="your-secret"
ic ncp ec2 info
```

**Platform-Specific Issues:**
```bash
# Check platform configuration
ic config get ncp.platform        # Should be "VPC" or "Classic"

# VPC services not available on Classic platform
ic ncp vpc info --platform classic  # Will show "not available" message

# Switch to VPC platform
ic config set ncp.platform "VPC"
```

**Government Cloud Issues:**
```bash
# Verify API Gateway key is configured
ic config get ncpgov.apigw_key

# Check security settings
ic config get ncpgov.security.encryption_enabled

# Enable compliance mode
ic config set ncpgov.security.compliance_mode true
```

**Regional Issues:**
```bash
# Check supported regions
ic config get ncp.region          # Should be KR, US, or JP

# Test different regions
ic ncp ec2 info --region KR
ic ncp ec2 info --region US
ic ncp ec2 info --region JP

# Some services may not be available in all regions
```

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

**NCP Issues:**
- Ensure NCP dependencies are installed: `pip install ic-code` (includes NCP support)
- Check API credentials in NCP Console → My Page → API Key Management
- Verify configuration files exist: `~/.ncp/config` and `~/.ncpgov/config`
- Check file permissions: `chmod 600 ~/.ncp/config ~/.ncpgov/config`
- Validate platform compatibility: VPC platform recommended, Classic is legacy
- For government cloud: Ensure API Gateway key is configured
- Test connectivity: `ic ncp ec2 info --dry-run` and `ic ncpgov ec2 info --dry-run`
- Check region availability: Some services may not be available in all regions
- Verify platform-specific services: VPC services not available on Classic platform

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

# NCP service help
ic ncp --help                    # NCP platform overview
ic ncp ec2 --help               # NCP EC2 service help
ic ncp s3 --help                # NCP S3 service help
ic ncp vpc --help               # NCP VPC service help
ic ncp rds --help               # NCP RDS service help
ic ncp sg --help                # NCP Security Group help

# NCP Government cloud help
ic ncpgov --help                # NCP Gov platform overview
ic ncpgov ec2 --help            # NCP Gov EC2 service help
ic ncpgov s3 --help             # NCP Gov S3 service help
ic ncpgov vpc --help            # NCP Gov VPC service help
ic ncpgov rds --help            # NCP Gov RDS service help
ic ncpgov sg --help             # NCP Gov Security Group help

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
- ✅ **NCP**: Fully tested and production ready (Standard and Government Cloud)
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
├── ncp_module/            # NCP (Naver Cloud Platform) modules
├── ncpgov_module/         # NCP Government Cloud modules
├── ncp/                   # NCP legacy modules (compatibility)
├── ncpgov/                # NCP Gov legacy modules (compatibility)
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
pytest -m ncp            # NCP-specific tests only
pytest -m ncpgov         # NCP Government cloud tests only

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

