# NCP Installation Guide

This guide covers the installation and initial setup of NCP (Naver Cloud Platform) integration for the IC CLI tool.

## Prerequisites

- Python 3.9 or higher (3.11.13 recommended)
- IC CLI tool installed
- NCP account with appropriate permissions
- Internet access to NCP APIs

## Installation Steps

### 1. Install Dependencies

```bash
# Install the IC CLI tool if not already installed
pip install ic-code

# Verify NCP support is available (no separate SDK needed)
ic ncp --help        # Should show NCP commands
ic ncpgov --help     # Should show NCP Government Cloud commands
```

### 2. Verify Installation

```bash
# Test NCP module imports
python -c "from ncp_module.client import NCPClient; print('NCP client: OK')"
python -c "from ncpgov_module.client import NCPGovClient; print('NCP Gov client: OK')"

# Verify core dependencies
python -c "import requests, yaml, cryptography; print('NCP dependencies: OK')"
```

### 3. Initial Configuration

After installation, you'll need to configure your NCP credentials. See the [Configuration Guide](configuration.md) for detailed instructions.

## Platform-Specific Requirements

### System Requirements

- Operating System: Linux, macOS, or Windows
- Memory: Minimum 512MB RAM
- Disk Space: 100MB free space

### NCP Requirements

- Valid NCP or NCP Government Cloud account
- API access enabled
- Access Key and Secret Key generated in NCP console
- Required permissions for services you plan to use

### Core Dependencies

IC CLI includes built-in NCP support without requiring external SDKs:

```
requests>=2.28.0,<3.0.0           # HTTP client for NCP API calls
PyYAML>=6.0,<=6.0.2               # Configuration file parsing
cryptography>=3.4.8,<42.0.0       # HMAC-SHA256 signature generation
rich>=12.0.0,<15.0.0              # Terminal output formatting
click>=8.0.0,<9.0.0               # CLI framework
```

## Alternative Installation Methods

### Method 1: Source Installation

```bash
# Clone repository
git clone https://github.com/dgr009/ic.git
cd ic

# Create virtual environment
python -m venv ncp-env
source ncp-env/bin/activate  # On Windows: ncp-env\Scripts\activate

# Install with NCP dependencies
pip install -r requirements.txt
pip install -e .

# Verify installation
ic ncp --help
```

### Method 2: Docker Installation

```bash
# Pull IC CLI Docker image (includes NCP support)
docker pull ic-cli:latest

# Run with NCP configuration mounted
docker run -v ~/.ncp:/root/.ncp -v ~/.ncpgov:/root/.ncpgov ic-cli:latest ic ncp ec2 info
```

## Troubleshooting Installation

### Common Issues

#### Issue: ModuleNotFoundError: No module named 'ncp_module'
```bash
# Solution: IC CLI includes built-in NCP support
pip install --upgrade ic-code

# Verify NCP modules are available
python -c "from ncp_module.client import NCPClient; print('NCP module: OK')"
```

#### Issue: ImportError: cannot import name 'NCPClient'
```bash
# Solution: Check IC CLI installation
pip list | grep ic-code

# Reinstall IC CLI
pip uninstall ic-code
pip install ic-code
```

#### Issue: Cryptography dependency errors
```bash
# Solution: Install/upgrade cryptography for HMAC-SHA256 signatures
pip install --upgrade cryptography>=3.4.8

# On Ubuntu/Debian:
sudo apt-get install build-essential libssl-dev libffi-dev python3-dev

# On macOS:
brew install openssl libffi
```

### Getting Help

If you encounter issues during installation:

1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Verify all prerequisites are met
3. Check the main project documentation
4. Report issues on the project repository

## Next Steps

After successful installation:

1. Configure your NCP credentials using the [Configuration Guide](configuration.md)
2. Learn how to use NCP commands in the [Usage Guide](usage.md)
3. Test your setup with basic commands:
   ```bash
   ic ncp ec2 info
   ic ncp s3 info
   ```