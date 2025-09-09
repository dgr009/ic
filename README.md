# IC CLI Tool

[![Tests](https://github.com/yourusername/ic-cli/workflows/Tests/badge.svg)](https://github.com/yourusername/ic-cli/actions)
[![PyPI version](https://badge.fury.io/py/ic-code.svg)](https://badge.fury.io/py/ic-code)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Infrastructure Command Line Interface tool for managing various cloud services and infrastructure components.

## Features

- **AWS Services**: EC2, S3, ECS, EKS, RDS, VPC, Load Balancers, MSK, and more
- **CloudFlare**: DNS record management with account/zone filtering
- **SSH**: Server information gathering and management with security filtering
- **OCI**: Oracle Cloud Infrastructure support
- **Multi-account/Multi-region**: Support for multiple AWS accounts and regions
- **Rich Output**: Beautiful terminal output with tables and colors
- **YAML Configuration**: Modern YAML-based configuration management
- **Security**: Separate secrets management with example templates

## Installation

### From PyPI (Recommended)

```bash
pip install ic-code
```

### From Source

```bash
# Clone the repository
git clone https://github.com/dgr009/ic.git
cd ic

# Create virtual environment
python -m venv ic-env
source ic-env/bin/activate  # On Windows: ic-env\Scripts\activate

# Install in development mode
pip install -e .
```

## Configuration

### YAML Configuration System

IC CLI uses a modern YAML-based configuration system with separate files for default settings and secrets.

#### 1. Create Configuration Files

```bash
# Copy example files (new preferred location)
mkdir -p .ic/config
cp .ic/config/secrets.yaml.example .ic/config/secrets.yaml

# Or use legacy location for backward compatibility
cp config/secrets.yaml.example config/secrets.yaml

# Edit with your actual values
vim .ic/config/secrets.yaml
```

#### 2. Configure Secrets (~/.ic/config/secrets.yaml)

```yaml
# AWS Configuration
aws:
  accounts:
    - "123456789012"  # Your AWS account IDs
    - "987654321098"
  profiles:
    default: "your-aws-profile-name"

# CloudFlare Configuration  
cloudflare:
  email: "your-email@example.com"
  api_token: "your-cloudflare-api-token"
  cloudflare_accounts: "account1,account2"  # Filter accounts
  cloudflare_zones: "zone1,zone2"           # Filter zones

# SSH Configuration (Security-sensitive)
ssh:
  key_dir: "~/aws-key"
  skip_prefixes:  # Skip servers with these prefixes
    - "git"
    - "bastion"
    - "jump"
    - "proxy"

# OCI Configuration
oci:
  config_file: "~/.oci/config"
  profile: "DEFAULT"
```

#### 3. Default Settings (.ic/config/default.yaml)

The default configuration is already provided and includes:
- AWS regions
- SSH connection settings
- Timeout values
- Other non-sensitive defaults

### AWS Credentials

Ensure your AWS credentials are configured:

```bash
# Using AWS CLI
aws configure

# Or use AWS profiles
aws configure --profile myprofile
```

## Usage

### AWS Services

```bash
# EC2 instances
ic aws ec2 info
ic aws ec2 info --account 123456789012 --regions us-east-1

# S3 buckets
ic aws s3 list_tags
ic aws s3 tag_check

# ECS services
ic aws ecs info
ic aws ecs service
ic aws ecs task

# EKS clusters
ic aws eks info
ic aws eks nodes
ic aws eks pods

# RDS instances
ic aws rds list_tags
ic aws rds tag_check

# Load Balancers
ic aws lb list_tags
ic aws lb tag_check

# VPC resources
ic aws vpc list_tags
ic aws vpc tag_check

# Security Groups
ic aws sg info

# MSK clusters
ic aws msk info
ic aws msk broker

# Fargate services
ic aws fargate info

# CodePipeline
ic aws codepipeline build
ic aws codepipeline deploy
```

### CloudFlare

```bash
# DNS records (filtered by configured accounts/zones)
ic cf dns info
ic cf dns info --account specific-account
ic cf dns info --zone specific-zone
```

### SSH Management

```bash
# Server information (with security filtering)
ic ssh info

# Auto-discover and register SSH servers
ic ssh reg
```

### OCI (Oracle Cloud Infrastructure)

```bash
# OCI information
ic oci info

# VM instances
ic oci vm

# Load balancers
ic oci lb
```

### Configuration Management

```bash
# View current configuration
ic config show

# Validate configuration
ic config validate

# Migrate from old configuration
ic config migrate
```

## Command Structure

The CLI follows a consistent structure:

```
ic <platform> <service> <command> [options]
```

- **platform**: aws, cf (CloudFlare), ssh, oci, config
- **service**: ec2, s3, ecs, eks, rds, etc.
- **command**: info, list_tags, tag_check, etc.
- **options**: --account, --regions, --name, etc.

## Examples

### Multi-account AWS EC2 Query

```bash
# Query EC2 instances across multiple accounts and regions
ic aws ec2 info --account 123456789012,987654321098 --regions us-east-1,ap-northeast-2
```

### CloudFlare DNS Management

```bash
# List all DNS records
ic cf dns info

# Filter by specific account
ic cf dns info --account production

# Filter by specific zone
ic cf dns info --zone example.com
```

### SSH Server Discovery

```bash
# Get information about all registered SSH servers
ic ssh info

# Auto-discover new SSH servers in your network
ic ssh reg
```

## Development

### Project Structure

```
ic/
├── src/ic/
│   ├── cli.py              # Main CLI entry point
│   ├── config/             # Configuration management
│   └── core/               # Core utilities
├── aws/                    # AWS service modules
├── cf/                     # CloudFlare modules
├── ssh/                    # SSH management modules
├── oci_module/             # OCI modules
├── common/                 # Common utilities
├── config/                 # Configuration files
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

### Adding New Services

1. Create a new module directory (e.g., `gcp/`)
2. Implement service-specific functions
3. Add CLI integration in `src/ic/cli.py`
4. Update documentation

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions, please use the GitHub issue tracker.$`

